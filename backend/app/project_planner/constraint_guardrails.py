from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from app.project_planner.schemas import (
    ConceptOption,
    ProjectPlannerInput,
    ProjectReport,
)

CONCEPT_CONSTRAINT_CORRECTION_WARNING = (
    "Одна или несколько концепций были скорректированы, так как противоречили "
    "жёстким ограничениям пользователя."
)
CONCEPT_CONSTRAINT_VALIDATION_WARNING = (
    "В отчёте есть концепция, противоречащая жёстким ограничениям пользователя; "
    "требуется проверка."
)

_VALID_EFFORT_LEVELS = {"низкая", "средняя", "высокая", "очень высокая"}
_CONSTRAINT_FIELDS = (
    "idea",
    "stakeholders",
    "current_resources",
    "technology_constraints",
    "project_accents",
)
_NO_EXTERNAL_SAAS_PATTERNS = (
    r"\b(?:не\s+использовать|не\s+применять|без|запрещен\w*|исключить)" r"\s+(?:\w+\s+){0,3}saas\b",
    r"\b(?:не\s+использовать|не\s+применять|без|запрещен\w*|исключить)"
    r"\s+(?:\w+\s+){0,3}внешн\w+\s+(?:сервис\w+|платформ\w+)\b",
)
_INTERNAL_CONTOUR_PATTERNS = (
    r"\bтолько\s+(?:через\s+)?внутренн\w+\s+контур\w*\b",
    r"\bинтеграц\w+\s+только\s+через\s+внутренн\w+\s+контур\w*\b",
)
_INTERNAL_CHANNELS_PATTERNS = (
    r"\bтолько\s+(?:согласованн\w+\s+)?внутренн\w+\s+канал\w+\b",
    r"\bбез\s+внешн\w+\s+реклам\w+\b",
    r"\bбез\s+публичн\w+\s+канал\w+\b",
)
_EXTERNAL_PLATFORM_SIGNALS = (
    r"\bиспользовани\w*\s+внешн\w+(?:\s+\w+){0,3}\s+saas\b",
    r"\bиспользовать\s+внешн\w+(?:\s+\w+){0,3}\s+saas\b",
    r"\bвнешн\w+\s+(?:решени\w+\s+)?saas\b",
    r"\bвнешн\w+\s+saas[-\s]+решени\w+\b",
    r"\bвнешн\w+\s+saas[-\s]+платформ\w+\b",
    r"\bвнешн\w+\s+платформ\w+\b",
    r"\bвнешн\w+\s+сервис\w+\b",
    r"\bоблачн\w+\s+сервис\w+\b",
    r"\bthird[- ]party\b",
    r"\bexternal\s+saas\b",
)
_EXTERNAL_CHANNEL_SIGNALS = (
    r"\bвнешн\w+\s+реклам\w+\b",
    r"\bпубличн\w+\s+соцсет\w+\b",
    r"\bпубличн\w+\s+социальн\w+\s+сет\w+\b",
    r"\bнаружн\w+\s+реклам\w+\b",
    r"\bпубличн\w+\s+рекламн\w+\s+кампан\w+\b",
)
_NEGATION_MARKERS = (
    "без",
    "не использовать",
    "не использует",
    "не применять",
    "не применяет",
    "не предполагает",
    "не требует",
    "отказ от",
    "исключает",
    "исключить",
)


@dataclass(frozen=True)
class ProjectConstraintProfile:
    no_external_saas: bool = False
    internal_contour_only: bool = False
    internal_channels_only: bool = False
    matched_constraints: tuple[str, ...] = ()

    @property
    def has_constraints(self) -> bool:
        return bool(
            self.no_external_saas or self.internal_contour_only or self.internal_channels_only
        )


def _normalize_text(value: object) -> str:
    return " ".join(str(value or "").strip().lower().replace("ё", "е").split())


def _payload_text(payload: ProjectPlannerInput) -> str:
    return "\n".join(
        _normalize_text(getattr(payload, field_name))
        for field_name in _CONSTRAINT_FIELDS
        if getattr(payload, field_name)
    )


