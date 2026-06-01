# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and the repository follows a lightweight semantic versioning approach for releases.

## [Unreleased]

### Added

- GitHub Actions: job `quality` (ruff, black), `unit-tests` (`pytest -m "not integration"`), `integration-tests` (`pytest -m integration`), сборка архива `backend`; опциональные шаги публикации релиза и deploy по тегу и ветке `main`. Триггер push также для веток `integration` и `react-new-base-backend`.
- Project Planner MVP: отдельная страница `/project-planner`, mock/offline режим, опциональный GigaChat provider, уточняющие вопросы, генерация с допущениями, run history, preview и DOCX-экспорт.
- Маркер pytest `integration` в `pytest.ini`; интеграционный тест API `POST /api/agent/run-once` со списками greetings/deliveries; тесты guardrails; unit-тест форматирования времени МСК в веб-слое.
- Опциональный few-shot по менеджерскому feedback: флаг `VECTOR_FEEDBACK_ENABLED`, зависимости в `backend/requirements-rag.txt`, поле `generation_source` у сценариев генерации.
- Календарь праздников в БД с загрузкой/миграцией и классификацией поводов (merge `holidays_branch` в `integration`).
- Merge ветки `New-tests` в `integration` с сохранением коммитов участника в истории (`merge --no-ff`).

### Changed

- Web UI feedback на странице поздравлений: одна кнопка сохранения отзыва, обязательный `score`; `training_verdict` выставляется в `save_feedback()` по оценке (4–5 → `accepted`, 1–3 → `rejected`), явная передача вердикта из формы не используется. API по-прежнему допускает явный `training_verdict` при создании записи.
- Project Planner: усилены DOCX preview/export, prompt skeleton, LLM JSON normalizer, fallback-поведение, roadmap deadline/start guardrails, Gantt-like представление и типографика DOCX.
- Конфигурация доставки: удалён неиспользуемый параметр `DELIVERY_SCHEDULE_MODE`; отправка всегда происходит только в день события (`Event.event_date == today`).
- Планировщик: автономность теперь гейтит scheduler и запуск «run once on start» (если автономность выключена — прогон не запускается).
- Документация: `docs/DECISIONS.md` (в т.ч. нумерация разделов 13–15), `README.md`, `docs/PROJECT_OVERVIEW.md`, `SETUP.md`, `ROADMAP.md`, этот changelog — без ссылок на удалённый VIP-контур и устаревший ручной вердикт в UI.

### Removed

- VIP approval gating и сегмент клиента в продуктовом потоке; отдельное согласование перед отправкой.

### Fixed

- SMTP: для демо-клиентов и небезопасных адресов — откат в file-outbox вместо падения прогона.
- Обработка «почти JSON» ответов GigaChat и повторяемость demo-flow (см. также коммиты в `integration`).
- Project Planner: исправлено скачивание DOCX через SPA/dev proxy, скрыты технические Pydantic tracebacks из пользовательских warnings.
