from __future__ import annotations

import datetime as dt
import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.generator import generate_subject_body
from app.agent.gigachat_providers import GigaChatImageProvider, build_card_image_prompt
from app.core.config import settings
from app.db.models import AgentRun, Client, Event, Greeting
from app.services.card_renderer import render_card
from app.services.event_detector import ensure_upcoming_events
from app.services.sender import send_greeting_file
from app.services.template_selector import choose_template

log = logging.getLogger(__name__)


class AgentSummary:
    def __init__(self) -> None:
        self.scanned_events = 0
        self.generated_greetings = 0
        self.sent_deliveries = 0
        self.skipped_existing = 0
        self.errors = 0

    def as_dict(self) -> dict:
        return {
            "scanned_events": self.scanned_events,
            "generated_greetings": self.generated_greetings,
            "sent_deliveries": self.sent_deliveries,
            "skipped_existing": self.skipped_existing,
            "errors": self.errors,
        }


def _client_context(c: Client) -> dict:
    return {
        "first_name": c.first_name,
        "last_name": c.last_name,
        "company_name": c.company_name,
        "position": c.position,
        "segment": c.segment,
        "preferred_channel": c.preferred_channel,
        "email": c.email,
        "phone": c.phone,
        "last_interaction_summary": c.last_interaction_summary,
        "preferences": c.preferences or {},
    }


async def run_once(
    session: AsyncSession,
    *,
    today: dt.date | None = None,
    lookahead_days: int | None = None,
    triggered_by: str = "unknown",
) -> AgentSummary:
    today = today or dt.date.today()
    lookahead_days = int(lookahead_days or settings.lookahead_days)

    summary = AgentSummary()

    # Create AgentRun record early to have audit trail even on failures.
    run = AgentRun(
        triggered_by=triggered_by,
        status="running",
        lookahead_days=lookahead_days,
        llm_mode=(settings.llm_mode or "template"),
        image_mode=(settings.image_mode or "pillow"),
        started_at=dt.datetime.now(dt.timezone.utc),
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    run_id = run.id

    # 1) Ensure events exist (idempotent)
    try:
        await ensure_upcoming_events(session, today=today, lookahead_days=lookahead_days)

        # 2) Fetch events in window
        end = today + dt.timedelta(days=lookahead_days)
        events = (
            (
                await session.execute(
                    select(Event).where(Event.event_date >= today).where(Event.event_date <= end)
                )
            )
            .scalars()
            .all()
        )

        for ev in events:
            summary.scanned_events += 1
            try:
                # Skip if greeting already exists for this event
                existing = (
                    await session.execute(select(Greeting.id).where(Greeting.event_id == ev.id))
                ).first()
                if existing:
                    summary.skipped_existing += 1
                    continue

                client = None
                if ev.client_id is not None:
                    client = (
                        await session.execute(select(Client).where(Client.id == ev.client_id))
                    ).scalar_one_or_none()
                if not client:
                    # For MVP we require a client to personalize and send.
                    summary.errors += 1
                    continue

                choice = choose_template(
                    segment=client.segment, event_type=ev.event_type, title=ev.title
                )
                tone, subject, body = await generate_subject_body(
                    event=ev, client=client, template_choice=choice, today=today
                )

                # Render card
                cards_dir = Path(__file__).resolve().parents[2] / "data" / "cards"
                recipient_line = f"{client.first_name} {client.last_name}".strip()
                card_path = None
                if (
                    settings.image_mode or "pillow"
                ).lower() == "gigachat" and settings.gigachat_credentials:
                    try:
                        style, prompt = build_card_image_prompt(
                            event_title=ev.title,
                            recipient_line=recipient_line,
                            company=client.company_name,
                        )
                        provider = GigaChatImageProvider()
                        file_id, jpg = await provider.generate_jpg(
                            system_style=style,
                            prompt=prompt,
                            x_client_id=str(client.id),
                        )
                        cards_dir.mkdir(parents=True, exist_ok=True)
                        filename = f"gigachat_{file_id}.jpg"
                        card_path = cards_dir / filename
                        card_path.write_bytes(jpg)
                    except Exception:
                        # Fallback to deterministic Pillow card
                        card_path = None

                if card_path is None:
                    card_path = render_card(
                        out_dir=cards_dir,
                        title=ev.title,
                        recipient_line=recipient_line,
                        date=ev.event_date,
                        brand_line="Сбер",
                    )

                greeting = Greeting(
                    event_id=ev.id,
                    client_id=client.id,
                    tone=tone,
                    subject=subject,
                    body=body,
                    image_path=str(card_path),
                    status="needs_approval" if client.segment.lower() == "vip" else "generated",
                )
                session.add(greeting)
                await session.commit()
                await session.refresh(greeting)
                summary.generated_greetings += 1

                # Send (MVP: file outbox) — only if not VIP approval-gated
                if client.segment.lower() != "vip":
                    recipient = client.email or client.phone or f"client:{client.id}"
                    delivery = await send_greeting_file(
                        session, greeting=greeting, recipient=recipient
                    )
                    if delivery.status == "sent":
                        greeting.status = "sent"
                        await session.commit()
                        summary.sent_deliveries += 1

            except Exception as e:
                log.exception("agent error on event=%s: %s", getattr(ev, "id", None), e)
                summary.errors += 1
                await session.rollback()
    except Exception as e:
        log.exception("agent fatal error: %s", e)
        summary.errors += 1
        await session.rollback()
    finally:
        # Finalize AgentRun
        run2 = (
            await session.execute(select(AgentRun).where(AgentRun.id == run_id))
        ).scalar_one_or_none()
        if run2:
            run2.scanned_events = summary.scanned_events
            run2.generated_greetings = summary.generated_greetings
            run2.sent_deliveries = summary.sent_deliveries
            run2.skipped_existing = summary.skipped_existing
            run2.errors = summary.errors
            run2.finished_at = dt.datetime.now(dt.timezone.utc)
            if summary.errors == 0:
                run2.status = "success"
            elif summary.generated_greetings > 0:
                run2.status = "partial"
            else:
                run2.status = "error"
            await session.commit()

    return summary
