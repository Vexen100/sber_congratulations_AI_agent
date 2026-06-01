from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.core.config import settings


@dataclass(frozen=True)
class LLMResponse:
    content: str
    model_name: str


class LLMProvider(Protocol):
    async def generate_text(self, messages: list[dict], **kwargs) -> LLMResponse:
        raise NotImplementedError


def get_project_planner_llm_provider() -> LLMProvider | None:
    if bool(settings.project_planner_use_mock_llm):
        return None
    if not settings.gigachat_credentials:
        return None

    from app.llm.gigachat_provider import GigaChatLLMProvider

    return GigaChatLLMProvider()
