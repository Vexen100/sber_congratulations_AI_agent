# AI Handoff (Cursor) — Sber Congratulations AI Agent

Этот файл нужен для **безопасной и быстрой передачи контекста** в новый чат (контекстные окна ограничены).  
Держите его актуальным: новый ассистент читает его и сразу “въезжает” в проект.

## TL;DR (что это за проект)

MVP: конвейер поздравлений (события → генерация текста/открытки → отправка/log) с web UI + API.  
Поддерживает офлайн‑режим и интеграцию с **GigaChat** (текст + открытки).

## Безопасность общения (обязательные правила)

- **Никогда не отправляйте в чат**:
  - `backend/.env` (ключи/секреты),
  - `backend/data/*` (БД, outbox, артефакты),
  - реальные персональные данные клиентов,
  - токены/ключи/сертификаты (`*.pem/*.crt/*.key`).
- **Трейсбеки/логи**: можно отправлять, но **вырезайте** любые `Authorization`, `Bearer`, `Basic`, `access_token`.
- Если нужно проверить настройки: пишите “ключ настроен, но не показываю”.

## Быстрый старт (локально, Windows)

1) Установка:

```bat
scripts\setup_backend.cmd
```

2) Запуск UI+API:

```bat
scripts\run_backend.cmd
```

Скрипт сам подберёт доступный порт и выведет URL.

3) Демо:
- **Seed demo data**
- **Run agent now**
- страницы: Clients / Events / Greetings / Deliveries
- артефакты: `backend\data\outbox\`, `backend\data\cards\`

## Режимы генерации (важно)

Настраивается в `backend/.env` (файл не коммитится).

- **Офлайн**:
  - `LLM_MODE=template`
  - `IMAGE_MODE=pillow`
- **GigaChat**:
  - `LLM_MODE=gigachat`
  - `IMAGE_MODE=gigachat`
  - `GIGACHAT_CREDENTIALS=...`
  - TLS/сертификат: см. `instruction_gigachat.md`

## End-to-end smoke test (GigaChat)

Проверка “реально ходим в API и скачиваем картинку”:

```bat
scripts\run_gigachat_smoke.cmd
```

Результаты: `backend\data\smoke\text.json` и `backend\data\smoke\card_<id>.jpg`

## Карта кода (куда смотреть)

- **Точка входа приложения**: `backend/app/main.py`
- **Web UI**: `backend/app/web/router.py` + `backend/app/web/templates/*`
- **API**: `backend/app/api/*`
- **БД модели**: `backend/app/db/models.py`
- **Агент (оркестратор)**: `backend/app/agent/orchestrator.py`
- **Генерация текста (общая)**: `backend/app/agent/generator.py`
- **LLM провайдеры**: `backend/app/agent/llm_provider.py`
- **GigaChat**:
  - клиент: `backend/app/agent/gigachat_client.py`
  - провайдеры: `backend/app/agent/gigachat_providers.py`
- **Детектор событий**: `backend/app/services/event_detector.py`
- **Отправка (MVP outbox)**: `backend/app/services/sender.py`
- **Guardrails**: `backend/app/services/guardrails.py`
- **Планировщик**: `backend/app/worker/run_scheduler.py`

## Что уже “принято” как решения

См. `docs/DECISIONS.md`.

## Следующие крупные задачи (после MVP)

- **VIP approval flow**: уже реализован базовый вариант: `vip` → `needs_approval`, подтверждение в UI → отправка.
- **Статистика/аудит**: AgentRun, метрики по периодам, ошибки, повторная отправка.
- **Реальные каналы отправки**: SMTP/SMS/мессенджеры.

## Copy‑paste для нового чата (Cursor)

Скопируйте и вставьте в новый чат:

> Мы работаем в Cursor над репозиторием `sber_congratulations_AI_agent_2`.  
> Прочитай `AI_HANDOFF.md`, `README.md`, `SETUP.md`, `docs/DECISIONS.md`.  
> Важно: секреты/ключи/`.env`/`backend/data` в чат не отправляю.  
> Текущая задача: (вставь сюда задачу).  


