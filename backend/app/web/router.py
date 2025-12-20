from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agent.orchestrator import run_once
from app.db.models import AgentRun, Client, Delivery, Event, Greeting
from app.db.session import get_session
from app.services.approval import approve_greeting, reject_greeting
from app.services.reset_runtime import reset_runtime_data

router = APIRouter()

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, session: AsyncSession = Depends(get_session)):
    clients_count = (await session.execute(select(func.count(Client.id)))).scalar_one()
    events_count = (await session.execute(select(func.count(Event.id)))).scalar_one()
    greetings_count = (await session.execute(select(func.count(Greeting.id)))).scalar_one()
    deliveries_count = (await session.execute(select(func.count(Delivery.id)))).scalar_one()
    last_runs = (
        (await session.execute(select(AgentRun).order_by(AgentRun.id.desc()).limit(10)))
        .scalars()
        .all()
    )

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "clients_count": clients_count,
            "events_count": events_count,
            "greetings_count": greetings_count,
            "deliveries_count": deliveries_count,
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
    await reset_runtime_data(session)
    return RedirectResponse(url="/", status_code=303)


@router.get("/clients", response_class=HTMLResponse)
async def clients_page(request: Request, session: AsyncSession = Depends(get_session)):
    clients = (await session.execute(select(Client).order_by(Client.id.desc()))).scalars().all()
    qp = request.query_params
    return templates.TemplateResponse(
        "clients.html",
        {
            "request": request,
            "clients": clients,
            "msg": qp.get("msg", ""),
            "error": qp.get("error", ""),
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


@router.post("/clients")
async def clients_create(
    first_name: str = Form(...),
    middle_name: str = Form(...),
    last_name: str = Form(...),
    company_name: str = Form(""),
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
            position=position.strip() or None,
            profession=prof,
            segment=seg,
            email=em,
            phone=phone.strip() or None,
            preferred_channel=pref,
            birth_date=bd,
            preferences={},
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
    events = (await session.execute(select(Event).order_by(Event.event_date.asc()))).scalars().all()
    return templates.TemplateResponse("events.html", {"request": request, "events": events})


@router.get("/greetings", response_class=HTMLResponse)
async def greetings_page(request: Request, session: AsyncSession = Depends(get_session)):
    greetings = (
        (
            await session.execute(
                select(Greeting)
                .options(selectinload(Greeting.event), selectinload(Greeting.client))
                .order_by(Greeting.id.desc())
            )
        )
        .scalars()
        .all()
    )
    return templates.TemplateResponse(
        "greetings.html", {"request": request, "greetings": greetings}
    )


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
    return templates.TemplateResponse(
        "deliveries.html", {"request": request, "deliveries": deliveries}
    )


@router.get("/runs", response_class=HTMLResponse)
async def runs_page(request: Request, session: AsyncSession = Depends(get_session)):
    runs = (
        (await session.execute(select(AgentRun).order_by(AgentRun.id.desc()).limit(100)))
        .scalars()
        .all()
    )
    return templates.TemplateResponse("runs.html", {"request": request, "runs": runs})
