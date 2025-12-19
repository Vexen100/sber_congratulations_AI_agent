from __future__ import annotations

import datetime as dt
import logging

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
        "last_name": client.last_name,
        "company_name": client.company_name,
        "position": client.position,
        "segment": client.segment,
        # We intentionally do not pass last_interaction_summary to the model to avoid leaking topics/details.
        # Note: we deliberately do not pass email/phone to the LLM.
    }


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
            facts = _allowed_facts(client)
            # Extract tone_hint from holiday tags if available
            tone_hint = None
            if event.event_type == "holiday" and event.details:
                holiday_tags = event.details.get("holiday_tags", {})
                tone_hint = holiday_tags.get("tone_hint")

            system = build_system_prompt()
            user = build_user_prompt(
                event_type=event.event_type,
                event_title=event.title,
                event_date=event.event_date,
                segment=client.segment,
                facts=facts,
                tone_hint=tone_hint,
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

            validate_message_text(parsed.subject)
            validate_message_text(parsed.body)

            log.debug(
                "LLM generated greeting for event=%s client=%s: tone=%s subject_len=%d body_len=%d",
                event.id,
                client.id,
                parsed.tone,
                len(parsed.subject),
                len(parsed.body),
            )
            return parsed.tone, parsed.subject, parsed.body
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
        context=_allowed_facts(client),
        title=event.title,
    )
    validate_message_text(subject)
    validate_message_text(body)
    return template_choice.tone, subject, body
