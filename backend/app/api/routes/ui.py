from __future__ import annotations

import datetime as dt
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agent.orchestrator import run_once
from app.core.config import settings
from app.db.models import AgentRun, Client, Delivery, Event, Feedback, Greeting
from app.db.session import get_session
from app.services.autonomy import get_or_create_state, next_daily_run_at
from app.services.company_enrichment import (
    enrich_client_company_by_id,
    enrich_missing_clients,
)
from app.services.company_import import import_clients_from_company_csv
from app.services.manual_events import seed_manual_campaign_for_real_clients
from app.services.reset_runtime import reset_runtime_data

router = APIRouter(prefix="/ui")


class ManualCampaignCreate(BaseModel):
    title: str = Field(default="Персональное деловое поздравление", max_length=250)
    count: int = Field(default=5, ge=1, le=20)
    event_date: dt.date | None = None


def _datetime(value: dt.datetime | None) -> str | None:
    return value.isoformat() if value else None


def _date(value: dt.date | None) -> str | None:
    return value.isoformat() if value else None


def _image_url(image_path: str | None) -> str | None:
    if not image_path:
        return None
    clean_path = image_path.replace("\\", "/").lstrip("/")
    return f"/data/{quote(clean_path, safe='/')}"


def _client_payload(client: Client | None) -> dict | None:
    if client is None:
        return None
    return {
        "id": client.id,
        "first_name": client.first_name,
        "middle_name": client.middle_name,
        "last_name": client.last_name,
        "company_name": client.company_name,
        "official_company_name": client.official_company_name,
        "position": client.position,
        "profession": client.profession,
        "inn": client.inn,
        "ogrn": client.ogrn,
        "kpp": client.kpp,
        "ceo_name": client.ceo_name,
        "okved_code": client.okved_code,
        "okved_name": client.okved_name,
        "company_status": client.company_status,
        "company_address": client.company_address,
        "company_site": client.company_site,
        "source_url": client.source_url,
        "enrichment_status": client.enrichment_status,
        "enrichment_error": client.enrichment_error,
        "enriched_at": _datetime(client.enriched_at),
        "email": client.email,
        "phone": client.phone,
        "preferred_channel": client.preferred_channel,
        "birth_date": _date(client.birth_date),
        "preferences": client.preferences or {},
        "last_interaction_summary": client.last_interaction_summary,
        "is_demo": client.is_demo,
        "created_at": _datetime(client.created_at),
    }


def _event_payload(event: Event | None, *, include_client: bool = True) -> dict | None:
    if event is None:
        return None
    payload = {
        "id": event.id,
        "client_id": event.client_id,
        "event_type": event.event_type,
        "event_date": _date(event.event_date),
        "title": event.title,
        "metadata": event.details or {},
        "created_at": _datetime(event.created_at),
    }
    if include_client:
        payload["client"] = _client_payload(event.client)
    return payload


def _feedback_payload(feedback: Feedback) -> dict:
    return {
        "id": feedback.id,
        "greeting_id": feedback.greeting_id,
        "outcome": feedback.outcome,
        "score": feedback.score,
        "notes": feedback.notes,
        "training_verdict": feedback.training_verdict,
        "created_at": _datetime(feedback.created_at),
    }


def _delivery_payload(delivery: Delivery, *, include_greeting: bool = False) -> dict:
    payload = {
        "id": delivery.id,
        "greeting_id": delivery.greeting_id,
        "channel": delivery.channel,
        "recipient": delivery.recipient,
        "status": delivery.status,
        "provider_message": delivery.provider_message,
        "sent_at": _datetime(delivery.sent_at),
        "idempotency_key": delivery.idempotency_key,
    }
    if include_greeting:
        greeting_payload = _greeting_payload(delivery.greeting, include_relations=False)
        if greeting_payload is not None and delivery.greeting is not None:
            greeting_payload["client"] = _client_payload(delivery.greeting.client)
        payload["greeting"] = greeting_payload
    return payload


