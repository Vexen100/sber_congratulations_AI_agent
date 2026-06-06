from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RegionCoefficient:
    name: str
    coefficient: float


REGION_COEFFICIENTS: tuple[RegionCoefficient, ...] = (
    RegionCoefficient("Свердловская область", 1.00),
    RegionCoefficient("Челябинская область", 0.95),
    RegionCoefficient("Тюменская область", 1.10),
    RegionCoefficient("Курганская область", 0.90),
    RegionCoefficient("Республика Башкортостан", 0.95),
    RegionCoefficient("ХМАО", 1.25),
    RegionCoefficient("ЯНАО", 1.35),
)

PROJECT_TYPES = ("event", "it", "hr", "marketing", "operations")

BUDGET_BASE_ITEMS: dict[str, float] = {
    "Подготовка и управление проектом": 280_000,
    "Подрядчики и экспертная поддержка": 420_000,
    "Маркетинг и коммуникации": 180_000,
    "Техническое обеспечение": 260_000,
    "Резерв на риски": 160_000,
}

UNIVERSAL_ROLES: tuple[dict, ...] = (
    {
        "title": "Руководитель проекта",
        "count": 1,
        "competencies": ["планирование", "управление сроками", "коммуникации"],
        "assignment_comment": "Отвечает за общий результат, сроки и согласования.",
    },
    {
        "title": "Бизнес-заказчик",
        "count": 1,
        "competencies": ["видение результата", "приоритизация", "приёмка"],
        "assignment_comment": "Фиксирует цели, критерии успеха и принимает ключевые решения.",
    },
    {
        "title": "Координатор проекта",
        "count": 1,
        "competencies": ["операционное сопровождение", "протоколирование", "контроль задач"],
        "assignment_comment": "Поддерживает календарь, документы и коммуникации команды.",
    },
    {
        "title": "Финансовый аналитик",
        "count": 1,
        "competencies": ["смета", "контроль бюджета", "оценка рисков"],
        "assignment_comment": "Готовит предварительную смету и контролирует бюджетные допущения.",
    },
    {
        "title": "Коммуникационный менеджер",
        "count": 1,
        "competencies": ["внутренние коммуникации", "презентации", "работа с аудиторией"],
        "assignment_comment": "Отвечает за информирование участников и материалы для защиты.",
    },
)

ROADMAP_PHASE_TEMPLATES: tuple[dict, ...] = (
    {
        "name": "Инициация и уточнение замысла",
        "milestones": (
            "Зафиксировать цель и критерии успеха",
            "Определить стейкхолдеров и формат управления",
            "Согласовать ограничения по срокам и бюджету",
        ),
    },
    {
        "name": "Проектирование решения",
        "milestones": (
            "Подготовить целевой сценарий проекта",
            "Сформировать предварительную смету",
            "Выбрать роли команды и зону ответственности",
        ),
    },
    {
        "name": "Подготовка реализации",
        "milestones": (
            "Подготовить материалы и ресурсы",
            "Согласовать план коммуникаций",
            "Провести контрольную проверку рисков",
        ),
    },
    {
        "name": "Реализация и запуск",
        "milestones": (
            "Провести ключевые работы проекта",
            "Отследить контрольные точки",
            "Собрать обратную связь по промежуточным результатам",
        ),
    },
    {
        "name": "Завершение и защита результата",
        "milestones": (
            "Собрать итоговые материалы",
            "Подготовить защиту проекта",
            "Зафиксировать выводы и дальнейшие шаги",
        ),
    },
)


def normalize_region_name(value: str | None) -> str:
    text = (value or "").strip()
    if not text:
        return "Свердловская область"
    lowered = text.lower()
    for item in REGION_COEFFICIENTS:
        if item.name.lower() in lowered or lowered in item.name.lower():
            return item.name
    return text


def region_coefficient(value: str | None) -> float:
    name = normalize_region_name(value)
    for item in REGION_COEFFICIENTS:
        if item.name == name:
            return item.coefficient
    return 1.0
