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
- **Промпты для персонализации**: 
  - Детальные инструкции по персонализации с использованием FACTS (имя, компания, должность)
  - Универсальные промпты, адаптирующиеся под разные типы праздников (birthday, holiday)
  - Рекомендации по тону на основе сегмента клиента и tone_hint из holiday_tags
  - Требования к длине body: 450-1200 символов (целевой диапазон 600-900) для более содержательных текстов
  - Акцент на разнообразие формулировок и естественность текста
  - **Практика**: некоторые провайдеры (в т.ч. GigaChat) могут вернуть «почти JSON» с **неэкранированными переносами строк внутри строк**.  
    В `parse_llm_json()` есть безопасный repair: переносы строк **внутри** строковых литералов экранируются как `\\n`, после чего JSON парсится.
  - **Важно про “обрывки” в логах**: предупреждения печатают только **preview** первых ~500 символов ответа для читабельности логов.  
    В БД/в outbox сохраняется **полный** текст `Greeting.body`.

## 4) Изображения через встроенную text2image (function_call="auto")

- **Решение**: для картинок используем `function_call="auto"` и парсим `<img src="file_id">`.
- **Причина**: соответствует официальной схеме из документации.
- **Файлы**: `backend/app/agent/gigachat_client.py` (extract + download), `backend/app/agent/gigachat_providers.py`.
- **Промпт**: используется прямая команда "Нарисуй ..." как в официальных примерах GigaChat, промпт максимально простой для надежной генерации.

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
  Отправка происходит по расписанию (в день события) после действия **Approve** в UI (через `services/approval.py`).
- **Причина**: контроль качества/рисков для VIP и соответствие требованиям процесса.
- **Файлы**: `backend/app/agent/orchestrator.py`, `backend/app/services/approval.py`, `backend/app/web/templates/greetings.html`.

## 10) Аудит запусков агента (AgentRun)

- **Решение**: каждый вызов `run_once()` создаёт запись `AgentRun` и заполняет счётчики/статус по завершению.
- **Причина**: наблюдаемость конвейера, демо “регулярности”, диагностика ошибок и объёма работы.
- **Файлы**: `backend/app/db/models.py` (AgentRun), `backend/app/agent/orchestrator.py`, UI: `backend/app/web/router.py` + `backend/app/web/templates/runs.html`.

## 11) Лимит получателей на праздники (демо‑контроль токенов)

- **Решение**: при генерации holiday‑ивентов ограничиваем число получателей (по умолчанию `MAX_HOLIDAY_RECIPIENTS=12`).
- **Причина**: праздник *для каждого клиента* быстро сжигает токены/время на демо.
- **Файлы**: `backend/app/services/event_detector.py`, `backend/app/core/config.py`, `backend/env.example`.

## 12) Reset runtime data для чистых прогонов

- **Решение**: кнопка в UI очищает runtime‑данные (Events/Greetings/Deliveries/AgentRuns) и outbox/cards/smoke артефакты, но сохраняет Clients/Holidays.
- **Причина**: повторные прогоны по умолчанию идемпотентны → много `skipped` и “старые” статусы. Reset делает демо воспроизводимым.
- **Файлы**: `backend/app/services/reset_runtime.py`, `backend/app/web/router.py`, `backend/app/web/templates/base.html`.

## 13) Скорость: лимит GigaChat-изображений за прогон

- **Решение**: ограничиваем количество генераций изображений через GigaChat за один `run_once()` (`MAX_GIGACHAT_IMAGES_PER_RUN`, по умолчанию 5). Остальные изображения — быстрый Pillow fallback.
- **Причина**: генерация картинок самая медленная и “дорогая” по токенам/времени, особенно при нескольких событиях.
- **Файлы**: `backend/app/core/config.py`, `backend/app/agent/orchestrator.py`, `backend/env.example`.


