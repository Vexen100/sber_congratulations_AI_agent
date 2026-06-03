from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import Any, Mapping

from app.project_planner.schemas import ProjectPlannerInput

logger = logging.getLogger(__name__)

PLAYBOOK_RESOURCE_PACKAGE = "app.project_planner.resources"
PLAYBOOK_RESOURCE_NAME = "domain_playbooks_v1.json"
SUPPORTED_PROJECT_TYPES: tuple[str, ...] = ("it_service", "event", "general")
GENERAL_PROJECT_TYPE = "general"
HIGH_CONFIDENCE_THRESHOLD = 0.7
PROMPT_CONTEXT_TARGET_CHARS = 700
PROMPT_CONTEXT_HARD_LIMIT_CHARS = 1200


class DomainPlaybookError(ValueError):
    pass


@dataclass(frozen=True)
class PlaybookPhase:
    name: str
    milestones: tuple[str, ...]


@dataclass(frozen=True)
class PlaybookRole:
    title: str
    count: int
    competencies: tuple[str, ...]
    assignment_comment: str


@dataclass(frozen=True)
class PlaybookConceptPattern:
    name: str
    key_idea: str
    scenario_steps: tuple[str, ...]
    advantages: tuple[str, ...]
    disadvantages: tuple[str, ...]
    effort_level: str
    effort_factors: tuple[str, ...]
    differences: str


@dataclass(frozen=True)
class RaciDefaults:
    responsible: str
    accountable: str
    consulted: tuple[str, ...]
    informed: tuple[str, ...]


@dataclass(frozen=True)
class DomainPlaybook:
    project_type: str
    display_name: str
    prompt_context_summary: str
    strong_keywords: tuple[str, ...]
    support_keywords: tuple[str, ...]
    expected_keywords: tuple[str, ...]
    phases: tuple[PlaybookPhase, ...]
    roles: tuple[PlaybookRole, ...]
    raci_activities: tuple[str, ...]
    raci_defaults: RaciDefaults
    material_resources: tuple[str, ...]
    information_resources: tuple[str, ...]
    risks: tuple[str, ...]
    concept_patterns: tuple[PlaybookConceptPattern, ...]


@dataclass(frozen=True)
class ProjectTypeClassification:
    project_type: str
    confidence: float
    matched_keywords: tuple[str, ...]


