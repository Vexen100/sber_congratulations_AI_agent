from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agent.orchestrator import run_once
from app.core.config import settings
from app.db.models import AgentRun, Client, Delivery, Event, Feedback, Greeting
from app.db.session import get_session
from app.services.approval import approve_greeting, reject_greeting
from app.services.company_enrichment import enrich_client_company_by_id, enrich_missing_clients
from app.services.company_import import import_clients_from_company_csv
from app.services.feedback import save_feedback
from app.services.manual_events import (
    create_manual_event_record,
    seed_manual_campaign_for_real_clients,
)
from app.services.reset_runtime import reset_runtime_data

router = APIRouter()

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _split_contact_values(value: str | None) -> list[str]:
    text = (value or "").replace("\r", "\n")
    text = text.replace(";", ",").replace("\n", ",")
    parts = [re.sub(r"\s+", " ", chunk).strip(" ,") for chunk in text.split(",")]
    return [part for part in parts if part]


templates.env.globals["split_contact_values"] = _split_contact_values


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, session: AsyncSession = Depends(get_session)):
    qp = request.query_params
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
    greetings_needing_approval = (
        await session.execute(
            select(func.count(Greeting.id)).where(Greeting.status == "needs_approval")
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
    delivery_success_rate = (
        round((sent_greetings_count / greetings_count) * 100) if greetings_count else 0
    )
    feedback_coverage_rate = (
        round((greetings_with_feedback_count / greetings_count) * 100) if greetings_count else 0
    )
    last_runs = (
        (await session.execute(select(AgentRun).order_by(AgentRun.id.desc()).limit(10)))
        .scalars()
        .all()
    )

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "msg": qp.get("msg", ""),
            "clients_count": clients_count,
            "enriched_clients_count": enriched_clients_count,
            "events_count": events_count,
            "greetings_count": greetings_count,
            "deliveries_count": deliveries_count,
            "feedback_count": feedback_count,
            "greetings_needing_approval": greetings_needing_approval,
            "sent_greetings_count": sent_greetings_count,
            "delivery_errors_count": delivery_errors_count,
            "greetings_with_feedback_count": greetings_with_feedback_count,
            "feedback_avg_score": (
                round(float(feedback_avg_score or 0), 1) if feedback_avg_score is not None else None
            ),
            "runs_with_issues_count": runs_with_issues_count,
            "delivery_success_rate": delivery_success_rate,
            "feedback_coverage_rate": feedback_coverage_rate,
            "last_runs": last_runs,
        },
    )


@router.post("/actions/run-agent")
async def action_run_agent(session: AsyncSession = Depends(get_session)):
    await run_once(session, triggered_by="web-ui")
    return RedirectResponse(url="/greetings", status_code=303)


@router.post("/actions/seed-demo")
async def action_seed_demo(session: AsyncSession = Depends(get_session)):
    # Reseed demo data every time: random 5 clients with upcoming birthdays (good for demos).
    from app.api.routes.clients import seed_demo_clients

    await seed_demo_clients(session, n=5, replace=True)
    return RedirectResponse(url="/clients", status_code=303)


@router.post("/actions/reset-runtime")
async def action_reset_runtime(session: AsyncSession = Depends(get_session)):
    result = await reset_runtime_data(session, clear_clients=True)
    msg = (
        f"Данные очищены. кол-во очищенных клиентов: {result['cleared_clients']}, "
        f"кол-во очищенных файлов: {result['cleared_files']}"
    )
    return RedirectResponse(url=f"/?msg={quote(msg)}", status_code=303)


@router.post("/actions/enrich-clients")
async def action_enrich_clients(session: AsyncSession = Depends(get_session)):
    result = await enrich_missing_clients(session)
    provider = (settings.company_enrichment_provider or "demo").strip().lower()
    msg = (
        f"Обогащение завершено. Обогащено: {result['enriched']}, "
        f"ошибки: {result['errors']}, успешно: {result['processed']}"
    )
    return RedirectResponse(url=f"/clients?msg={quote(msg)}", status_code=303)


@router.post("/actions/refresh-clients-external")
async def action_refresh_clients_external(session: AsyncSession = Depends(get_session)):
    provider = (settings.company_enrichment_provider or "demo").strip().lower()
    result = await enrich_missing_clients(session, force=True)
    msg = (
        f"Актуализация ({provider}) завершена. Актуализировано: {result['enriched']}, "
        f"ошибки: {result['errors']}, успешно: {result['processed']}"
    )
    return RedirectResponse(url=f"/clients?msg={quote(msg)}", status_code=303)


@router.post("/actions/import-company-base")
async def action_import_company_base(session: AsyncSession = Depends(get_session)):
    result = await import_clients_from_company_csv(session)
    msg = (
        f"Импорт базы компаний завершён. Добавлено: {result['added']}, "
        f"обновлено: {result['updated']}, пропущено: {result['skipped']}"
    )
    return RedirectResponse(url=f"/clients?msg={quote(msg)}", status_code=303)


