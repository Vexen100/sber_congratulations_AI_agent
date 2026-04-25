# DECISIONS (ADR-lite)

Короткий список ключевых архитектурных решений и причин. Нужен, чтобы новый
участник быстро понял, почему проект устроен именно так.

## 1) Офлайн по умолчанию

- **Решение**: по умолчанию `LLM_MODE=template`, `IMAGE_MODE=pillow`.
- **Причина**: проект должен запускаться и демонстрироваться без внешних ключей и API.
- **Файлы**: `backend/app/agent/generator.py`, `backend/app/agent/text_generator.py`.

## 2) GigaChat как опциональный провайдер

- **Решение**: интеграция с GigaChat вынесена в отдельные клиент и провайдеры.
- **Причина**: изоляция авторизации, удобная замена провайдера и тестируемость.
- **Файлы**: `backend/app/agent/gigachat_client.py`, `backend/app/agent/gigachat_providers.py`.

## 3) Строгий JSON-контракт для текстовой генерации

- **Решение**: LLM обязана возвращать строго JSON вида `{tone, subject, body}`, а ответ валидируется и при необходимости мягко repair-ится.
- **Причина**: это снижает число “почти JSON” ошибок и упрощает автоматическую обработку результата.
- **Файлы**: `backend/app/agent/llm_prompts.py`, `backend/app/agent/llm_provider.py`.

## 4) Изображения через text2image и контролируемые visual presets

- **Решение**: для image-generation используются GigaChat text2image и event-specific visual presets с общими запретами на людей и текст.
- **Причина**: нужна предсказуемая визуальная генерация без хаотичных сцен и повторения birthday-мотивов для всех поводов.
- **Файлы**: `backend/app/agent/gigachat_client.py`, `backend/app/agent/gigachat_providers.py`.

## 5) Idempotency на доставку

- **Решение**: `Delivery.idempotency_key` уникален; повторный запуск не создаёт дублей отправки.
- **Причина**: конвейер должен быть безопасен к повторным прогонам и scheduler-сценариям.
- **Файлы**: `backend/app/services/sender.py`.

## 6) Без VIP approval gating (единый конвейер отправки)

- **Решение**: сегментация клиента и ручное согласование перед отправкой убраны. Все поздравления создаются как `status="generated"`, а отправка происходит только в день события (`Event.event_date == today`) и зависит от `SEND_MODE` (file/smtp/noop).
- **Причина**: продуктовая логика упрощена; качество для аналитики и будущего дообучения фиксируется через feedback (оценка и производный `training_verdict`), без влияния на доставку.
- **Файлы**: `backend/app/agent/orchestrator.py`, `backend/app/services/due_sender.py`, `backend/app/web/templates/greetings.html`.

## 7) Аудит запусков через AgentRun

- **Решение**: каждый `run_once()` фиксируется как `AgentRun`, а greeting-объекты связываются с конкретным run.
- **Причина**: для диагностики и демонстрации важен прозрачный аудит не только по счётчикам, но и по конкретным результатам прогона.
- **Файлы**: `backend/app/db/models.py`, `backend/app/agent/orchestrator.py`, `backend/app/web/templates/runs.html`, `backend/app/web/templates/run_detail.html`.

## 8) Company enrichment через provider-based слой

- **Решение**: enrichment работает через провайдеры `demo`, `dadata`, `hybrid`, а локальные данные лежат в `backend/app/resources/company_data/`.
- **Причина**: проекту нужен стабильный demo-контур и понятный путь к более реальному внешнему источнику по ИНН.
- **Файлы**: `backend/app/services/company_enrichment.py`, `backend/app/services/company_import.py`, `backend/app/services/dadata_client.py`.

## 9) Feedback loop для Human-in-the-Loop

- **Решение**: в web UI менеджер сохраняет обязательный `score` (1–5), опционально `outcome` и `notes`; отдельного выбора вердикта в форме нет. В `save_feedback()` при отсутствии явного `training_verdict` он выводится из оценки: **4–5 → `accepted`**, **1–3 → `rejected`** (для отбора примеров дообучения и метрик). Через API по-прежнему можно передать `training_verdict` явно (`accepted` или `rejected`) — значение валидируется.
- **Причина**: единый простой сценарий в UI и предсказуемая связь «оценка → допуск к обучающей выборке», без смешения с доставкой.
- **Файлы**: `backend/app/services/feedback.py`, `backend/app/web/templates/greetings.html`, `backend/app/web/router.py`, `backend/app/api/routes/feedback.py`.

## 10) Управляемый режим отправки через `.env`

_Удалено_ (переменная `DELIVERY_SCHEDULE_MODE` больше не используется): отправка всегда происходит только в день события, чтобы поведение было предсказуемым и одинаковым для demo и production контуров.

## 11) Ручные события для импортированной базы

- **Решение**: оператор может создать единичный ручной повод или demo-кампанию для реальных клиентов.
- **Причина**: импортированная база не обязана иметь релевантные дни рождения или праздники в текущем окне времени, а генерацию нужно запускать уже сейчас.
- **Файлы**: `backend/app/services/manual_events.py`, `backend/app/api/routes/events.py`, `backend/app/web/templates/events.html`.

## 12) Post-generation funnel на dashboard

- **Решение**: dashboard показывает метрики по доставке/feedback/вердиктам (без стадии approval).
- **Причина**: нужен быстрый управленческий экран, объясняющий качество процесса без погружения в отдельные таблицы.
- **Файлы**: `backend/app/web/router.py`, `backend/app/web/templates/dashboard.html`.

## 13) (Опционально) RAG few-shot по менеджерскому feedback

- **Решение**: векторная память примеров включается только флагом `VECTOR_FEEDBACK_ENABLED`; тяжёлые зависимости вынесены в отдельный `backend/requirements-rag.txt`, а при выключенном флаге слой работает как no-op.
- **Причина**: CI/офлайн-демо должны оставаться быстрыми и детерминированными; RAG нужен как расширение для более качественной генерации в LLM-режимах.
- **Файлы**: `backend/app/services/vector_feedback.py`, `backend/app/agent/generator.py`, `backend/app/agent/llm_prompts.py`, `backend/env.example`.

## 14) Holiday knowledge layer и semantic-layer

- **Решение**: праздники и manual-сценарии расширяются семантическими тегами, а общий `EventSemantics` используется в text/image prompt-building.
- **Причина**: проект должен масштабировать генерацию через структуру и семантику повода, а не через бесконечные ручные промпты.
- **Файлы**: `backend/app/services/holiday_catalog.py`, `backend/app/services/event_detector.py`, `backend/app/agent/event_semantics.py`, `backend/app/agent/llm_prompts.py`.

## 15) Branded HTML email и demo-safe fallback-доставка

- **Решение**: SMTP-отправка формирует `multipart/alternative` письмо с HTML-версией, а клиенты без пригодного email автоматически переводятся в file-outbox fallback.
- **Причина**: нужен одновременно более продуктовый email-канал и устойчивый demo-flow без падений на неполных контактах.
- **Файлы**: `backend/app/services/email_rendering.py`, `backend/app/services/sender.py`, `backend/app/services/due_sender.py`.