def _greeting_payload(greeting: Greeting | None, *, include_relations: bool = True) -> dict | None:
    if greeting is None:
        return None
    payload = {
        "id": greeting.id,
        "event_id": greeting.event_id,
        "client_id": greeting.client_id,
        "agent_run_id": greeting.agent_run_id,
        "tone": greeting.tone,
        "subject": greeting.subject,
        "body": greeting.body,
        "image_path": greeting.image_path,
        "image_url": _image_url(greeting.image_path),
        "generation_source": greeting.generation_source,
        "status": greeting.status,
        "created_at": _datetime(greeting.created_at),
    }
    if include_relations:
        feedback_entries = sorted(greeting.feedback_entries or [], key=lambda item: item.id)
        payload.update(
            {
                "event": _event_payload(greeting.event, include_client=False),
                "client": _client_payload(greeting.client),
                "deliveries": [
                    _delivery_payload(delivery)
                    for delivery in sorted(greeting.deliveries or [], key=lambda item: item.id)
                ],
                "feedback_entries": [_feedback_payload(item) for item in feedback_entries],
            }
        )
    return payload


def _run_payload(run: AgentRun) -> dict:
    return {
        "id": run.id,
        "triggered_by": run.triggered_by,
        "status": run.status,
        "started_at": _datetime(run.started_at),
        "finished_at": _datetime(run.finished_at),
        "lookahead_days": run.lookahead_days,
        "llm_mode": run.llm_mode,
        "image_mode": run.image_mode,
        "scanned_events": run.scanned_events,
        "generated_greetings": run.generated_greetings,
        "sent_deliveries": run.sent_deliveries,
        "skipped_existing": run.skipped_existing,
        "errors": run.errors,
        "notes": run.notes,
    }


@router.get("/dashboard")
async def dashboard_data(session: AsyncSession = Depends(get_session)) -> dict:
    clients_count = (await session.execute(select(func.count(Client.id)))).scalar_one()
    enriched_clients_count = (
        await session.execute(
            select(func.count(Client.id)).where(Client.enrichment_status == "enriched")
        )
    ).scalar_one()
    events_count = (await session.execute(select(func.count(Event.id)))).scalar_one()
    greetings_count = (await session.execute(select(func.count(Greeting.id)))).scalar_one()
    deliveries_count = (await session.execute(select(func.count(Delivery.id)))).scalar_one()
    feedback_count = (await session.execute(select(func.count(Feedback.id)))).scalar_one()
    greetings_with_training_verdict = (
        await session.execute(
            select(func.count(func.distinct(Feedback.greeting_id))).where(
                Feedback.training_verdict.is_not(None)
            )
        )
    ).scalar_one()
    sent_greetings_count = (
        await session.execute(
            select(func.count(func.distinct(Delivery.greeting_id))).where(Delivery.status == "sent")
        )
    ).scalar_one()
    delivery_errors_count = (
        await session.execute(select(func.count(Delivery.id)).where(Delivery.status == "error"))
    ).scalar_one()
    greetings_with_feedback_count = (
        await session.execute(select(func.count(func.distinct(Feedback.greeting_id))))
    ).scalar_one()
    feedback_avg_score = (
        await session.execute(select(func.avg(Feedback.score)).where(Feedback.score.is_not(None)))
    ).scalar()
    runs_with_issues_count = (
        await session.execute(
            select(func.count(AgentRun.id)).where(AgentRun.status.in_(("partial", "error")))
        )
    ).scalar_one()
    last_runs = (
        (await session.execute(select(AgentRun).order_by(AgentRun.id.desc()).limit(10)))
        .scalars()
        .all()
    )

    return {
        "clients_count": clients_count,
        "enriched_clients_count": enriched_clients_count,
        "events_count": events_count,
        "greetings_count": greetings_count,
        "deliveries_count": deliveries_count,
        "feedback_count": feedback_count,
        "greetings_with_training_verdict": greetings_with_training_verdict,
        "sent_greetings_count": sent_greetings_count,
        "delivery_errors_count": delivery_errors_count,
        "greetings_with_feedback_count": greetings_with_feedback_count,
        "feedback_avg_score": (
            round(float(feedback_avg_score), 1) if feedback_avg_score is not None else None
        ),
        "runs_with_issues_count": runs_with_issues_count,
        "delivery_success_rate": (
            round((sent_greetings_count / greetings_count) * 100) if greetings_count else 0
        ),
        "feedback_coverage_rate": (
            round((greetings_with_feedback_count / greetings_count) * 100) if greetings_count else 0
        ),
        "last_runs": [_run_payload(run) for run in last_runs],
    }


