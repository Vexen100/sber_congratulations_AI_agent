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

## Архитектура

```text
Sources -> Enrichment -> Events -> Agent -> Delivery -> Feedback/Audit

CSV / demo seed / DaData
        -> клиентский профиль и company context
        -> Event detection / manual events
        -> text + image generation
        -> SMTP or file outbox
        -> dashboard, runs, feedback
```

## Карта кода

| Модуль | Назначение |
|--------|------------|
| `backend/app/main.py` | Точка входа FastAPI |
| `backend/app/web/` | Веб-интерфейс и operator flow |
| `backend/app/api/` | REST API endpoints |
| `backend/app/db/` | Модели данных и инициализация БД |
| `backend/app/agent/` | Оркестратор, prompt-building, text/image generation |
| `backend/app/services/` | Delivery, enrichment, holidays, manual events, feedback |

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

## Связанные документы

- Установка и запуск: `SETUP.md`
- Архитектурные решения: `docs/DECISIONS.md`
- GigaChat: `docs/GIGACHAT_INTEGRATION.md`
