from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import agent, clients, deliveries, events, greetings, health

api_router = APIRouter(prefix="/api")

api_router.include_router(health.router, tags=["health"])
api_router.include_router(clients.router, tags=["clients"])
api_router.include_router(events.router, tags=["events"])
api_router.include_router(greetings.router, tags=["greetings"])
api_router.include_router(deliveries.router, tags=["deliveries"])
api_router.include_router(agent.router, tags=["agent"])
