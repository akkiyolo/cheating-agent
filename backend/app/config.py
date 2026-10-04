"""Application configuration, loaded once from the environment / `.env` at start-up."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    env: Literal["dev", "test", "prod"] = "dev"
    database_url: str = "postgresql+asyncpg://assess:assess@localhost:5433/assessment"
    jwt_secret: str = "change-me-dev-only-secret-0123456789abcdef"
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

    assessment_duration_s: int = Field(default=60 * 60, ge=60)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
