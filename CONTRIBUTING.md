# Contributing

Спасибо за интерес к проекту!

## Как предложить изменения

1) Создайте issue с описанием проблемы/предложения (или возьмите существующее).  
2) Сделайте fork и создайте ветку:

```bash
git checkout -b feat/short-description
```

3) Убедитесь, что проект запускается локально (см. `README.md` и `SETUP.md`).  
4) Добавьте/обновите тесты, если меняете бизнес-логику.  
5) Перед PR:

```bash
cd backend
python -m pytest -q
python -m ruff check .
python -m black --check .
```

## Быстрый локальный setup

### Windows

```bat
scripts\setup_backend.cmd
scripts\run_backend.cmd
```

### Linux/macOS

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp env.example .env
```

## Стиль кода

- Python: форматирование **Black**, линт **Ruff**.
- Пишите небольшие PR с понятным описанием и скриншотами UI (если релевантно).
- Перед участием в обсуждениях и review ознакомьтесь с `CODE_OF_CONDUCT.md`.

## Что не принимать в PR

- Секреты (ключи, токены), персональные данные реальных клиентов.
- Артефакты рантайма (`backend/data/`, `.venv/`, `.env`).


