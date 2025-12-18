from __future__ import annotations

import datetime as dt

from app.agent.llm_prompts import build_system_prompt, build_user_prompt
from app.agent.llm_provider import get_llm_provider, parse_llm_json
from app.agent.text_generator import generate_text
from app.db.models import Client, Event
from app.services.guardrails import validate_message_text
from app.services.template_selector import TemplateChoice


def _allowed_facts(client: Client) -> dict:
    # Keep the set minimal to avoid leakage and hallucinations.
    return {
        "first_name": client.first_name,
        "last_name": client.last_name,
        "company_name": client.company_name,
        "position": client.position,
        "segment": client.segment,
        "last_interaction_summary": client.last_interaction_summary,
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
            system = build_system_prompt()
            user = build_user_prompt(
                event_type=event.event_type,
                event_title=event.title,
                event_date=event.event_date,
                segment=client.segment,
                facts=facts,
            )
            raw = await provider.generate(system=system, user=user)
            parsed = parse_llm_json(raw)

            validate_message_text(parsed.subject)
            validate_message_text(parsed.body)

            return parsed.tone, parsed.subject, parsed.body
        except Exception:
            # Any parsing/provider issues → fallback
            pass

    subject, body = generate_text(
        template_choice,
        context=_allowed_facts(client),
        title=event.title,
    )
    validate_message_text(subject)
    validate_message_text(body)
    return template_choice.tone, subject, body
