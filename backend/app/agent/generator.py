from __future__ import annotations

import datetime as dt
import logging

from app.agent.addressing import (
    build_formal_name,
    build_respectful_greeting,
    infer_gender_hint,
    normalize_generated_salutation,
)
from app.agent.event_semantics import build_event_semantics
from app.agent.llm_prompts import build_system_prompt, build_user_prompt
from app.agent.llm_provider import LLMProviderError, get_llm_provider, parse_llm_json
from app.agent.text_generator import generate_text
from app.db.models import Client, Event
from app.services.guardrails import validate_message_text
from app.services.template_selector import TemplateChoice

log = logging.getLogger(__name__)


def _allowed_facts(client: Client) -> dict:
    # Keep the set minimal to avoid leakage and hallucinations.
    return {
        "first_name": client.first_name,
        "middle_name": (getattr(client, "middle_name", None) or ""),
        "last_name": client.last_name,
        "company_name": client.company_name,
        "official_company_name": getattr(client, "official_company_name", None),
        "position": client.position,
        "profession": (getattr(client, "profession", None) or ""),
        "inn": getattr(client, "inn", None),
        "ceo_name": getattr(client, "ceo_name", None),
        "okved_code": getattr(client, "okved_code", None),
        "okved_name": getattr(client, "okved_name", None),
        "company_site": getattr(client, "company_site", None),
        "formal_name": build_formal_name(
            first_name=client.first_name,
            middle_name=getattr(client, "middle_name", None),
        ),
        "respectful_greeting": build_respectful_greeting(
            first_name=client.first_name,
            middle_name=getattr(client, "middle_name", None),
        ),
        "gender_hint": infer_gender_hint(
            first_name=client.first_name,
            middle_name=getattr(client, "middle_name", None),
        ),
        # We intentionally do not pass last_interaction_summary to the model to avoid leaking topics/details.
        # Note: we deliberately do not pass email/phone to the LLM.
    }


def _generation_context(client: Client, event: Event) -> dict:
    context = _allowed_facts(client)
    semantics = build_event_semantics(
        event_type=event.event_type,
        event_title=event.title,
        event_details=event.details or {},
        profession=getattr(client, "profession", None),
    )
    context.update(
        {
            "event_semantic_category": semantics.category,
            "event_semantic_focus": semantics.focus_hint,
            "event_prompt_hint": semantics.prompt_hint,
            "event_greeting_guidance": semantics.greeting_guidance,
            "event_visual_theme": semantics.visual_theme,
        }
    )
    if event.event_type == "holiday" and event.details:
        holiday_tags = event.details.get("holiday_tags", {}) or {}
        context.update(
            {
                "holiday_category": holiday_tags.get("category"),
                "holiday_focus_hint": holiday_tags.get("focus_hint"),
                "holiday_prompt_hint": holiday_tags.get("prompt_hint"),
                "holiday_audience": holiday_tags.get("audience"),
            }
        )
    if event.event_type == "manual" and event.details:
        context.update(
            {
                "manual_kind": event.details.get("manual_kind"),
                "focus_hint": event.details.get("focus_hint"),
                "event_tone_hint": event.details.get("tone_hint"),
            }
        )
    return context


async def generate_subject_body(
    *,
    event: Event,
    client: Client,
    template_choice: TemplateChoice,
    today: dt.date | None = None,
) -> tuple[str, str, str]:
    """Return (tone, subject, body).

    Strategy:
    1) If LLM is enabled, ask it for strict JSON, validate + guardrails.
    2) On any error → fallback to deterministic template generation.
    """
    _ = today  # reserved for future use (e.g., "today" in prompt)

    provider = get_llm_provider()
    if provider is not None:
        try:
            facts = _generation_context(client, event)
            # Extract tone_hint from holiday tags if available
            tone_hint = None
            if event.event_type == "holiday" and event.details:
                holiday_tags = event.details.get("holiday_tags", {})
                tone_hint = holiday_tags.get("tone_hint")
            elif event.event_type == "manual" and event.details:
                tone_hint = event.details.get("tone_hint")

            system = build_system_prompt()
            user = build_user_prompt(
                event_type=event.event_type,
                event_title=event.title,
                event_date=event.event_date,
                facts=facts,
                tone_hint=tone_hint,
                event_details=event.details or {},
            )
            raw = await provider.generate(system=system, user=user)
            log.debug(
                "LLM raw response for event=%s client=%s (first 1000 chars, total length=%d): %s",
                event.id,
                client.id,
                len(raw),
                raw[:1000] if len(raw) > 1000 else raw,
            )
            parsed = parse_llm_json(raw)

            # Strict validation: body must be at least 450 characters (as per prompt requirement)
            if len(parsed.body) < 450:
                raise LLMProviderError(
                    f"LLM generated body too short: {len(parsed.body)} chars "
                    f"(minimum required: 450, target: 600-900)"
                )

            normalized_body = normalize_generated_salutation(parsed.body, client=client)
            validate_message_text(parsed.subject)
            validate_message_text(normalized_body)

            log.debug(
                "LLM generated greeting for event=%s client=%s: tone=%s subject_len=%d body_len=%d",
                event.id,
                client.id,
                parsed.tone,
                len(parsed.subject),
                len(parsed.body),
            )
            return parsed.tone, parsed.subject, normalized_body
        except Exception as e:
            # Log the error for debugging, then fallback to templates
            log.warning(
                "LLM generation failed for event=%s client=%s, falling back to template: %s",
                getattr(event, "id", None),
                getattr(client, "id", None),
                e,
            )

    # Fallback to template-based generation
    log.debug(
        "Using template fallback for event=%s client=%s (LLM not configured or failed)",
        getattr(event, "id", None),
        getattr(client, "id", None),
    )
    subject, body = generate_text(
        template_choice,
        context=_generation_context(client, event),
        title=event.title,
    )
    normalized_body = normalize_generated_salutation(body, client=client)
    validate_message_text(subject)
    validate_message_text(normalized_body)
    return template_choice.tone, subject, normalized_body
