# Changelog

## Unreleased

- Initial MVP: конвейер поздравлений (events → generate → send), web UI, API, tests, scripts.
- Docs/scripts: дефолтный порт запуска `run_backend.cmd` → **8001**, добавлен `scripts/kill_port.cmd`, добавлен `SETUP.md`.
- Added: VIP approval gating (`needs_approval`) and AgentRun audit (runs page).
- Improved: GigaChat card prompts (no text), text privacy (no last interaction details), reset runtime button, seed demo diversity, holiday recipient limit.
- Fixed: GigaChat image generation — упрощен промпт до формата "Нарисуй ..." (соответствует документации), улучшен парсер file_id, добавлено детальное логирование для отладки.


