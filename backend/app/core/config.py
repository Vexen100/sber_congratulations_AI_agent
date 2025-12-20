from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Sber Congratulations AI Agent (MVP)"
    app_env: str = "dev"
    tz: str = "Europe/Moscow"

    database_url: str = "sqlite+aiosqlite:///./data/app.db"

    lookahead_days: int = 7
    max_holiday_recipients: int = 12  # prevents token blow-up on demo (per holiday)
    max_gigachat_images_per_run: int = 5  # speed + token safety; rest uses Pillow fallback

    send_mode: str = "file"  # file|smtp|noop
    outbox_dir: str = "./data/outbox"

    # SMTP (optional, real email sending)
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None
    smtp_starttls: bool = True
    smtp_ssl: bool = False
    smtp_timeout_sec: float = 15.0

    # Safety: never send to demo/test addresses by default.
    # Allowlist is a comma-separated list of domains, e.g. "mycompany.com,gmail.com".
    smtp_allowlist_domains: str = ""
    smtp_allow_all_recipients: bool = False

    # LLM (optional). Keep "template" as default for offline demos.
    llm_mode: str = "template"  # template|openai|gigachat

    # Image generation (optional). Default is deterministic Pillow render.
    image_mode: str = "pillow"  # pillow|gigachat

    # OpenAI-compatible endpoint (OpenAI / vLLM / LM Studio / etc.)
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    openai_temperature: float = 0.5
    openai_timeout_sec: float = 20.0

    # GigaChat (optional)
    gigachat_credentials: str | None = (
        None  # Authorization Key (used as Basic credential for oauth)
    )
    gigachat_scope: str = "GIGACHAT_API_PERS"
    gigachat_oauth_url: str = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    gigachat_base_url: str = "https://gigachat.devices.sberbank.ru/api/v1"
    gigachat_model: str = "GigaChat"
    gigachat_temperature: float | None = None
    # Base timeout для обычных запросов (чат, текст)
    gigachat_timeout_sec: float = 30.0
    # Отдельный таймаут для скачивания изображений (обычно дольше, можно поднять для демо)
    gigachat_image_timeout_sec: float = 60.0

    # TLS / certificates
    gigachat_verify_ssl_certs: bool = True
    gigachat_ca_bundle_file: str | None = None


settings = Settings()