@router.post("/actions/clients/{client_id}/enrich")
async def action_enrich_client(client_id: int, session: AsyncSession = Depends(get_session)):
    result = await enrich_client_company_by_id(session, client_id=client_id)
    if result["status"] == "enriched":
        msg = f"Профиль клиента #{client_id} успешно обогащён."
        return RedirectResponse(url=f"/clients?msg={quote(msg)}", status_code=303)
    error = result.get("reason", "Не удалось обогатить профиль клиента.")
    return RedirectResponse(url=f"/clients?error={quote(error)}", status_code=303)


@router.get("/clients", response_class=HTMLResponse)
async def clients_page(request: Request, session: AsyncSession = Depends(get_session)):
    clients = (await session.execute(select(Client).order_by(Client.id.desc()))).scalars().all()
    qp = request.query_params
    return templates.TemplateResponse(
        request,
        "clients.html",
        {
            "clients": clients,
            "msg": qp.get("msg", ""),
            "error": qp.get("error", ""),
            "company_enrichment_provider": (settings.company_enrichment_provider or "demo")
            .strip()
            .lower(),
            "delivery_schedule_mode": (settings.delivery_schedule_mode or "event_date")
            .strip()
            .lower(),
        },
    )


_NAME_RE = re.compile(r"^[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё\s\-]{1,49}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PROFESSIONS = {
    "management",
    "finance",
    "accounting",
    "it",
    "hr",
    "marketing",
    "sales",
    "logistics",
    "construction",
    "medicine",
    "security",
}


def _validate_human_name(value: str, *, field: str) -> str:
    v = (value or "").strip()
    if not _NAME_RE.fullmatch(v):
        raise ValueError(f"{field}: используйте 2-50 символов (буквы/пробел/дефис)")
    return v


def _validate_email(value: str) -> str:
    v = (value or "").strip()
    if not _EMAIL_RE.fullmatch(v):
        raise ValueError("email: некорректный формат")
    low = v.lower()
    if low.endswith("@example.com") or low.endswith(".invalid") or low.endswith(".example"):
        raise ValueError("email: используйте реальный адрес (example.com запрещён)")
    return v


def _normalize_inn(value: str) -> str | None:
    digits = re.sub(r"\D", "", value or "")
    if not digits:
        return None
    if len(digits) not in {10, 12}:
        raise ValueError("inn: ИНН должен содержать 10 или 12 цифр")
    return digits


@router.post("/clients")
async def clients_create(
    first_name: str = Form(...),
    middle_name: str = Form(...),
    last_name: str = Form(...),
    company_name: str = Form(""),
    inn: str = Form(""),
    position: str = Form(""),
    profession: str = Form(...),
    segment: str = Form("standard"),
    email: str = Form(""),
    phone: str = Form(""),
    preferred_channel: str = Form("email"),
    birth_date: str = Form(""),
    session: AsyncSession = Depends(get_session),
):
    try:
        fn = _validate_human_name(first_name, field="first_name")
        mn = _validate_human_name(middle_name, field="middle_name")
        ln = _validate_human_name(last_name, field="last_name")
        prof = (profession or "").strip().lower()
        if prof not in _PROFESSIONS:
            raise ValueError("profession: выберите значение из списка")
        seg = (segment or "standard").strip().lower()
        if seg not in {"standard", "vip", "loyal", "new"}:
            raise ValueError("segment: недопустимое значение")

        bd = None
        if birth_date.strip():
            bd = dt.date.fromisoformat(birth_date.strip())
        norm_inn = _normalize_inn(inn)

        pref = (preferred_channel or "email").strip().lower()
        if pref not in {"email", "sms", "messenger"}:
            raise ValueError("preferred_channel: недопустимое значение")

        em = None
        if email.strip():
            em = _validate_email(email)
        if pref == "email" and not em:
            raise ValueError("email: обязателен для preferred_channel=email")

        # Keep total clients at 5 to avoid hitting GigaChat image limits in demo.
        clients = (
            (await session.execute(select(Client).order_by(Client.created_at.asc())))
            .scalars()
            .all()
        )
        if len(clients) >= 5:
            demo_clients = [c for c in clients if getattr(c, "is_demo", False)]
            if demo_clients:
                # Remove the oldest demo client to keep capacity.
                await session.delete(demo_clients[0])
                await session.commit()
            else:
                raise ValueError(
                    "Лимит: уже 5 реальных клиентов. Удалите одного или используйте Seed demo data."
                )

        c = Client(
            first_name=fn,
            middle_name=mn,
            last_name=ln,
            company_name=company_name.strip() or None,
            official_company_name=None,
            inn=norm_inn,
            position=position.strip() or None,
            profession=prof,
            segment=seg,
            email=em,
            phone=phone.strip() or None,
            preferred_channel=pref,
            birth_date=bd,
            preferences={},
            enrichment_status="pending" if norm_inn else "not_requested",
            is_demo=False,
        )
        session.add(c)
        await session.commit()
        return RedirectResponse(
            url=f"/clients?msg={quote('Клиент добавлен. Реальные письма отправляются только на ручные email.')}",
            status_code=303,
        )
    except Exception as e:
        return RedirectResponse(url=f"/clients?error={quote(str(e))}", status_code=303)


