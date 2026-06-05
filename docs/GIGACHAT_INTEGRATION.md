# Интеграция с GigaChat

## Подключение

Для использования GigaChat в проекте необходимо:

1. Получить ключ авторизации в [личном кабинете GigaChat](https://developers.sber.ru/studio).
2. Добавить в `backend/.env`:

```env
LLM_MODE=gigachat
IMAGE_MODE=gigachat
GIGACHAT_CREDENTIALS=<ваш_ключ_авторизации>
```

## TLS-сертификат

Для работы с GigaChat API может потребоваться корневой сертификат Минцифры.

- Инструкция по установке: <https://developers.sber.ru/docs/gigachat/certificates>
- Общая документация API: <https://developers.sber.ru/docs/gigachat>

Для локального демо можно временно отключить проверку сертификата:

```env
GIGACHAT_VERIFY_SSL_CERTS=false
```

Использовать это значение в постоянной среде не рекомендуется.

## Project Planner

Project Planner использует GigaChat опционально и по умолчанию остаётся в локальном mock/offline режиме:

```env
PROJECT_PLANNER_USE_MOCK_LLM=true
```

Чтобы включить GigaChat для Project Planner, выставьте:

```env
PROJECT_PLANNER_USE_MOCK_LLM=false
GIGACHAT_CREDENTIALS=<ваш_ключ_авторизации>
```

Настройки старого агента поздравлений (`LLM_MODE`, `IMAGE_MODE`) при этом не меняются автоматически. Для Project Planner ответы Lite/Pro проходят retry, JSON-нормализацию, Pydantic-валидацию и backend guardrails; если структура ответа не подходит, используется fallback generator с коротким пользовательским предупреждением.

Reference Packs, если установлены, добавляются в Project Planner prompt как компактный curated JSON context. В v1 они не меняют напрямую `ProjectReport`, budget totals, roadmap, concepts, resources или warnings.

DOCX и PPTX exports строятся из сохранённого результата run. Скачивание export-файлов не выполняет новый вызов GigaChat.

## Что ещё проверить

- `GIGACHAT_CREDENTIALS` задан в `backend/.env`, а сам файл не попал в Git.
- Для текстовой генерации выставлен `LLM_MODE=gigachat`.
- Для генерации изображений выставлен `IMAGE_MODE=gigachat`.
- При необходимости можно прогнать smoke-test: `scripts\run_gigachat_smoke.cmd`.