@router.post("/agent/run-once")
async def run_agent_from_ui(session: AsyncSession = Depends(get_session)) -> dict:
    summary = await run_once(session, triggered_by="web-ui")
    return summary.as_dict()


@router.post("/seed-demo")
async def seed_demo_from_ui(session: AsyncSession = Depends(get_session)) -> dict:
    from app.api.routes.clients import seed_demo_clients

    result = await seed_demo_clients(session, n=5, replace=True)
    return {"message": "Демо-данные загружены.", **result}


@router.post("/reset-runtime")
async def reset_runtime_from_ui(session: AsyncSession = Depends(get_session)) -> dict:
    result = await reset_runtime_data(session, clear_clients=True)
    message = (
        f"Данные очищены. кол-во очищенных клиентов: {result['cleared_clients']}, "
        f"кол-во очищенных файлов: {result['cleared_files']}"
    )
    return {"message": message, **result}


@router.get("/clients")
async def clients_data(session: AsyncSession = Depends(get_session)) -> dict:
    clients = (await session.execute(select(Client).order_by(Client.id.desc()))).scalars().all()
    provider = (settings.company_enrichment_provider or "demo").strip().lower()
    return {
        "clients": [_client_payload(client) for client in clients],
        "company_enrichment_provider": provider,
    }


@router.post("/clients/enrich-missing")
async def enrich_clients_from_ui(session: AsyncSession = Depends(get_session)) -> dict:
    result = await enrich_missing_clients(session)
    provider = (settings.company_enrichment_provider or "demo").strip().lower()
    message = (
        f"Обогащение ({provider}) завершено. Обогащено: {result['enriched']}, "
        f"ошибки: {result['errors']}, успешно: {result['processed']}"
    )
    return {"message": message, **result}


@router.post("/clients/refresh-external")
async def refresh_clients_external_from_ui(session: AsyncSession = Depends(get_session)) -> dict:
    result = await enrich_missing_clients(session, force=True)
    provider = (settings.company_enrichment_provider or "demo").strip().lower()
    message = (
        f"Актуализация ({provider}) завершена. Актуализировано: {result['enriched']}, "
        f"ошибки: {result['errors']}, успешно: {result['processed']}"
    )
    return {"message": message, **result}


@router.post("/clients/import-company-base")
async def import_company_base_from_ui(session: AsyncSession = Depends(get_session)) -> dict:
    result = await import_clients_from_company_csv(session)
    message = (
        f"Импорт базы компаний завершён. Добавлено: {result['added']}, "
        f"обновлено: {result['updated']}, пропущено: {result['skipped']}"
    )
    return {"message": message, **result}


@router.post("/clients/{client_id}/enrich")
async def enrich_client_from_ui(
    client_id: int, session: AsyncSession = Depends(get_session)
) -> dict:
    result = await enrich_client_company_by_id(session, client_id=client_id)
    if result["status"] == "enriched":
        return {"message": f"Профиль клиента #{client_id} успешно обогащён.", **result}
    raise HTTPException(
        status_code=400,
        detail=result.get("reason", "Не удалось обогатить профиль клиента."),
    )


@router.get("/events")
async def events_data(session: AsyncSession = Depends(get_session)) -> dict:
    events = (
        (
            await session.execute(
                select(Event).options(selectinload(Event.client)).order_by(Event.event_date.asc())
            )
        )
        .scalars()
        .all()
    )
    clients = (
        (
            await session.execute(
                select(Client)
                .where(Client.is_demo.is_(False))
                .order_by(Client.company_name.asc(), Client.id.asc())
            )
        )
        .scalars()
        .all()
    )
    return {
        "events": [_event_payload(event) for event in events],
        "clients": [_client_payload(client) for client in clients],
    }


