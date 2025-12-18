# DECISIONS (ADR-lite)

Короткий список ключевых архитектурных решений и причин.  
Нужен, чтобы новый чат/участник команды быстро понял “почему так”.

## 1) Офлайн по умолчанию

- **Решение**: по умолчанию `LLM_MODE=template`, `IMAGE_MODE=pillow`.
- **Причина**: демо должно работать без внешних сервисов/ключей.
- **Следствие**: всегда есть fallback, даже если API недоступно.

## 2) GigaChat интеграция как опциональный провайдер

- **Решение**: `LLM_MODE=gigachat` и `IMAGE_MODE=gigachat`, клиент + провайдеры выделены отдельными модулями.
- **Причина**: удобная смена провайдеров, изоляция авторизации/скачивания изображений, тестируемость.
- **Файлы**: `backend/app/agent/gigachat_client.py`, `backend/app/agent/gigachat_providers.py`.

## 3) Строгий формат ответа LLM для текста

- **Решение**: просим **строго JSON** `{tone, subject, body}` и валидируем.
- **Причина**: снижает галлюцинации и упрощает автоматизацию.
- **Файлы**: `backend/app/agent/llm_prompts.py`, `backend/app/agent/llm_provider.py`.

## 4) Изображения через встроенную text2image (function_call="auto")

- **Решение**: для картинок используем `function_call="auto"` и парсим `<img src="file_id">`.
- **Причина**: соответствует официальной схеме из документации.
- **Файлы**: `backend/app/agent/gigachat_client.py` (extract + download).

## 5) Idempotency на доставку

- **Решение**: `Delivery.idempotency_key` уникален; повторные запуски не создают дублей.
- **Причина**: регулярный конвейер должен быть безопасен к повторным прогонам.
- **Файлы**: `backend/app/services/sender.py`.

## 6) Runtime‑данные не в git

- **Решение**: `backend/data/` и `backend/.env` игнорируются.
- **Причина**: безопасность (секреты/артефакты/БД) и чистота репозитория.
- **Файлы**: `.gitignore`, `SECURITY.md`.

## 7) Windows‑friendly запуск

- **Решение**: `scripts/run_backend.cmd` с автоподбором порта.
- **Причина**: Windows часто имеет ограничения/занятые порты (WinError 10013/“залипшие” процессы).
- **Файлы**: `scripts/run_backend.cmd`, `backend/app/worker/run_dev_server.py`, `scripts/kill_port.cmd`.

## 8) Lifespan вместо on_event

- **Решение**: FastAPI startup реализован через `lifespan`.
- **Причина**: убрать deprecation warnings и быть совместимыми с будущими версиями.
- **Файлы**: `backend/app/main.py`.

## 9) VIP approval gating

- **Решение**: для клиентов с `segment=vip` агент создаёт `Greeting.status="needs_approval"` и **не отправляет автоматически**.
  Отправка происходит после действия **Approve & send** в UI (через `services/approval.py`).
- **Причина**: контроль качества/рисков для VIP и соответствие требованиям процесса.
- **Файлы**: `backend/app/agent/orchestrator.py`, `backend/app/services/approval.py`, `backend/app/web/templates/greetings.html`.

## 10) Аудит запусков агента (AgentRun)

- **Решение**: каждый вызов `run_once()` создаёт запись `AgentRun` и заполняет счётчики/статус по завершению.
- **Причина**: наблюдаемость конвейера, демо “регулярности”, диагностика ошибок и объёма работы.
- **Файлы**: `backend/app/db/models.py` (AgentRun), `backend/app/agent/orchestrator.py`, UI: `backend/app/web/router.py` + `backend/app/web/templates/runs.html`.


