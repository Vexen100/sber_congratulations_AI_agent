from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import (
    agent,
    autonomy,
    clients,
    deliveries,
    events,
    feedback,
    greetings,
    health,
    ui,
)
from app.project_planner.router import router as project_planner_router

api_router = APIRouter(prefix="/api")

api_router.include_router(health.router, tags=["health"])
api_router.include_router(clients.router, tags=["clients"])
api_router.include_router(events.router, tags=["events"])
api_router.include_router(greetings.router, tags=["greetings"])
api_router.include_router(deliveries.router, tags=["deliveries"])
api_router.include_router(feedback.router, tags=["feedback"])
api_router.include_router(agent.router, tags=["agent"])
api_router.include_router(autonomy.router, tags=["autonomy"])
api_router.include_router(ui.router, tags=["ui"])
api_router.include_router(project_planner_router, tags=["project-planner"])