@router.post("/events/demo-campaign")
async def create_demo_campaign_from_ui(
    payload: ManualCampaignCreate, session: AsyncSession = Depends(get_session)
) -> dict:
    result = await seed_manual_campaign_for_real_clients(
        session,
        event_date=payload.event_date or dt.date.today(),
        title=payload.title,
        limit=payload.count,
    )
    message = (
        f"Demo-кампания создана: events={result['created']}, "
        f"duplicates={result['duplicates']}, clients={result['selected_clients']}"
    )
    return {"message": message, **result}


@router.get("/greetings")
async def greetings_data(session: AsyncSession = Depends(get_session)) -> dict:
    greetings = (
        (
            await session.execute(
                select(Greeting)
                .options(
                    selectinload(Greeting.event),
                    selectinload(Greeting.client),
                    selectinload(Greeting.deliveries),
                    selectinload(Greeting.feedback_entries),
                )
                .order_by(Greeting.id.desc())
            )
        )
        .scalars()
        .all()
    )
    return {"greetings": [_greeting_payload(greeting) for greeting in greetings]}


@router.get("/deliveries")
async def deliveries_data(session: AsyncSession = Depends(get_session)) -> dict:
    deliveries = (
        (
            await session.execute(
                select(Delivery)
                .options(selectinload(Delivery.greeting).selectinload(Greeting.client))
                .order_by(Delivery.id.desc())
            )
        )
        .scalars()
        .all()
    )
    return {
        "deliveries": [
            _delivery_payload(delivery, include_greeting=True) for delivery in deliveries
        ]
    }


@router.get("/runs")
async def runs_data(session: AsyncSession = Depends(get_session)) -> dict:
    autonomy = await get_or_create_state(session)
    now = dt.datetime.now(dt.timezone.utc)
    next_run = next_daily_run_at(now=now) if autonomy.enabled else None
    runs = (
        (await session.execute(select(AgentRun).order_by(AgentRun.id.desc()).limit(100)))
        .scalars()
        .all()
    )
    total_runs = (await session.execute(select(func.count(AgentRun.id)))).scalar_one()
    grouped_statuses = (
        await session.execute(
            select(AgentRun.status, func.count(AgentRun.id)).group_by(AgentRun.status)
        )
    ).all()
    status_totals = {"success": 0, "partial": 0, "error": 0, "running": 0}
    for status, count in grouped_statuses:
        status_totals[status] = count
    return {
        "runs": [_run_payload(run) for run in runs],
        "total_runs": total_runs,
        "status_totals": status_totals,
        "autonomy": {
            "enabled": autonomy.enabled,
            "next_run_at": _datetime(next_run),
        },
    }


@router.get("/runs/{run_id}")
async def run_detail_data(run_id: int, session: AsyncSession = Depends(get_session)) -> dict:
    run = (
        await session.execute(select(AgentRun).where(AgentRun.id == run_id))
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Запуск агента не найден.")

    greetings = (
        (
            await session.execute(
                select(Greeting)
                .where(Greeting.agent_run_id == run_id)
                .options(
                    selectinload(Greeting.client),
                    selectinload(Greeting.event),
                    selectinload(Greeting.deliveries),
                    selectinload(Greeting.feedback_entries),
                )
                .order_by(Greeting.id.desc())
            )
        )
        .scalars()
        .all()
    )
    actual_deliveries = sum(len(greeting.deliveries) for greeting in greetings)
    actual_sent = sum(
        1
        for greeting in greetings
        for delivery in greeting.deliveries
        if (delivery.status or "").lower() == "sent"
    )
    greetings_with_feedback = sum(1 for greeting in greetings if greeting.feedback_entries)
    greetings_with_training_verdict = sum(
        1
        for greeting in greetings
        if any(getattr(item, "training_verdict", None) for item in greeting.feedback_entries)
    )
    return {
        "run": _run_payload(run),
        "greetings": [_greeting_payload(greeting) for greeting in greetings],
        "actual_deliveries": actual_deliveries,
        "actual_sent": actual_sent,
        "greetings_with_feedback": greetings_with_feedback,
        "greetings_with_training_verdict": greetings_with_training_verdict,
    }