def _matches_any(text: str, patterns: Iterable[str]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def extract_project_constraints(payload: ProjectPlannerInput) -> ProjectConstraintProfile:
    text = _payload_text(payload)
    if not text:
        return ProjectConstraintProfile()

    no_external_saas = _matches_any(text, _NO_EXTERNAL_SAAS_PATTERNS)
    internal_contour_only = _matches_any(text, _INTERNAL_CONTOUR_PATTERNS)
    internal_channels_only = _matches_any(text, _INTERNAL_CHANNELS_PATTERNS)

    matched_constraints: list[str] = []
    if no_external_saas:
        matched_constraints.append("no_external_saas")
    if internal_contour_only:
        matched_constraints.append("internal_contour_only")
    if internal_channels_only:
        matched_constraints.append("internal_channels_only")

    return ProjectConstraintProfile(
        no_external_saas=no_external_saas,
        internal_contour_only=internal_contour_only,
        internal_channels_only=internal_channels_only,
        matched_constraints=tuple(matched_constraints),
    )


def build_constraint_prompt_context(payload: ProjectPlannerInput) -> str:
    profile = extract_project_constraints(payload)
    if not profile.has_constraints:
        return ""

    rules: list[str] = []
    if profile.no_external_saas or profile.internal_contour_only:
        if profile.internal_contour_only:
            rules.append(
                "use internal contour only; do not propose external SaaS, external "
                "services or external platforms."
            )
        else:
            rules.append("do not propose external SaaS, external services or external platforms.")
    if profile.internal_channels_only:
        rules.append(
            "use approved internal channels only; do not propose public external advertising."
        )
    return "Hard constraints context:\n- " + "\n- ".join(rules)


def _concept_text(concept: ConceptOption) -> str:
    chunks = [
        concept.name,
        concept.key_idea,
        *concept.scenario_steps,
        *concept.advantages,
        *concept.disadvantages,
        *concept.effort_factors,
        concept.differences,
    ]
    return _normalize_text("\n".join(chunks))


def _is_negated_match(text: str, start: int) -> bool:
    before = text[max(0, start - 70) : start]
    fragment = re.split(r"[.!?;\n]", before)[-1]
    return any(marker in fragment for marker in _NEGATION_MARKERS)


def _contains_forbidden_signal(text: str, patterns: Iterable[str]) -> bool:
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            if not _is_negated_match(text, match.start()):
                return True
    return False


def _concept_violation_kinds(
    concept: ConceptOption,
    profile: ProjectConstraintProfile,
) -> set[str]:
    if not profile.has_constraints:
        return set()

    text = _concept_text(concept)
    violation_kinds: set[str] = set()
    if (profile.no_external_saas or profile.internal_contour_only) and _contains_forbidden_signal(
        text, _EXTERNAL_PLATFORM_SIGNALS
    ):
        violation_kinds.add("external_platform")
    if profile.internal_channels_only and _contains_forbidden_signal(
        text,
        _EXTERNAL_CHANNEL_SIGNALS,
    ):
        violation_kinds.add("external_channels")
    return violation_kinds


def concept_violates_constraints(
    concept: ConceptOption,
    profile: ProjectConstraintProfile,
) -> bool:
    return bool(_concept_violation_kinds(concept, profile))


def _safe_effort_level(concept: ConceptOption) -> str:
    return concept.effort_level if concept.effort_level in _VALID_EFFORT_LEVELS else "средняя"


def _external_platform_replacement(concept: ConceptOption) -> ConceptOption:
    return ConceptOption(
        name="Внутренний MVP-прототип в корпоративном контуре",
        key_idea=(
            "Проверить сценарий регистрации инициатив на корпоративном портале и во "
            "внутреннем контуре."
        ),
        scenario_steps=[
            "Выбрать минимальный пользовательский сценарий.",
            "Настроить прототип на корпоративном портале.",
            "Проверить маршрутизацию и роли доступа.",
            "Собрать обратную связь и требования к масштабированию.",
        ],
        advantages=[
            "Соблюдает ограничение по внутреннему контуру.",
            "Снижает риски ИБ и согласований.",
        ],
        disadvantages=[
            "Потребуется внутренняя настройка и поддержка.",
            "Меньше готовых функций по сравнению с коробочными решениями.",
        ],
        estimated_cost=concept.estimated_cost,
        effort_level=_safe_effort_level(concept),
        effort_factors=["внутренний контур", "ИБ", "корпоративный портал"],
        differences=("Отличается проверкой сценария внутри разрешённого корпоративного контура."),
    )


def _internal_channels_replacement(concept: ConceptOption) -> ConceptOption:
    return ConceptOption(
        name="Внутренняя коммуникационная концепция",
        key_idea="Провести продвижение через согласованные внутренние каналы.",
        scenario_steps=[
            "Согласовать перечень внутренних каналов.",
            "Подготовить сообщения для сотрудников.",
            "Запустить коммуникации через разрешённые каналы.",
            "Собрать обратную связь и метрики вовлечения.",
        ],
        advantages=[
            "Соблюдает ограничение по внутренним каналам.",
            "Снижает риски несогласованных коммуникаций.",
        ],
        disadvantages=[
            "Охват зависит от эффективности внутренних каналов.",
            "Потребуется аккуратная настройка сообщений.",
        ],
        estimated_cost=concept.estimated_cost,
        effort_level=_safe_effort_level(concept),
        effort_factors=["внутренние каналы", "согласование коммуникаций", "метрики вовлечения"],
        differences="Отличается фокусом на разрешённых внутренних коммуникациях.",
    )


def _replacement_for_concept(
    concept: ConceptOption,
    violation_kinds: set[str],
) -> ConceptOption:
    if "external_platform" in violation_kinds:
        return _external_platform_replacement(concept)
    return _internal_channels_replacement(concept)


def _unique_concept_name(base_name: str, used_names: set[str]) -> str:
    if _normalize_text(base_name) not in used_names:
        used_names.add(_normalize_text(base_name))
        return base_name
    index = 2
    while True:
        candidate = f"{base_name} — вариант {index}"
        normalized = _normalize_text(candidate)
        if normalized not in used_names:
            used_names.add(normalized)
            return candidate
        index += 1


def _append_warning_once(report: ProjectReport, warning: str) -> None:
    if warning not in report.warnings:
        report.warnings.append(warning)


def _first_compliant_concept(
    concepts: list[ConceptOption],
    profile: ProjectConstraintProfile,
) -> ConceptOption | None:
    return next(
        (concept for concept in concepts if not concept_violates_constraints(concept, profile)),
        None,
    )


def apply_concept_constraint_guardrails(
    report: ProjectReport,
    payload: ProjectPlannerInput,
) -> ProjectReport:
    profile = extract_project_constraints(payload)
    if not profile.has_constraints or not report.concepts:
        return report

    processed = report.model_copy(deep=True)
    violation_by_index = {
        index: _concept_violation_kinds(concept, profile)
        for index, concept in enumerate(processed.concepts)
    }
    violation_by_index = {index: kinds for index, kinds in violation_by_index.items() if kinds}
    if not violation_by_index:
        return processed

    used_names = {
        _normalize_text(concept.name)
        for index, concept in enumerate(processed.concepts)
        if index not in violation_by_index
    }
    replaced_names: dict[str, str] = {}
    new_concepts: list[ConceptOption] = []
    for index, concept in enumerate(processed.concepts):
        violation_kinds = violation_by_index.get(index)
        if not violation_kinds:
            new_concepts.append(concept)
            continue
        replacement = _replacement_for_concept(concept, violation_kinds)
        replacement = replacement.model_copy(
            update={"name": _unique_concept_name(replacement.name, used_names)}
        )
        replaced_names[_normalize_text(concept.name)] = replacement.name
        new_concepts.append(replacement)

    processed.concepts = new_concepts
    recommended_name = _normalize_text(processed.recommended_concept.concept_name)
    target_name = replaced_names.get(recommended_name)
    if target_name is None and not any(
        _normalize_text(concept.name) == recommended_name for concept in processed.concepts
    ):
        first_compliant = _first_compliant_concept(processed.concepts, profile)
        target_name = first_compliant.name if first_compliant is not None else None
    if target_name:
        processed.recommended_concept = processed.recommended_concept.model_copy(
            update={
                "concept_name": target_name,
                "rationale": (
                    "Рекомендация обновлена: выбран вариант, соблюдающий жёсткие "
                    "ограничения пользователя."
                ),
            }
        )

    _append_warning_once(processed, CONCEPT_CONSTRAINT_CORRECTION_WARNING)
    return processed


def validate_concept_constraints(
    report: ProjectReport,
    payload: ProjectPlannerInput,
) -> list[str]:
    profile = extract_project_constraints(payload)
    if not profile.has_constraints:
        return []
    if any(concept_violates_constraints(concept, profile) for concept in report.concepts):
        return [CONCEPT_CONSTRAINT_VALIDATION_WARNING]
    return []