def _clean_text(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise DomainPlaybookError(f"{field_name} must be a string")
    text = " ".join(value.strip().split())
    if not text:
        raise DomainPlaybookError(f"{field_name} must not be empty")
    return text


def _parse_string_list(value: Any, *, field_name: str, min_length: int = 1) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise DomainPlaybookError(f"{field_name} must be a list")
    parsed = tuple(
        _clean_text(item, field_name=f"{field_name}[{index}]") for index, item in enumerate(value)
    )
    if len(parsed) < min_length:
        raise DomainPlaybookError(f"{field_name} must contain at least {min_length} items")
    return parsed


def _parse_phase(value: Any, *, index: int) -> PlaybookPhase:
    if not isinstance(value, Mapping):
        raise DomainPlaybookError(f"phases[{index}] must be an object")
    return PlaybookPhase(
        name=_clean_text(value.get("name"), field_name=f"phases[{index}].name"),
        milestones=_parse_string_list(
            value.get("milestones"),
            field_name=f"phases[{index}].milestones",
            min_length=3,
        ),
    )


def _parse_role(value: Any, *, index: int) -> PlaybookRole:
    if not isinstance(value, Mapping):
        raise DomainPlaybookError(f"roles[{index}] must be an object")
    count = value.get("count")
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise DomainPlaybookError(f"roles[{index}].count must be a positive integer")
    return PlaybookRole(
        title=_clean_text(value.get("title"), field_name=f"roles[{index}].title"),
        count=count,
        competencies=_parse_string_list(
            value.get("competencies"),
            field_name=f"roles[{index}].competencies",
            min_length=1,
        ),
        assignment_comment=_clean_text(
            value.get("assignment_comment"),
            field_name=f"roles[{index}].assignment_comment",
        ),
    )


def _parse_concept(value: Any, *, index: int) -> PlaybookConceptPattern:
    if not isinstance(value, Mapping):
        raise DomainPlaybookError(f"concept_patterns[{index}] must be an object")
    return PlaybookConceptPattern(
        name=_clean_text(value.get("name"), field_name=f"concept_patterns[{index}].name"),
        key_idea=_clean_text(
            value.get("key_idea"),
            field_name=f"concept_patterns[{index}].key_idea",
        ),
        scenario_steps=_parse_string_list(
            value.get("scenario_steps"),
            field_name=f"concept_patterns[{index}].scenario_steps",
            min_length=3,
        ),
        advantages=_parse_string_list(
            value.get("advantages"),
            field_name=f"concept_patterns[{index}].advantages",
            min_length=1,
        ),
        disadvantages=_parse_string_list(
            value.get("disadvantages"),
            field_name=f"concept_patterns[{index}].disadvantages",
            min_length=1,
        ),
        effort_level=_clean_text(
            value.get("effort_level"),
            field_name=f"concept_patterns[{index}].effort_level",
        ),
        effort_factors=_parse_string_list(
            value.get("effort_factors"),
            field_name=f"concept_patterns[{index}].effort_factors",
            min_length=1,
        ),
        differences=_clean_text(
            value.get("differences"),
            field_name=f"concept_patterns[{index}].differences",
        ),
    )


def _parse_raci_defaults(value: Any, *, role_titles: set[str], playbook_type: str) -> RaciDefaults:
    if not isinstance(value, Mapping):
        raise DomainPlaybookError(f"playbook {playbook_type} raci_defaults must be an object")
    responsible = _clean_text(value.get("responsible"), field_name="raci_defaults.responsible")
    accountable = _clean_text(value.get("accountable"), field_name="raci_defaults.accountable")
    consulted = _parse_string_list(
        value.get("consulted"),
        field_name="raci_defaults.consulted",
        min_length=1,
    )
    informed = _parse_string_list(
        value.get("informed"),
        field_name="raci_defaults.informed",
        min_length=1,
    )
    referenced_titles = {responsible, accountable, *consulted, *informed}
    missing_titles = sorted(referenced_titles - role_titles)
    if missing_titles:
        raise DomainPlaybookError(
            f"playbook {playbook_type} raci_defaults references unknown roles: "
            f"{', '.join(missing_titles)}"
        )
    return RaciDefaults(
        responsible=responsible,
        accountable=accountable,
        consulted=consulted,
        informed=informed,
    )


def _parse_playbook(value: Any, *, index: int) -> DomainPlaybook:
    if not isinstance(value, Mapping):
        raise DomainPlaybookError(f"playbooks[{index}] must be an object")
    project_type = _clean_text(value.get("project_type"), field_name=f"playbooks[{index}].type")
    if project_type not in SUPPORTED_PROJECT_TYPES:
        raise DomainPlaybookError(f"unsupported playbook project_type: {project_type}")
    classification = value.get("classification")
    if not isinstance(classification, Mapping):
        raise DomainPlaybookError(f"playbooks[{index}].classification must be an object")

    summary = _clean_text(
        value.get("prompt_context_summary"),
        field_name=f"playbooks[{index}].prompt_context_summary",
    )
    if len(summary) > PROMPT_CONTEXT_HARD_LIMIT_CHARS:
        raise DomainPlaybookError("prompt_context_summary exceeds hard limit")

    phases = tuple(
        _parse_phase(item, index=phase_index)
        for phase_index, item in enumerate(value.get("phases") or [])
    )
    roles = tuple(
        _parse_role(item, index=role_index)
        for role_index, item in enumerate(value.get("roles") or [])
    )
    concepts = tuple(
        _parse_concept(item, index=concept_index)
        for concept_index, item in enumerate(value.get("concept_patterns") or [])
    )
    if len(phases) < 4:
        raise DomainPlaybookError(f"playbook {project_type} must have at least 4 phases")
    if len(roles) < 3:
        raise DomainPlaybookError(f"playbook {project_type} must have at least 3 roles")
    if len(concepts) != 3:
        raise DomainPlaybookError(f"playbook {project_type} must have exactly 3 concepts")
    role_titles = {role.title for role in roles}
    raci_defaults = _parse_raci_defaults(
        value.get("raci_defaults"),
        role_titles=role_titles,
        playbook_type=project_type,
    )

    return DomainPlaybook(
        project_type=project_type,
        display_name=_clean_text(
            value.get("display_name"),
            field_name=f"playbooks[{index}].display_name",
        ),
        prompt_context_summary=summary,
        strong_keywords=_parse_string_list(
            classification.get("strong_keywords"),
            field_name=f"playbooks[{index}].classification.strong_keywords",
            min_length=0,
        ),
        support_keywords=_parse_string_list(
            classification.get("support_keywords"),
            field_name=f"playbooks[{index}].classification.support_keywords",
            min_length=0,
        ),
        expected_keywords=_parse_string_list(
            value.get("expected_keywords"),
            field_name=f"playbooks[{index}].expected_keywords",
            min_length=0,
        ),
        phases=phases,
        roles=roles,
        raci_activities=_parse_string_list(
            value.get("raci_activities"),
            field_name=f"playbooks[{index}].raci_activities",
            min_length=1,
        ),
        raci_defaults=raci_defaults,
        material_resources=_parse_string_list(
            value.get("material_resources"),
            field_name=f"playbooks[{index}].material_resources",
            min_length=1,
        ),
        information_resources=_parse_string_list(
            value.get("information_resources"),
            field_name=f"playbooks[{index}].information_resources",
            min_length=1,
        ),
        risks=_parse_string_list(
            value.get("risks"),
            field_name=f"playbooks[{index}].risks",
            min_length=1,
        ),
        concept_patterns=concepts,
    )


def parse_domain_playbooks(data: Mapping[str, Any]) -> dict[str, DomainPlaybook]:
    version = _clean_text(data.get("version"), field_name="version")
    if version != "v1":
        raise DomainPlaybookError("unsupported domain playbook version")
    raw_playbooks = data.get("playbooks")
    if not isinstance(raw_playbooks, list):
        raise DomainPlaybookError("playbooks must be a list")
    playbooks = {
        playbook.project_type: playbook
        for playbook in (
            _parse_playbook(item, index=index) for index, item in enumerate(raw_playbooks)
        )
    }
    missing = set(SUPPORTED_PROJECT_TYPES) - set(playbooks)
    if missing:
        raise DomainPlaybookError(f"domain playbooks missing: {', '.join(sorted(missing))}")
    return playbooks


@lru_cache(maxsize=1)
def load_domain_playbooks() -> dict[str, DomainPlaybook]:
    raw_text = (
        resources.files(PLAYBOOK_RESOURCE_PACKAGE)
        .joinpath(PLAYBOOK_RESOURCE_NAME)
        .read_text(encoding="utf-8")
    )
    data = json.loads(raw_text)
    if not isinstance(data, Mapping):
        raise DomainPlaybookError("domain playbook root must be an object")
    return parse_domain_playbooks(data)


def _minimal_safe_general_playbook() -> DomainPlaybook:
    roles = (
        PlaybookRole(
            title="Руководитель проекта",
            count=1,
            competencies=("планирование", "коммуникации"),
            assignment_comment="Отвечает за общий результат и согласования.",
        ),
        PlaybookRole(
            title="Бизнес-заказчик",
            count=1,
            competencies=("приоритизация", "приёмка"),
            assignment_comment="Принимает ключевые решения и результат MVP.",
        ),
        PlaybookRole(
            title="Координатор проекта",
            count=1,
            competencies=("координация", "контроль задач"),
            assignment_comment="Поддерживает календарь, документы и коммуникации.",
        ),
    )
    return DomainPlaybook(
        project_type=GENERAL_PROJECT_TYPE,
        display_name="Универсальный проект",
        prompt_context_summary=(
            "Универсальный MVP: уточнить цель, роли, ресурсы, риски, дорожную карту, "
            "RACI и 3 концепции без доменных допущений."
        ),
        strong_keywords=(),
        support_keywords=(),
        expected_keywords=(),
        phases=(
            PlaybookPhase(
                name="Инициация",
                milestones=(
                    "Зафиксировать цель",
                    "Определить участников",
                    "Согласовать ограничения",
                ),
            ),
            PlaybookPhase(
                name="Проектирование",
                milestones=(
                    "Описать сценарий",
                    "Оценить ресурсы",
                    "Согласовать роли",
                ),
            ),
            PlaybookPhase(
                name="Подготовка",
                milestones=(
                    "Подготовить материалы",
                    "Проверить риски",
                    "Согласовать запуск",
                ),
            ),
            PlaybookPhase(
                name="Реализация и защита",
                milestones=(
                    "Провести работы",
                    "Собрать обратную связь",
                    "Защитить результат",
                ),
            ),
        ),
        roles=roles,
        raci_activities=("Уточнение целей", "Планирование", "Реализация", "Защита результата"),
        raci_defaults=RaciDefaults(
            responsible="Руководитель проекта",
            accountable="Бизнес-заказчик",
            consulted=("Координатор проекта",),
            informed=("Координатор проекта",),
        ),
        material_resources=("Рабочее пространство проекта", "Материалы для встреч"),
        information_resources=("Паспорт проекта", "Список стейкхолдеров"),
        risks=("Недостаток исходных данных может снизить точность оценок.",),
        concept_patterns=(
            PlaybookConceptPattern(
                name="Базовая управляемая концепция",
                key_idea="Реализовать инициативу через понятный MVP-план.",
                scenario_steps=("Уточнить цель.", "Подготовить ресурсы.", "Защитить результат."),
                advantages=("Быстрый старт", "Понятная управляемость"),
                disadvantages=("Ограниченная детализация",),
                effort_level="средняя",
                effort_factors=("типовая команда", "контроль сроков"),
                differences="Фокус на управляемой реализации.",
            ),
            PlaybookConceptPattern(
                name="Расширенная концепция",
                key_idea="Усилить MVP коммуникациями и вовлечением стейкхолдеров.",
                scenario_steps=(
                    "Собрать ожидания.",
                    "Расширить коммуникации.",
                    "Подготовить итоговые материалы.",
                ),
                advantages=("Больше охват", "Выше вовлечённость"),
                disadvantages=("Выше трудоёмкость",),
                effort_level="высокая",
                effort_factors=("коммуникации", "согласования"),
                differences="Отличается расширенным охватом.",
            ),
            PlaybookConceptPattern(
                name="Пилотная концепция",
                key_idea="Проверить MVP на ограниченном контуре перед масштабированием.",
                scenario_steps=(
                    "Выбрать пилот.",
                    "Проверить гипотезы.",
                    "Описать масштабирование.",
                ),
                advantages=("Ниже риск", "Проверка гипотез"),
                disadvantages=("Ограниченный масштаб",),
                effort_level="низкая",
                effort_factors=("пилот", "ограниченный контур"),
                differences="Отличается пилотной логикой.",
            ),
        ),
    )


@lru_cache(maxsize=1)
def load_domain_playbooks_safe() -> dict[str, DomainPlaybook]:
    try:
        return load_domain_playbooks()
    except (OSError, json.JSONDecodeError, DomainPlaybookError):
        logger.warning(
            "Domain playbook resource is unavailable or invalid; using safe general fallback.",
            exc_info=True,
        )
        playbook = _minimal_safe_general_playbook()
        return {GENERAL_PROJECT_TYPE: playbook}


def _normalized(value: str) -> str:
    return " ".join(value.strip().lower().replace("ё", "е").split())


def _keyword_variants(keyword: str) -> tuple[str, ...]:
    normalized = _normalized(keyword)
    variants = {normalized}
    if len(normalized) >= 6:
        for suffix in ("иями", "ями", "ами", "ией", "ия", "ии", "ие", "ой", "ая", "ые"):
            if normalized.endswith(suffix):
                variants.add(normalized[: -len(suffix)])
        last = normalized[-1]
        if last in "аяыиеую":
            variants.add(normalized[:-1])
    return tuple(item for item in variants if len(item) >= 3)


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[0-9a-zа-я]+", _normalized(text), flags=re.IGNORECASE))


def _is_short_single_word_keyword(keyword: str) -> bool:
    normalized = _normalized(keyword)
    return len(normalized) <= 3 and bool(re.fullmatch(r"[0-9a-zа-я]+", normalized))


def _keyword_present(text: str, keyword: str) -> bool:
    if _is_short_single_word_keyword(keyword):
        return _normalized(keyword) in _tokens(text)
    return any(variant in text for variant in _keyword_variants(keyword))


def contains_controlled_keyword(text: str, keyword: str) -> bool:
    return _keyword_present(_normalized(text), keyword)


def _payload_text(payload: ProjectPlannerInput) -> str:
    values = (
        payload.idea,
        payload.geography,
        payload.stakeholders,
        payload.current_resources,
        payload.technology_constraints,
        payload.project_accents,
    )
    return _normalized(" ".join(value or "" for value in values))


def _matches(text: str, keywords: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(keyword for keyword in keywords if _keyword_present(text, keyword))


def _score_playbook(playbook: DomainPlaybook, text: str) -> tuple[float, tuple[str, ...]]:
    strong = _matches(text, playbook.strong_keywords)
    support = tuple(
        keyword for keyword in _matches(text, playbook.support_keywords) if keyword not in strong
    )
    if playbook.project_type == "it_service":
        qualifies = len(strong) >= 2 or (
            bool({"внутренний сервис", "корпоративный портал"} & set(strong)) and support
        )
    elif playbook.project_type == "event":
        qualifies = bool(strong)
    else:
        qualifies = False
    if not qualifies:
        return 0.0, ()
    score = len(strong) * 2 + len(support)
    confidence = min(0.95, max(0.55, score / 7))
    return confidence, (*strong, *support)[:8]


def classify_project_type(payload: ProjectPlannerInput) -> ProjectTypeClassification:
    playbooks = load_domain_playbooks_safe()
    text = _payload_text(payload)
    candidates: list[ProjectTypeClassification] = []
    for project_type in ("it_service", "event"):
        if project_type not in playbooks:
            continue
        confidence, matched_keywords = _score_playbook(playbooks[project_type], text)
        if confidence > 0:
            candidates.append(
                ProjectTypeClassification(
                    project_type=project_type,
                    confidence=confidence,
                    matched_keywords=matched_keywords,
                )
            )
    if not candidates:
        return ProjectTypeClassification(GENERAL_PROJECT_TYPE, 0.0, ())

    candidates.sort(key=lambda item: (-item.confidence, item.project_type))
    best = candidates[0]
    if len(candidates) > 1 and abs(best.confidence - candidates[1].confidence) < 0.15:
        return ProjectTypeClassification(GENERAL_PROJECT_TYPE, 0.0, ())
    if best.confidence < 0.55:
        return ProjectTypeClassification(GENERAL_PROJECT_TYPE, 0.0, ())
    return best


def select_playbook(
    payload: ProjectPlannerInput,
) -> tuple[DomainPlaybook, ProjectTypeClassification]:
    playbooks = load_domain_playbooks_safe()
    classification = classify_project_type(payload)
    return playbooks[classification.project_type], classification


def build_playbook_prompt_context(payload: ProjectPlannerInput) -> str:
    playbook, classification = select_playbook(payload)
    summary = playbook.prompt_context_summary[:PROMPT_CONTEXT_HARD_LIMIT_CHARS]
    return (
        "Domain playbook context:\n"
        f"- project_type: {classification.project_type}\n"
        f"- confidence: {classification.confidence:.2f}\n"
        f"- summary: {summary}"
    )
