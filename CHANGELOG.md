# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and the repository follows a lightweight semantic versioning approach for releases.

## [Unreleased]

### Added
- Базовый конвейер поздравлений: события -> генерация -> доставка, web UI, API, тесты и локальные скрипты запуска.
- VIP approval gating (`needs_approval`) и аудит запусков через `AgentRun`.
- Company enrichment layer: импорт CSV, поля `ИНН/ОКВЭД/руководитель`, провайдеры `demo`, `dadata`, `hybrid`.
- Feedback loop для оценки качества поздравлений и ручные события для импортированной базы.
- Документы по проектной структуре, обзору и интеграции GigaChat.

### Changed
- Публичная документация приведена к более профессиональной структуре: краткий `README`, отдельный `SETUP.md`, обзор проекта и краткая инструкция по GigaChat.
- Дефолтный запуск `run_backend.cmd` использует порт `8001`.
- Генерация изображений через GigaChat использует event-specific presets и строгие запреты на людей и текст.

### Fixed
- SMTP fallback для клиентов без пригодного email.
- Стабильность JSON-ответа GigaChat и обработка “почти JSON” сценариев.
- Повторяемость demo-flow: reset runtime data, контроль лимитов и улучшенные outbox-сценарии.


