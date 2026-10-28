from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    environment: str = "development"
    frontend_url: str = "https://www.gnkalgo.com"
    database_url: str = "postgresql+psycopg://gnk@postgres/gnk"
    redis_url: str = "redis://redis:6379/0"
    session_ttl: int = 28800
    cookie_secure: bool = True
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@gnkalgo.com"
    smtp_starttls: bool = True

    @field_validator("frontend_url")
    @classmethod
    def origin_only(cls, value: str):
        from urllib.parse import urlparse

        parsed = urlparse(value)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.netloc
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
            or parsed.username
        ):
            raise ValueError("FRONTEND_URL must be an HTTP(S) origin, without markdown or a path")
        return value.rstrip("/")


@lru_cache
def settings():
    value = Settings()
    if value.environment == "production" and (
        not value.cookie_secure
        or not value.frontend_url.startswith("https://")
        or not value.smtp_host
        or not value.smtp_starttls
    ):
        raise RuntimeError("Production requires HTTPS, Secure cookies and SMTP with STARTTLS")
    return value
