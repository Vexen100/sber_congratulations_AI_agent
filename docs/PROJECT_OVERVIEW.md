# Project Overview — Sber Congratulations AI Agent

Краткий архитектурный обзор проекта для быстрого входа в репозиторий.

## Назначение

Система автоматизирует подготовку и доставку персонализированных поздравлений:
событие -> данные клиента и компании -> генерация текста и иллюстрации -> доставка -> feedback и audit.

## Ключевые возможности

- Обнаружение событий: дни рождения, календарные и профессиональные праздники, ручные поводы.
- Enrichment профилей клиентов через CSV, локальный demo-registry и `DaData`.
- Генерация текста через `GigaChat` или template fallback.
- Генерация открыток через `GigaChat` или локальный `Pillow` fallback.
- Доставка через file outbox или SMTP с HTML-письмом.
- Операторский контроль: feedback по поздравлениям, audit запусков (`AgentRun`), метрики на dashboard.
- Project Planner: отдельный UI-контур для подготовки структурированного проектного отчёта, preview/history, DOCX export, on-demand PPTX export и Reference Packs в mock/offline или GigaChat-режиме.

## Архитектура

```text
Sources -> Enrichment -> Events -> Agent -> Delivery -> Feedback/Audit

CSV / demo seed / DaData
        -> клиентский профиль и company context
        -> Event detection / manual events
        -> text + image generation
        -> SMTP or file outbox
        -> dashboard, runs, feedback

Project Planner input
        -> optional Reference Packs prompt context
        -> clarifications / assumptions
        -> LLM or mock report generation
        -> validation, guardrails, fallback
        -> preview, run history, DOCX, on-demand PPTX
```

## Карта кода

| Модуль | Назначение |
|--------|------------|
| `backend/app/main.py` | Точка входа FastAPI |
| `backend/app/web/` | Веб-интерфейс и operator flow |
| `backend/app/api/` | REST API endpoints |
| `backend/app/db/` | Модели данных и инициализация БД |
| `backend/app/agent/` | Оркестратор, prompt-building, text/image generation |
| `backend/app/project_planner/` | Project Planner API/service/schema, генерация отчёта, DOCX/PPTX export, Reference Packs, guardrails |
| `backend/app/llm/` | Общий LLM-provider слой, включая GigaChat provider для Project Planner |
| `backend/app/services/` | Delivery, enrichment, holidays, manual events, feedback |
| `frontend/src/pages/ProjectPlannerPage.tsx` | React-страница Project Planner |
| `scripts/project_planner_reference_pack.py` | Локальный CLI validate/install/list для curated Reference Packs |

## Основные режимы конфигурации

Настройка идёт через `backend/.env`.

| Переменная | Значения | Назначение |
|------------|----------|------------|
| `LLM_MODE` | `template`, `gigachat`, `openai` | Генерация текста |
| `IMAGE_MODE` | `pillow`, `gigachat` | Генерация открыток |
| `SEND_MODE` | `file`, `smtp` | Канал доставки |
| `SCHEDULER_MODE` | `off`, `inprocess`, `worker` | Где запускается scheduler автономного режима |
| `COMPANY_ENRICHMENT_PROVIDER` | `demo`, `dadata`, `hybrid` | Источник enrichment |
| `VECTOR_FEEDBACK_ENABLED` | `true`, `false` | Опциональный few-shot по принятым отзывам (см. `docs/DECISIONS.md`, §13) |
| `PROJECT_PLANNER_USE_MOCK_LLM` | `true`, `false` | Project Planner mock/offline режим или GigaChat provider с fallback |

## Project Planner

Project Planner не переносит существующего агента поздравлений на новый LLM provider. Это отдельный модуль с собственными схемами, run history и exports. В локальном режиме `PROJECT_PLANNER_USE_MOCK_LLM=true` он работает без сети и credentials.

При включённом GigaChat Project Planner валидирует JSON-ответ по строгой схеме, нормализует частые структурные ошибки (`effort_level`, RACI scalar fields и другие JSON-shape cases), применяет guardrails к hard constraints, budget consistency, roadmap deadline/start/horizon, milestone density и уходит в fallback generator, если ответ небезопасно восстановить. Validators добавляют короткие warnings без technical traceback.

DOCX export отдаёт полный отчёт. PPTX export строит краткую executive pitch-презентацию on-demand из сохранённого `ProjectReport`; export не создаёт новый run и не вызывает GigaChat. PDF export не реализован.

Reference Packs — curated JSON packs, которые выбираются по region/keywords и добавляются только в prompt context. В v1 они не мутируют `ProjectReport`, не меняют budget totals, roadmap, concepts, resources или warnings. UI поддерживает JSON upload/validation/install/replace/template/selection preview, CLI — validate/install/list. Установленные packs живут в `backend/data/project_planner/reference_packs`; real/customer packs не должны попадать в Git без отдельного решения.

## Связанные документы

- Установка и запуск: `SETUP.md`
- Архитектурные решения: `docs/DECISIONS.md`
- GigaChat: `docs/GIGACHAT_INTEGRATION.md`
