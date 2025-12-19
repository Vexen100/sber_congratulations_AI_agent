from __future__ import annotations

import asyncio
import datetime as dt
import json
import os
from pathlib import Path

from app.agent.gigachat_providers import (
    GigaChatImageProvider,
    GigaChatTextProvider,
    build_illustration_prompt,
)
from app.agent.llm_provider import LLMProviderError, parse_llm_json
from app.core.config import settings
from app.services.guardrails import validate_message_text


def _get_secret_from_dotenv(key: str) -> str | None:
    """Best-effort .env parser for local smoke tests (no extra deps).

    Prefers Settings (pydantic-settings) which already reads .env, but this function
    helps produce clearer error messages when users mis-format the .env file.
    """
    # 1) Prefer settings (loads backend/.env via SettingsConfigDict env_file)
    val = getattr(settings, "gigachat_credentials", None)
    if isinstance(val, str) and val.strip():
        return val.strip()

    # 2) Fallback to real env var (if exported)
    v = os.getenv(key, "").strip()
    if v:
        return v

    # 3) Fallback: parse .env file in CWD (we run from backend/)
    env_path = Path(".env")
    if not env_path.exists():
        return None

    for raw_line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v2 = line.split("=", 1)
        if k.strip() == key and v2.strip():
            return v2.strip().strip('"').strip("'")

    return None


async def main() -> None:
    # Preconditions: user configured .env and installed certs (or disabled verify for demo).
    creds = _get_secret_from_dotenv("GIGACHAT_CREDENTIALS")
    if not creds:
        env_path = Path(".env")
        cwd = os.getcwd()
        raise RuntimeError(
            "Missing required GigaChat credentials.\n"
            f"Current working directory: {cwd}\n"
            f"Looking for .env at: {env_path.resolve()} (exists={env_path.exists()})\n"
            "Ensure you have a line like this in backend/.env (key=value):\n"
            "  GIGACHAT_CREDENTIALS=YOUR_AUTHORIZATION_KEY\n"
            "Not just the raw key on a line.\n"
        )

    out_dir = Path("data") / "smoke"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) TEXT: ask for strict JSON, parse, validate, save
    system = (
        "Ты помощник Сбербанка. Сгенерируй поздравление. "
        "Выводи строго JSON без markdown и лишнего текста."
    )
    facts = {
        "first_name": "Ирина",
        "last_name": "Соколова",
        "company_name": "ООО Альфа-Логистика",
        "position": "Генеральный директор",
        "segment": "vip",
        "last_interaction_summary": "обсуждали условия РКО и зарплатный проект",
    }
    user = (
        "FACTS:\n"
        f"{facts}\n\n"
        "CONTEXT:\n"
        f"- event_type: birthday\n"
        f"- event_title: День рождения\n"
        f"- event_date: {dt.date.today().isoformat()}\n\n"
        "OUTPUT JSON schema:\n"
        "{\n"
        '  "tone": "official|warm",\n'
        '  "subject": "string",\n'
        '  "body": "string"\n'
        "}\n"
    )
    text_provider = GigaChatTextProvider()
    raw = await text_provider.generate(system=system, user=user)
    try:
        parsed = parse_llm_json(raw)
    except LLMProviderError:
        # Save raw for debugging, but do not print tokens/secrets.
        (out_dir / "text_raw.txt").write_text(raw, encoding="utf-8")
        raise

    validate_message_text(parsed.subject)
    validate_message_text(parsed.body)
    (out_dir / "text.json").write_text(
        json.dumps(
            {"tone": parsed.tone, "subject": parsed.subject, "body": parsed.body},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # 2) IMAGE: ask for a card, download jpg, save
    recipient_line = f"{facts['first_name']} {facts['last_name']}"
    style, prompt = build_illustration_prompt(
        event_type="birthday",
        event_title="День рождения",
        recipient_line=recipient_line,
        company=facts["company_name"],
    )
    img_provider = GigaChatImageProvider()
    file_id, jpg = await img_provider.generate_jpg(
        system_style=style,
        prompt=prompt,
        x_client_id="smoke-test",
    )
    (out_dir / f"card_{file_id}.jpg").write_bytes(jpg)

    print("[OK] GigaChat smoke test completed.")
    print(f"      Text saved:  {out_dir / 'text.json'}")
    print(f"      Image saved: {out_dir / f'card_{file_id}.jpg'}")


if __name__ == "__main__":
    asyncio.run(main())
