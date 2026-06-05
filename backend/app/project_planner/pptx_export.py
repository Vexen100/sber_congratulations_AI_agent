from __future__ import annotations

import datetime as dt
import re
from io import BytesIO
from typing import Iterable

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, PP_PARAGRAPH_ALIGNMENT
from pptx.util import Inches, Pt

from app.project_planner.schemas import ConceptOption, ProjectReport

PPTX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"

_COLOR_DARK = RGBColor(31, 52, 45)
_COLOR_GREEN = RGBColor(25, 135, 84)
_COLOR_LIGHT_GREEN = RGBColor(226, 245, 236)
_COLOR_LIGHT = RGBColor(248, 250, 249)
_COLOR_MUTED = RGBColor(96, 108, 104)
_COLOR_WHITE = RGBColor(255, 255, 255)

_SLIDE_W = Inches(13.333)
_SLIDE_H = Inches(7.5)
_MARGIN_X = Inches(0.55)


def safe_text(value: object, limit: int = 180) -> str:
    text = "" if value is None else str(value)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return "—"
    if limit > 3 and len(text) > limit:
        return text[: limit - 3].rstrip() + "..."
    return text


def format_money_rub(value: object) -> str:
    if value is None:
        return "—"
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return safe_text(value, 60)
    return f"{amount:,.0f}".replace(",", " ") + " руб."


def format_date(value: object) -> str:
    if value is None:
        return "—"
    if isinstance(value, dt.datetime):
        return value.date().strftime("%d.%m.%Y")
    if isinstance(value, dt.date):
        return value.strftime("%d.%m.%Y")
    return safe_text(value, 40)


def truncate_items(items: Iterable[object], max_count: int, *, limit: int = 120) -> list[str]:
    result: list[str] = []
    for item in items:
        text = safe_text(item, limit)
        if text != "—":
            result.append(text)
        if len(result) >= max_count:
            break
    return result


def _set_run_font(
    run, *, size: int = 16, bold: bool = False, color: RGBColor | None = None
) -> None:
    run.font.name = "Aptos"
    run.font.size = Pt(size)
    run.font.bold = bold
    if color is not None:
        run.font.color.rgb = color


def _set_paragraph_font(paragraph, *, size: int = 16, bold: bool = False) -> None:
    for run in paragraph.runs:
        _set_run_font(run, size=size, bold=bold, color=_COLOR_DARK)


def _add_title(slide, text: str, subtitle: str | None = None) -> None:
    title_box = slide.shapes.add_textbox(_MARGIN_X, Inches(0.25), Inches(12.2), Inches(0.55))
    title_frame = title_box.text_frame
    title_frame.clear()
    paragraph = title_frame.paragraphs[0]
    paragraph.text = safe_text(text, 90)
    paragraph.alignment = PP_ALIGN.LEFT
    _set_paragraph_font(paragraph, size=26, bold=True)

    line = slide.shapes.add_shape(1, _MARGIN_X, Inches(0.9), Inches(12.2), Inches(0.03))
    line.fill.solid()
    line.fill.fore_color.rgb = _COLOR_GREEN
    line.line.color.rgb = _COLOR_GREEN

    if subtitle:
        subtitle_box = slide.shapes.add_textbox(_MARGIN_X, Inches(0.98), Inches(12.2), Inches(0.35))
        subtitle_frame = subtitle_box.text_frame
        subtitle_frame.clear()
        paragraph = subtitle_frame.paragraphs[0]
        paragraph.text = safe_text(subtitle, 150)
        _set_paragraph_font(paragraph, size=11)
        paragraph.runs[0].font.color.rgb = _COLOR_MUTED


def _add_bullets(
    slide,
    items: Iterable[object],
    *,
    x=Inches(0.65),
    y=Inches(1.45),
    w=Inches(5.8),
    h=Inches(4.8),
    font_size: int = 15,
    max_items: int = 7,
    limit: int = 145,
) -> None:
    box = slide.shapes.add_textbox(x, y, w, h)
    frame = box.text_frame
    frame.clear()
    frame.word_wrap = True
    prepared = truncate_items(items, max_items, limit=limit)
    if not prepared:
        prepared = ["Данные не указаны."]
    for index, item in enumerate(prepared):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.text = item
        paragraph.level = 0
        paragraph.font.name = "Aptos"
        paragraph.font.size = Pt(font_size)
        paragraph.font.color.rgb = _COLOR_DARK
        paragraph.space_after = Pt(4)


