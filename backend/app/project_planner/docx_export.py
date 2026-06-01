from __future__ import annotations

import html
import logging
import zipfile
from pathlib import Path

from app.core.config import settings
from app.project_planner.schemas import ProjectReport

logger = logging.getLogger(__name__)


def _safe_filename(value: str) -> str:
    clean = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value)
    return clean.strip("_")[:80] or "project_report"


def _paragraph_xml(text: str) -> str:
    return f"<w:p><w:r><w:t>{html.escape(text)}</w:t></w:r></w:p>"


def _write_minimal_docx(report: ProjectReport, path: Path) -> None:
    paragraphs = [
        "Проектный отчёт",
        report.passport.title,
        "Исходные данные",
        f"Идея: {report.source_input.idea}",
        f"Дедлайн: {report.source_input.deadline or 'не указан'}",
        f"Бюджет: {report.source_input.budget or 'не указан'}",
        f"География: {report.source_input.geography or 'не указана'}",
        f"Акценты: {report.source_input.project_accents or 'не указаны'}",
        "Предупреждения",
        *report.warnings,
        "Допущения",
        *report.assumptions,
        "Паспорт проекта",
        report.passport.goal,
        "Дорожная карта",
        *[
            f"{phase.name}: {phase.start_date.isoformat()} - {phase.end_date.isoformat()}"
            for phase in report.roadmap
        ],
        "Концепции",
        *[f"{concept.name}: {concept.key_idea}" for concept in report.concepts],
        "Рекомендованная концепция",
        f"{report.recommended_concept.concept_name}: {report.recommended_concept.rationale}",
    ]
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>"
        + "".join(_paragraph_xml(item) for item in paragraphs)
        + '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/></w:sectPr></w:body></w:document>'
    )
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as docx:
        docx.writestr(
            "[Content_Types].xml",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Default Extension="xml" ContentType="application/xml"/>'
                '<Override PartName="/word/document.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                "</Types>"
            ),
        )
        docx.writestr(
            "_rels/.rels",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
                'Target="word/document.xml"/></Relationships>'
            ),
        )
        docx.writestr("word/document.xml", document_xml)


def _add_bullets(document, title: str, items: list[str]) -> None:
    document.add_heading(title, level=2)
    for item in items:
        document.add_paragraph(item, style="List Bullet")


def export_project_report_docx(report: ProjectReport, *, run_id: int) -> Path:
    out_dir = Path(settings.project_planner_docx_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = f"project_planner_run_{run_id}_{_safe_filename(report.passport.title)}.docx"
    path = out_dir / filename

    try:
        from docx import Document

        document = Document()
        document.add_heading("Проектный отчёт", level=0)
        document.add_paragraph(report.passport.title)

        document.add_heading("Исходные данные", level=1)
        source_rows = [
            ("Идея", report.source_input.idea),
            ("Дедлайн", str(report.source_input.deadline or "не указан")),
            ("Бюджет", str(report.source_input.budget or "не указан")),
            ("География", report.source_input.geography or "не указана"),
            ("Стейкхолдеры", report.source_input.stakeholders or "не указаны"),
            ("Текущие ресурсы", report.source_input.current_resources or "не указаны"),
            (
                "Технологические ограничения",
                report.source_input.technology_constraints or "не указаны",
            ),
            ("Акценты проекта", report.source_input.project_accents or "не указаны"),
        ]
        table = document.add_table(rows=1, cols=2)
        table.rows[0].cells[0].text = "Поле"
        table.rows[0].cells[1].text = "Значение"
        for key, value in source_rows:
            row = table.add_row().cells
            row[0].text = key
            row[1].text = value

        _add_bullets(document, "Предупреждения", report.warnings)
        _add_bullets(document, "Допущения", report.assumptions)

        document.add_heading("Паспорт проекта", level=1)
        document.add_paragraph(report.passport.goal)
        _add_bullets(document, "Задачи", report.passport.tasks)
        _add_bullets(document, "Критерии успеха", report.passport.success_criteria)
        document.add_paragraph(report.passport.relevance_for_ural_bank)

        document.add_heading("Дорожная карта", level=1)
        roadmap_table = document.add_table(rows=1, cols=4)
        for cell, title in zip(roadmap_table.rows[0].cells, ("Фаза", "Старт", "Финиш", "Контрольные точки"), strict=True):
            cell.text = title
        for phase in report.roadmap:
            row = roadmap_table.add_row().cells
            row[0].text = phase.name
            row[1].text = phase.start_date.isoformat()
            row[2].text = phase.end_date.isoformat()
            row[3].text = "; ".join(item.title for item in phase.milestones)

        document.add_heading("Gantt-like представление", level=1)
        for row in report.gantt:
            document.add_paragraph(f"{row.phase}: {row.period} | {row.timeline}")

        document.add_heading("Ресурсы", level=1)
        financial_table = document.add_table(rows=1, cols=3)
        for cell, title in zip(financial_table.rows[0].cells, ("Статья", "Сумма", "Комментарий"), strict=True):
            cell.text = title
        for item in report.resources.financial_items:
            row = financial_table.add_row().cells
            row[0].text = item.category
            row[1].text = f"{item.amount:,.0f}".replace(",", " ")
            row[2].text = item.comment
        document.add_paragraph(f"Итого: {report.resources.financial_total:,.0f}".replace(",", " "))
        _add_bullets(document, "Материально-технические ресурсы", report.resources.material_resources)
        _add_bullets(document, "Информационные ресурсы", report.resources.information_resources)

        document.add_heading("Команда проекта", level=1)
        for role in report.team:
            document.add_paragraph(
                f"{role.title} ({role.count} чел.): {', '.join(role.competencies)}. "
                f"{role.assignment_comment}"
            )

        document.add_heading("RACI", level=1)
        for item in report.raci:
            document.add_paragraph(
                f"{item.activity}: R={item.responsible}; A={item.accountable}; "
                f"C={', '.join(item.consulted)}; I={', '.join(item.informed)}"
            )

        document.add_heading("Три концепции", level=1)
        for concept in report.concepts:
            document.add_heading(concept.name, level=2)
            document.add_paragraph(concept.key_idea)
            _add_bullets(document, "Сценарий", concept.scenario_steps)
            _add_bullets(document, "Преимущества", concept.advantages)
            _add_bullets(document, "Недостатки", concept.disadvantages)
            document.add_paragraph(
                f"Оценка стоимости: {concept.estimated_cost:,.0f}; "
                f"трудоёмкость: {concept.effort_level}. {concept.differences}"
            )

        document.add_heading("Рекомендованная концепция", level=1)
        document.add_paragraph(report.recommended_concept.concept_name)
        document.add_paragraph(report.recommended_concept.rationale)
        _add_bullets(document, "Риски выбранной концепции", report.recommended_concept.risks)

        if report.presentation_outline:
            document.add_heading("Outline презентации", level=1)
            for slide in report.presentation_outline:
                _add_bullets(document, slide.title, slide.bullets)
        if report.defense_script:
            document.add_heading("Сценарий защиты", level=1)
            document.add_paragraph(report.defense_script)

        document.save(path)
    except Exception:
        logger.warning(
            "Failed to export Project Planner DOCX with python-docx; writing minimal fallback.",
            exc_info=True,
        )
        _write_minimal_docx(report, path)
    return path
