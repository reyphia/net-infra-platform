"""Central application configuration.

All runtime configuration is sourced from environment variables (see
`.env.example` at the repository root). Nothing here is a hardcoded secret;
`SECRET_KEY` / `ENCRYPTION_KEY` must be supplied by the operator.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Identity / server ---
    app_name: str = "Network Infrastructure Platform"
    environment: str = Field(default="development")  # development | production
    api_prefix: str = "/api"

    # --- Database ---
    database_url: str = Field(default="sqlite+aiosqlite:///./data/platform.db")

    # --- Security ---
    # SECRET_KEY signs session/API tokens. ENCRYPTION_KEY (Fernet, 32 url-safe
    # base64 bytes) encrypts credential profiles at rest. Both MUST be set
    # explicitly in production; the defaults below only exist so `pytest` and
    # first-run `docker compose up` don't crash, and are clearly insecure.
    secret_key: str = Field(default="INSECURE-DEV-SECRET-CHANGE-ME")
    encryption_key: str = Field(default="")

    # --- Discovery defaults (all overridable per discovery job) ---
    discovery_default_timeout_seconds: float = 2.0
    discovery_default_max_concurrency: int = 50
    discovery_default_retry_count: int = 1
    discovery_allowed_scopes: list[str] = Field(default_factory=list)  # empty == operator must specify scope per job

    # --- SNMP defaults ---
    snmp_default_community: str = ""  # never hardcode a real community string; empty forces explicit config
    snmp_default_port: int = 161
    snmp_default_timeout_seconds: float = 2.0
    snmp_default_retries: int = 1

    # --- SSH defaults ---
    ssh_connect_timeout_seconds: float = 8.0
    ssh_command_timeout_seconds: float = 20.0
    ssh_known_hosts_path: str = "./data/known_hosts"
    ssh_allow_insecure_lab_mode: bool = False  # must be explicitly enabled; see docs/security.md

    # --- Storage paths ---
    config_backup_dir: str = "./data/backups"

    @field_validator("environment")
    @classmethod
    def _validate_env(cls, v: str) -> str:
        if v not in {"development", "production", "test"}:
            raise ValueError("environment must be one of development|production|test")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
