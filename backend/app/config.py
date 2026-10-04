"""Application configuration, loaded once from the environment / `.env` at start-up."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
DEV_JWT_SECRET = "change-me-dev-only-secret-0123456789abcdef"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    env: Literal["dev", "test", "prod"] = "dev"
    database_url: str = "postgresql+asyncpg://assess:assess@localhost:5433/assessment"
    jwt_secret: str = DEV_JWT_SECRET
    access_token_minutes: int = 30
    refresh_token_days: int = 7
    cors_origins: str = "http://localhost:3000"

    admin_password: str = "admin-pass"
    researcher_password: str = "researcher-pass"
    candidate_password: str = "candidate-pass"

    # sandbox limits (immutable at runtime)
    sandbox_cpus: float = 0.5
    sandbox_memory_mb: int = 256
    sandbox_pids: int = 64
    sandbox_timeout_s: float = 10.0
    sandbox_python_image: str = "python:3.13-slim"
    sandbox_cpp_image: str = "gcc:14"
    sandbox_java_image: str = "eclipse-temurin:21-jdk"
    # Where per-run work dirs are created. When the backend itself runs in a container that talks to the host
    # Docker daemon, this must be a path mounted at the *same* location on the host (see docker-compose.yml).
    sandbox_workdir: str | None = None

    # Single-image deployment (e.g. Render): when set, the built front end in this directory is served at "/" and
    # the API moves under "/api", matching the front end's same-origin API base.
    frontend_dist: str | None = None

    assessment_duration_s: int = Field(default=60 * 60, ge=60)

    @field_validator("database_url")
    @classmethod
    def _async_driver(cls, v: str) -> str:
        # Hosting providers hand out postgres:// / postgresql:// URLs; SQLAlchemy async needs the asyncpg driver.
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+asyncpg://" + v[len(prefix):]
        return v

    @model_validator(mode="after")
    def _prod_secrets(self) -> Settings:
        if self.env == "prod" and (self.jwt_secret == DEV_JWT_SECRET or len(self.jwt_secret) < 32):
            raise ValueError("JWT_SECRET must be set to a random value of at least 32 characters when ENV=prod")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
