"""Explicit configuration loading; importing this module does not load settings."""

import ipaddress
import json
import os
from pathlib import Path
import re
from typing import Literal, Mapping
from urllib.parse import urlsplit

from dotenv import dotenv_values
from pydantic import Field, SecretStr, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class ConfigurationError(ValueError):
    """A safe error naming invalid settings without exposing their input."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        hide_input_in_errors=True, extra="forbid", populate_by_name=True
    )

    app_env: Literal["development", "test", "production"] = Field(
        default="development", alias="APP_ENV"
    )
    database_url: SecretStr = Field(alias="DATABASE_URL")
    university_email_domain: Literal["sdu.edu.kz"] = Field(
        default="sdu.edu.kz", alias="UNIVERSITY_EMAIL_DOMAIN"
    )
    frontend_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173"], alias="FRONTEND_ORIGINS"
    )
    jwt_secret_key: SecretStr = Field(alias="JWT_SECRET_KEY")
    jwt_access_minutes: int = Field(default=15, gt=0, alias="JWT_ACCESS_MINUTES")
    refresh_session_days: int = Field(default=7, gt=0, alias="REFRESH_SESSION_DAYS")
    upload_dir: Path = Field(default=Path("backend/uploads"), alias="UPLOAD_DIR")
    refresh_cookie_secure: bool = Field(default=False, alias="REFRESH_COOKIE_SECURE")
    refresh_cookie_httponly: bool = Field(
        default=True, alias="REFRESH_COOKIE_HTTPONLY"
    )
    refresh_cookie_samesite: Literal["lax"] = Field(
        default="lax", alias="REFRESH_COOKIE_SAMESITE"
    )
    smtp_host: str | None = Field(default=None, alias="SMTP_HOST")
    smtp_port: int | None = Field(default=None, gt=0, le=65535, alias="SMTP_PORT")
    smtp_username: SecretStr | None = Field(default=None, alias="SMTP_USERNAME")
    smtp_password: SecretStr | None = Field(default=None, alias="SMTP_PASSWORD")
    smtp_from_email: str | None = Field(default=None, alias="SMTP_FROM_EMAIL")
    smtp_security: Literal["starttls", "tls"] = Field(
        default="starttls", alias="SMTP_SECURITY"
    )

    @classmethod
    def settings_customise_sources(cls, settings_cls, **sources):
        # The loader provides one isolated merged input. Never re-read ambient
        # environment, .env, or a secrets directory behind the caller's back.
        return (sources["init_settings"],)

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value):
        try:
            if value.get_secret_value() == "sqlite+pysqlite:///:memory:":
                return value
            parsed = urlsplit(value.get_secret_value())
            valid = (
                parsed.scheme in {"postgresql", "postgresql+psycopg"}
                and parsed.hostname
                and parsed.path.strip("/")
                and parsed.port != 0
            )
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("DATABASE_URL must be PostgreSQL or explicit SQLite memory")
        return value

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret(cls, value):
        raw = value.get_secret_value()
        placeholders = ("replace", "placeholder", "change_me", "changeme", "example")
        if len(raw.strip()) < 32 or any(word in raw.lower() for word in placeholders):
            raise ValueError("JWT_SECRET_KEY requires a non-placeholder secret of at least 32 characters")
        return value

    @field_validator("upload_dir")
    @classmethod
    def resolve_upload_dir(cls, value):
        return (REPOSITORY_ROOT / value).resolve() if not value.is_absolute() else value.resolve()

    @field_validator("frontend_origins")
    @classmethod
    def validate_origins(cls, values):
        if not values:
            raise ValueError("FRONTEND_ORIGINS must contain explicit origins")
        for value in values:
            try:
                parsed = urlsplit(value)
                port = parsed.port
                valid = (
                    parsed.scheme in {"http", "https"}
                    and parsed.hostname
                    and "*" not in value
                    and not parsed.username
                    and not parsed.password
                    and not parsed.path
                    and not parsed.query
                    and not parsed.fragment
                    and port != 0
                )
                if parsed.scheme == "http" and parsed.hostname != "localhost":
                    valid = valid and ipaddress.ip_address(parsed.hostname).is_loopback
            except ValueError:
                valid = False
            if not valid:
                raise ValueError("FRONTEND_ORIGINS contains an invalid or insecure origin")
        return values

    @field_validator("smtp_host")
    @classmethod
    def validate_smtp_host(cls, value):
        if value is not None and (not value.strip() or any(c.isspace() for c in value) or "://" in value):
            raise ValueError("SMTP_HOST must be a hostname")
        return value

    @field_validator("refresh_cookie_httponly")
    @classmethod
    def require_httponly(cls, value):
        if not value:
            raise ValueError("REFRESH_COOKIE_HTTPONLY must be true")
        return value

    @field_validator("smtp_from_email")
    @classmethod
    def validate_sender(cls, value):
        if value is not None and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("SMTP_FROM_EMAIL must be an email address")
        return value

    @model_validator(mode="after")
    def production_safety(self):
        if self.app_env == "production":
            if self.database_url.get_secret_value() == "sqlite+pysqlite:///:memory:":
                raise ValueError("DATABASE_URL memory mode is forbidden in production")
            if not self.refresh_cookie_secure:
                raise ValueError("REFRESH_COOKIE_SECURE must be true in production")
            if any(urlsplit(origin).scheme != "https" for origin in self.frontend_origins):
                raise ValueError("FRONTEND_ORIGINS must use HTTPS in production")
        return self

    def validate_email_delivery(self):
        """Require complete SMTP configuration without connecting or sending."""
        missing = []
        for name in ("smtp_host", "smtp_port", "smtp_username", "smtp_password", "smtp_from_email"):
            value = getattr(self, name)
            raw = value.get_secret_value() if isinstance(value, SecretStr) else value
            if raw is None or (isinstance(raw, str) and not raw.strip()):
                missing.append(type(self).model_fields[name].alias)
        if missing:
            raise ConfigurationError("Missing email settings: " + ", ".join(missing))
        return self


def load_settings(*, environ: Mapping[str, str] | None = None, env_file=REPOSITORY_ROOT / ".env") -> Settings:
    """Environment overrides optional .env, which overrides non-secret defaults.

    Pass an isolated mapping and env_file=None for service-free tests.
    Relative .env paths and upload paths are rooted at the repository.
    """
    supported = {field.alias for field in Settings.model_fields.values()}
    values = {}
    if env_file is not None:
        path = Path(env_file)
        if not path.is_absolute():
            path = REPOSITORY_ROOT / path
        try:
            values.update({k: v for k, v in dotenv_values(path, interpolate=False).items() if k in supported})
        except (OSError, UnicodeError):
            raise ConfigurationError("Invalid .env configuration file") from None
    values.update({k: v for k, v in (os.environ if environ is None else environ).items() if k in supported})
    if "FRONTEND_ORIGINS" in values:
        try:
            values["FRONTEND_ORIGINS"] = json.loads(values["FRONTEND_ORIGINS"])
        except (TypeError, ValueError):
            raise ConfigurationError("Invalid setting: FRONTEND_ORIGINS") from None
    if "REFRESH_COOKIE_SECURE" not in values and values.get("APP_ENV") == "production":
        values["REFRESH_COOKIE_SECURE"] = True
    try:
        return Settings(**values)
    except ValidationError as error:
        names = set()
        for item in error.errors(include_input=False, include_context=False):
            if item["loc"]:
                names.add(str(item["loc"][0]))
            elif "DATABASE_URL" in item["msg"]:
                names.add("DATABASE_URL")
            elif "REFRESH_COOKIE_SECURE" in item["msg"]:
                names.add("REFRESH_COOKIE_SECURE")
            else:
                names.add("FRONTEND_ORIGINS")
        raise ConfigurationError("Invalid settings: " + ", ".join(sorted(names))) from None