def _style_cell(cell, text: object, *, bold: bool = False, font_size: int = 9) -> None:
    cell.text = safe_text(text, 110)
    cell.margin_left = Inches(0.06)
    cell.margin_right = Inches(0.06)
    cell.margin_top = Inches(0.04)
    cell.margin_bottom = Inches(0.04)
    for paragraph in cell.text_frame.paragraphs:
        paragraph.alignment = PP_PARAGRAPH_ALIGNMENT.LEFT
        paragraph.font.name = "Aptos"
        paragraph.font.size = Pt(font_size)
        paragraph.font.bold = bold
        paragraph.font.color.rgb = _COLOR_DARK


def _add_table(
    slide,
    headers: list[str],
    rows: list[list[object]],
    *,
    x=Inches(0.6),
    y=Inches(1.35),
    w=Inches(12.1),
    h=Inches(5.35),
    font_size: int = 9,
) -> None:
    visible_rows = rows or [["—" for _ in headers]]
    shape = slide.shapes.add_table(len(visible_rows) + 1, len(headers), x, y, w, h)
    table = shape.table
    for index, header in enumerate(headers):
        cell = table.cell(0, index)
        cell.fill.solid()
        cell.fill.fore_color.rgb = _COLOR_LIGHT_GREEN
        _style_cell(cell, header, bold=True, font_size=font_size)
    for row_index, row in enumerate(visible_rows, start=1):
        for col_index, value in enumerate(row[: len(headers)]):
            cell = table.cell(row_index, col_index)
            cell.fill.solid()
            cell.fill.fore_color.rgb = _COLOR_WHITE if row_index % 2 else _COLOR_LIGHT
            _style_cell(cell, value, font_size=font_size)


def _new_slide(prs: Presentation, title: str, subtitle: str | None = None):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = _COLOR_WHITE
    _add_title(slide, title, subtitle)
    return slide


def _find_recommended_concept(report: ProjectReport) -> ConceptOption | None:
    target = safe_text(report.recommended_concept.concept_name, 120).lower()
    for concept in report.concepts:
        if safe_text(concept.name, 120).lower() == target:
            return concept
    return report.concepts[0] if report.concepts else None


def _slide_title(prs: Presentation, report: ProjectReport) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = _COLOR_LIGHT

    title = slide.shapes.add_textbox(Inches(0.7), Inches(0.85), Inches(12), Inches(1.2))
    title_frame = title.text_frame
    title_frame.clear()
    paragraph = title_frame.paragraphs[0]
    paragraph.text = safe_text(report.passport.title, 95)
    _set_paragraph_font(paragraph, size=30, bold=True)

    bullets = [
        f"География: {safe_text(report.source_input.geography, 80)}",
        f"Дедлайн: {format_date(report.source_input.deadline)}",
        f"Финансовая оценка: {format_money_rub(report.resources.financial_total)}",
        f"Цель: {safe_text(report.passport.goal, 155)}",
    ]
    _add_bullets(
        slide, bullets, x=Inches(0.85), y=Inches(2.35), w=Inches(11.7), h=Inches(3.0), font_size=17
    )

    footer = slide.shapes.add_textbox(Inches(0.85), Inches(6.55), Inches(11.7), Inches(0.4))
    frame = footer.text_frame
    frame.clear()
    frame.paragraphs[0].text = "Project Planner: презентация для защиты проекта"
    _set_paragraph_font(frame.paragraphs[0], size=12)
    frame.paragraphs[0].runs[0].font.color.rgb = _COLOR_MUTED


def _slide_passport(prs: Presentation, report: ProjectReport) -> None:
    slide = _new_slide(prs, "Паспорт проекта")
    bullets = [
        f"Цель: {safe_text(report.passport.goal, 150)}",
        f"Актуальность: {safe_text(report.passport.relevance_for_ural_bank, 150)}",
        "Ожидаемый результат: " + safe_text("; ".join(report.passport.success_criteria[:3]), 165),
        "Ключевые задачи: " + safe_text("; ".join(report.passport.tasks[:3]), 165),
        "Ограничения: " + safe_text(report.source_input.technology_constraints, 130),
        "Допущения: "
        + safe_text("; ".join((report.assumptions or report.passport.assumptions)[:3]), 165),
    ]
    _add_bullets(slide, bullets, w=Inches(12.0), h=Inches(5.3), font_size=15)


def _slide_recommended(prs: Presentation, report: ProjectReport) -> None:
    concept = _find_recommended_concept(report)
    title = safe_text(report.recommended_concept.concept_name, 85)
    slide = _new_slide(prs, "Рекомендуемая концепция", title)
    bullets = [f"Обоснование: {safe_text(report.recommended_concept.rationale, 170)}"]
    if concept is not None:
        bullets.append(f"Идея: {safe_text(concept.key_idea, 160)}")
        bullets.extend(
            f"Преимущество: {item}" for item in truncate_items(concept.advantages, 3, limit=120)
        )
    else:
        bullets.append("Концепция требует уточнения в полном отчёте.")
    _add_bullets(slide, bullets, w=Inches(12.0), h=Inches(5.2), font_size=16)


