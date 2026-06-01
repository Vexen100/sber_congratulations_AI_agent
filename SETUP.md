# Инструкция по установке и запуску (Windows, локальное демо)

Эта инструкция рассчитана на **офлайн/локальную** демонстрацию MVP.

## 1) Установка

Самый простой способ:

```bat
scripts\setup_backend.cmd
```

Скрипт:
- создаст `backend\.venv`
- установит зависимости
- создаст `backend\.env` из `backend\env.example` (если `.env` ещё нет)

## 2) Запуск

```bat
scripts\run_backend.cmd
```

По умолчанию сервер поднимается на **8001**. Если на Windows выбранный порт запрещён/занят (например, `WinError 10013`),
скрипт **автоматически выберет ближайший доступный порт** и выведет его в консоль.

## (Опционально) Включить “реальный” LLM

По умолчанию проект работает в офлайн-режиме (`LLM_MODE=template`). Чтобы включить LLM:

1) Открой `backend\.env` и выставь:

```
LLM_MODE=openai
OPENAI_API_KEY=...
```

2) При необходимости укажи OpenAI-compatible endpoint/модель:

```
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
```

## (Опционально) Включить GigaChat (текст и/или открытки)

1) Открой `backend\.env` и выставь:

```
LLM_MODE=gigachat
IMAGE_MODE=gigachat
GIGACHAT_CREDENTIALS=...   # Authorization Key
```

2) Если возникают TLS ошибки, см. установку сертификата и краткую инструкцию в `docs/GIGACHAT_INTEGRATION.md`.
Для демо (не рекомендуется в проде) можно временно:

```
GIGACHAT_VERIFY_SSL_CERTS=false
```

## End-to-end проверка GigaChat (smoke test)

Когда переменные окружения настроены, можно прогнать e2e smoke-test (1 текст + 1 открытка):

```bat
scripts\run_gigachat_smoke.cmd
```

Результаты сохраняются в `backend\data\smoke\`.

### Если нужен другой порт

```bat
set PORT=8000
scripts\run_backend.cmd
```

### Если порт «залип»

Иногда после прошлых запусков на Windows порт может остаться занятым/подвисшим.

```bat
scripts\kill_port.cmd 8000
```

## 3) Быстрый демо-сценарий

1. Откройте `http://127.0.0.1:8001/` в браузере.
2. Нажмите кнопку **Seed demo data** — система создаст 5 демо‑клиентов, у которых ближайшие поводы будут сегодня или в ближайшие дни.
3. Нажмите **Run agent now**
4. Посмотрите результаты:
   - вкладки **Greetings** и **Deliveries**
   - файлы outbox: `backend\data\outbox\`
   - открытки: `backend\data\cards\`

Если вы уже запускали агента раньше и видите много `skipped`/мало новых файлов — это нормально (идемпотентность).
Для “чистого” демо нажмите в UI **Reset runtime data** и запустите агент снова.

Важно: агент **может сгенерировать поздравления заранее**, но отправка происходит **только в день события**.

## Project Planner (локальный mock-сценарий)

Project Planner работает отдельно от агента поздравлений и по умолчанию не требует сети или GigaChat credentials:

```env
PROJECT_PLANNER_USE_MOCK_LLM=true
```

1. Запустите backend через `scripts\run_backend.cmd`.
2. Откройте React UI и перейдите на `/project-planner`.
3. Заполните идею проекта, дедлайн, географию, стейкхолдеров и акценты.
4. При необходимости включите чекбокс **Генерировать с допущениями**.
5. Создайте run, проверьте preview/history и скачайте DOCX.

Если используете Vite dev server, backend должен быть запущен на `http://127.0.0.1:8001`: Vite проксирует `/api`, `/data` и `/static` на этот backend.

## React UI (опционально)

Backend теперь обслуживает только React UI. Чтобы открыть интерфейс через FastAPI, сначала соберите frontend:

```bat
cd frontend
npm install
npm run build
cd ..
scripts\run_backend.cmd
```

Для разработки можно запустить Vite отдельно. Он проксирует `/api`, `/data` и `/static` на backend на порту `8001`, поэтому backend должен быть уже запущен:

```bat
cd frontend
npm install
npm run dev
```

Если React build отсутствует, backend покажет страницу-подсказку с командой `npm run build`.

## (Опционально) Регулярный режим (планировщик)

Запуск:

```bat
:: Включить scheduler только в отдельном процессе (чтобы избежать двойных прогонов)
set SCHEDULER_MODE=worker
scripts\run_scheduler.cmd
```

Принципы регулярного режима:
- Планировщик запускает агента **каждый день в 09:00** (в таймзоне `TZ`, по умолчанию `Europe/Moscow`).
- Агент заранее генерирует поздравления на горизонт `LOOKAHEAD_DAYS`.
- Доставка происходит **только в день события** (event_date == today).
- Автономный режим фактически запускается только после включения кнопкой в UI (**Autonomy enabled**); при выключенной автономности планировщик не делает прогонов.

## (Опционально) Реальная отправка по email (SMTP)

По умолчанию отправка идёт в outbox-файлы (`SEND_MODE=file`). Для реальной отправки:

1) В `backend\.env` установите:

```
SEND_MODE=smtp
SMTP_HOST=...
SMTP_PORT=587
SMTP_USERNAME=...
SMTP_PASSWORD=...
SMTP_FROM_EMAIL=...
```

2) **Безопасность по умолчанию**: реальная отправка блокируется, пока вы не настроите allowlist доменов:

```
SMTP_ALLOWLIST_DOMAINS=mycompany.com,gmail.com
SMTP_ALLOW_ALL_RECIPIENTS=false
```

3) Дополнительно:
- Демо-клиенты (`is_demo=true`) и адреса вида `*@example.com` никогда не отправляются через SMTP.
- Если `SEND_MODE=smtp`, то для демо-клиентов отправка **падает обратно в outbox-файлы** (безопасный demo-flow).
 
## (Опционально) RAG / few-shot по менеджерскому feedback

По умолчанию RAG выключен. Чтобы включить:

1) Установите доп. зависимости:

```bat
cd backend
pip install -r requirements-rag.txt
```

2) В `backend\.env`:

```
VECTOR_FEEDBACK_ENABLED=true
VECTOR_DB_PATH=./data/chroma_feedback
```
