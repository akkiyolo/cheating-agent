from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, MetaData
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.config import get_settings

NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)
    type_annotation_map = {dict: JSON, list: JSON, datetime: DateTime(timezone=True)}


def make_engine(url: str | None = None, *, null_pool: bool = False) -> AsyncEngine:
    url = url or get_settings().database_url
    kwargs: dict = {}
    if null_pool or url.startswith("sqlite"):
        kwargs["poolclass"] = NullPool
    else:
        kwargs.update(pool_size=10, max_overflow=20, pool_pre_ping=True)
    return create_async_engine(url, **kwargs)


class Database:
    """Holds the process-wide engine. Agent threads create their own (engines are loop-bound)."""

    def __init__(self, url: str | None = None, *, null_pool: bool = False) -> None:
        self.engine = make_engine(url, null_pool=null_pool)
        self.sessionmaker = async_sessionmaker(self.engine, expire_on_commit=False)

    async def create_all(self) -> None:
        import app.models  # noqa: F401  (register tables)

        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def dispose(self) -> None:
        await self.engine.dispose()


_db: Database | None = None


def get_db() -> Database:
    global _db
    if _db is None:
        _db = Database()
    return _db


def set_db(db: Database) -> None:
    global _db
    _db = db


async def session_dep() -> AsyncIterator[AsyncSession]:
    async with get_db().sessionmaker() as session:
        yield session
