from __future__ import annotations

import os
from collections.abc import AsyncIterator

os.environ.setdefault("ENV", "test")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

import httpx  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.db import Database, set_db  # noqa: E402
from app.sandbox.runner import docker_available  # noqa: E402


@pytest.fixture
async def db() -> AsyncIterator[Database]:
    url = os.environ["DATABASE_URL"]
    database = Database.__new__(Database)
    if url.startswith("sqlite"):
        # one shared in-memory connection so every session sees the same tables
        database.engine = create_async_engine(url, poolclass=StaticPool, connect_args={"check_same_thread": False})
    else:
        database.engine = create_async_engine(url)
    database.sessionmaker = async_sessionmaker(database.engine, expire_on_commit=False)
    set_db(database)
    await database.create_all()
    yield database
    if not url.startswith("sqlite"):
        from app.db import Base

        async with database.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    await database.dispose()


@pytest.fixture
async def client(db: Database) -> AsyncIterator[httpx.AsyncClient]:
    from app.main import create_app

    app = create_app()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


async def login(client: httpx.AsyncClient, username: str = "candidate", password: str = "candidate-pass") -> dict:
    r = await client.post("/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


def auth(tokens: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


requires_docker = pytest.mark.skipif(not docker_available(), reason="Docker daemon not available")