def _slide_concepts(prs: Presentation, report: ProjectReport) -> None:
    slide = _new_slide(prs, "Сравнение концепций")
    rows = [
        [
            concept.name,
            concept.effort_level,
            format_money_rub(concept.estimated_cost),
            concept.advantages[0] if concept.advantages else "—",
            concept.disadvantages[0] if concept.disadvantages else "—",
        ]
        for concept in report.concepts[:5]
    ]
    _add_table(
        slide,
        ["Концепция", "Сложность", "Оценка", "Плюс", "Риск/минус"],
        rows,
        font_size=8,
    )


def _slide_roadmap(prs: Presentation, report: ProjectReport) -> None:
    slide = _new_slide(prs, "Дорожная карта")
    rows = [
        [
            phase.name,
            format_date(phase.start_date),
            format_date(phase.end_date),
            "; ".join(item.title for item in phase.milestones[:3]),
        ]
        for phase in report.roadmap[:7]
    ]
    _add_table(slide, ["Фаза", "Старт", "Финиш", "Контрольные точки"], rows, font_size=8)


def _budget_caveat(report: ProjectReport) -> str:
    first_comment = next(
        (
            item.comment
            for item in report.resources.financial_items
            if safe_text(item.comment) != "—"
        ),
        "",
    )
    if first_comment:
        return "Источник оценки: " + safe_text(first_comment, 150)
    return "Финансовая оценка предварительная и требует экспертной проверки."


def _slide_resources(prs: Presentation, report: ProjectReport) -> None:
    slide = _new_slide(prs, "Ресурсы и бюджет")
    financial_items = [
        f"{item.category}: {format_money_rub(item.amount)}"
        for item in report.resources.financial_items[:5]
    ]
    left = [f"Итого: {format_money_rub(report.resources.financial_total)}", *financial_items]
    _add_bullets(
        slide, left, x=Inches(0.65), y=Inches(1.35), w=Inches(5.9), h=Inches(3.9), font_size=14
    )

    right = [
        "Материальные ресурсы: "
        + safe_text(
            "; ".join(truncate_items(report.resources.material_resources, 4, limit=70)), 210
        ),
        "Информационные ресурсы: "
        + safe_text(
            "; ".join(truncate_items(report.resources.information_resources, 4, limit=70)), 210
        ),
        _budget_caveat(report),
    ]
    _add_bullets(
        slide, right, x=Inches(6.75), y=Inches(1.35), w=Inches(5.85), h=Inches(3.9), font_size=14
    )


def _slide_team_raci(prs: Presentation, report: ProjectReport) -> None:
    slide = _new_slide(prs, "Команда и RACI")
    team = [
        f"{role.title}: {role.count} чел.; {safe_text(', '.join(role.competencies[:2]), 80)}"
        for role in report.team[:5]
    ]
    _add_bullets(
        slide,
        team,
        x=Inches(0.65),
        y=Inches(1.35),
        w=Inches(5.6),
        h=Inches(5.1),
        font_size=13,
        max_items=5,
    )

    rows = [
        [
            item.activity,
            item.responsible,
            item.accountable,
            ", ".join(item.consulted[:2]),
            ", ".join(item.informed[:2]),
        ]
        for item in report.raci[:4]
    ]
    _add_table(
        slide,
        ["Активность", "R", "A", "C", "I"],
        rows,
        x=Inches(6.35),
        y=Inches(1.35),
        w=Inches(6.25),
        h=Inches(5.1),
        font_size=7,
    )


def export_project_report_pptx(report: ProjectReport) -> bytes:
    prs = Presentation()
    prs.slide_width = _SLIDE_W
    prs.slide_height = _SLIDE_H
    prs.core_properties.author = "Project Planner"
    prs.core_properties.title = safe_text(report.passport.title, 120)
    prs.core_properties.subject = "Project Planner PPTX export"
    fixed_timestamp = dt.datetime(2026, 1, 1, 0, 0, 0)
    prs.core_properties.created = fixed_timestamp
    prs.core_properties.modified = fixed_timestamp

    _slide_title(prs, report)
    _slide_passport(prs, report)
    _slide_recommended(prs, report)
    _slide_concepts(prs, report)
    _slide_roadmap(prs, report)
    _slide_resources(prs, report)
    if report.team or report.raci:
        _slide_team_raci(prs, report)

    output = BytesIO()
    prs.save(output)
    return output.getvalue()
