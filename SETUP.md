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

2) Если возникают TLS ошибки, см. установку сертификата в `instruction_gigachat.md`.
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

## 3) Демо (2 клика)

1. Откройте `http://127.0.0.1:8001/`
2. Нажмите **Seed demo data**
3. Нажмите **Run agent now**
4. Посмотрите результаты:
   - вкладки **Greetings** и **Deliveries**
   - файлы outbox: `backend\data\outbox\`
   - открытки: `backend\data\cards\`