@router.get("/events", response_class=HTMLResponse)
async def events_page(request: Request, session: AsyncSession = Depends(get_session)):
    qp = request.query_params
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
    return templates.TemplateResponse(
        request,
        "events.html",
        {
            "events": events,
            "clients": clients,
            "msg": qp.get("msg", ""),
            "error": qp.get("error", ""),
        },
    )


@router.post("/actions/events/manual")
async def action_create_manual_event(
    client_id: int = Form(...),
    title: str = Form(...),
    event_date: str = Form(...),
    session: AsyncSession = Depends(get_session),
):
    try:
        date_value = dt.date.fromisoformat(event_date.strip())
        await create_manual_event_record(
            session,
            client_id=client_id,
            event_date=date_value,
            title=title,
            metadata={"source": "web-manual"},
        )
        return RedirectResponse(
            url=f"/events?msg={quote('Ручное событие создано')}",
            status_code=303,
        )
    except Exception as e:
        return RedirectResponse(url=f"/events?error={quote(str(e))}", status_code=303)


@router.post("/actions/events/demo-campaign")
async def action_create_demo_campaign(
    title: str = Form("Персональное деловое поздравление"),
    count: int = Form(5),
    event_date: str = Form(""),
    session: AsyncSession = Depends(get_session),
):
    try:
        date_value = (
            dt.date.fromisoformat(event_date.strip()) if event_date.strip() else dt.date.today()
        )
        result = await seed_manual_campaign_for_real_clients(
            session,
            event_date=date_value,
            title=title,
            limit=max(1, min(int(count), 20)),
        )
        msg = (
            f"Demo-кампания создана: events={result['created']}, "
            f"duplicates={result['duplicates']}, clients={result['selected_clients']}"
        )
        return RedirectResponse(url=f"/events?msg={quote(msg)}", status_code=303)
    except Exception as e:
        return RedirectResponse(url=f"/events?error={quote(str(e))}", status_code=303)


@router.get("/greetings", response_class=HTMLResponse)
async def greetings_page(request: Request, session: AsyncSession = Depends(get_session)):
    qp = request.query_params
    greetings = (
        (
            await session.execute(
                select(Greeting)
                .options(
                    selectinload(Greeting.event),
                    selectinload(Greeting.client),
                    selectinload(Greeting.feedback_entries),
                )
                .order_by(Greeting.id.desc())
            )
        )
        .scalars()
        .all()
    )
    return templates.TemplateResponse(
        request,
        "greetings.html",
        {
            "greetings": greetings,
            "msg": qp.get("msg", ""),
            "error": qp.get("error", ""),
            "delivery_schedule_mode": (settings.delivery_schedule_mode or "event_date")
            .strip()
            .lower(),
        },
    )


@router.post("/actions/greetings/{greeting_id}/feedback")
async def action_feedback_greeting(
    greeting_id: int,
    score: int | None = Form(None),
    outcome: str = Form("unknown"),
    notes: str = Form(""),
    session: AsyncSession = Depends(get_session),
):
    try:
        await save_feedback(
            session,
            greeting_id=greeting_id,
            score=score,
            outcome=outcome,
            notes=notes,
        )
        return RedirectResponse(
            url=f"/greetings?msg={quote('Отзыв сохранён')}",
            status_code=303,
        )
    except Exception as e:
        return RedirectResponse(url=f"/greetings?error={quote(str(e))}", status_code=303)


@router.post("/actions/greetings/{greeting_id}/approve")
async def action_approve_greeting(
    greeting_id: int,
    session: AsyncSession = Depends(get_session),
):
    await approve_greeting(session, greeting_id=greeting_id, approved_by="web-ui")
    return RedirectResponse(url="/greetings", status_code=303)


@router.post("/actions/greetings/{greeting_id}/reject")
async def action_reject_greeting(
    greeting_id: int,
    session: AsyncSession = Depends(get_session),
):
    await reject_greeting(session, greeting_id=greeting_id, rejected_by="web-ui")
    return RedirectResponse(url="/greetings", status_code=303)


@router.get("/deliveries", response_class=HTMLResponse)
async def deliveries_page(request: Request, session: AsyncSession = Depends(get_session)):
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
    return templates.TemplateResponse(request, "deliveries.html", {"deliveries": deliveries})


@router.get("/runs", response_class=HTMLResponse)
async def runs_page(request: Request, session: AsyncSession = Depends(get_session)):
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
    return templates.TemplateResponse(
        request,
        "runs.html",
        {"runs": runs, "total_runs": total_runs, "status_totals": status_totals},
    )


@router.get("/runs/{run_id}", response_class=HTMLResponse)
async def run_detail_page(
    run_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
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
    greetings_needing_approval = sum(
        1 for greeting in greetings if (greeting.status or "").lower() == "needs_approval"
    )
    return templates.TemplateResponse(
        request,
        "run_detail.html",
        {
            "run": run,
            "greetings": greetings,
            "actual_deliveries": actual_deliveries,
            "actual_sent": actual_sent,
            "greetings_with_feedback": greetings_with_feedback,
            "greetings_needing_approval": greetings_needing_approval,
        },
    )
