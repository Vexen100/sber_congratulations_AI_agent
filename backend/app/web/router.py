from __future__ import annotations

import datetime as dt
from pathlib import Path

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
    # Reuse API logic quickly: add a couple of clients if empty-ish
    existing = (await session.execute(select(func.count(Client.id)))).scalar_one()
    if existing < 1:
        from app.api.routes.clients import seed_demo

        await seed_demo(session)
    return RedirectResponse(url="/clients", status_code=303)


@router.post("/actions/reset-runtime")
async def action_reset_runtime(session: AsyncSession = Depends(get_session)):
    await reset_runtime_data(session)
    return RedirectResponse(url="/", status_code=303)


@router.get("/clients", response_class=HTMLResponse)
async def clients_page(request: Request, session: AsyncSession = Depends(get_session)):
    clients = (await session.execute(select(Client).order_by(Client.id.desc()))).scalars().all()
    return templates.TemplateResponse("clients.html", {"request": request, "clients": clients})


@router.post("/clients")
async def clients_create(
    first_name: str = Form(...),
    last_name: str = Form(...),
    company_name: str = Form(""),
    position: str = Form(""),
    segment: str = Form("standard"),
    email: str = Form(""),
    phone: str = Form(""),
    preferred_channel: str = Form("email"),
    birth_date: str = Form(""),
    session: AsyncSession = Depends(get_session),
):
    bd = None
    if birth_date.strip():
        bd = dt.date.fromisoformat(birth_date.strip())
    c = Client(
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        company_name=company_name.strip() or None,
        position=position.strip() or None,
        segment=segment.strip() or "standard",
        email=email.strip() or None,
        phone=phone.strip() or None,
        preferred_channel=preferred_channel.strip() or "email",
        birth_date=bd,
        preferences={},
    )
    session.add(c)
    await session.commit()
    return RedirectResponse(url="/clients", status_code=303)


@router.get("/events", response_class=HTMLResponse)
async def events_page(request: Request, session: AsyncSession = Depends(get_session)):
    events = (await session.execute(select(Event).order_by(Event.event_date.asc()))).scalars().all()
    return templates.TemplateResponse("events.html", {"request": request, "events": events})


@router.get("/greetings", response_class=HTMLResponse)
async def greetings_page(request: Request, session: AsyncSession = Depends(get_session)):
    greetings = (
        (await session.execute(select(Greeting).order_by(Greeting.id.desc()))).scalars().all()
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
