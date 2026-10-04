"""Single-image deployment mode (FRONTEND_DIST set): SPA at "/", API under "/api"."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import httpx
import pytest

from app.config import Settings, get_settings
from app.db import Database


@pytest.fixture
def dist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><div id=root></div>", encoding="utf-8")
    (tmp_path / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    monkeypatch.setenv("FRONTEND_DIST", str(tmp_path))
    get_settings.cache_clear()
    yield tmp_path
    monkeypatch.delenv("FRONTEND_DIST")
    get_settings.cache_clear()


@pytest.fixture
async def spa_client(db: Database, dist: Path) -> AsyncIterator[httpx.AsyncClient]:
    from app.main import create_app

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app), httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_api_is_served_under_api_prefix(spa_client: httpx.AsyncClient) -> None:
    assert (await spa_client.get("/api/health")).json() == {"status": "ok"}
    r = await spa_client.post("/api/auth/login", json={"username": "candidate", "password": "candidate-pass"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    r = await spa_client.get("/api/assessments", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200 and r.json()[0]["slug"] == "general-aptitude"


async def test_spa_routes_and_static_files(spa_client: httpx.AsyncClient) -> None:
    for path in ("/", "/login", "/assessment", "/results"):
        r = await spa_client.get(path)
        assert r.status_code == 200 and "id=root" in r.text, path
    assert (await spa_client.get("/assets/app.js")).text == "console.log(1)"
    assert (await spa_client.get("/favicon.svg")).text == "<svg/>"


async def test_unknown_api_path_is_404_not_index(spa_client: httpx.AsyncClient) -> None:
    r = await spa_client.get("/api/nope")
    assert r.status_code == 404
    assert "id=root" not in r.text


async def test_path_traversal_falls_back_to_index(spa_client: httpx.AsyncClient) -> None:
    r = await spa_client.get("/..%2F..%2Fpyproject.toml")
    assert r.status_code == 200 and "id=root" in r.text


def test_hosting_database_urls_get_async_driver() -> None:
    for url in ("postgres://u:p@h:5432/db", "postgresql://u:p@h:5432/db"):
        assert Settings(database_url=url).database_url == "postgresql+asyncpg://u:p@h:5432/db"
    assert Settings(database_url="sqlite+aiosqlite:///x.db").database_url == "sqlite+aiosqlite:///x.db"


def test_prod_requires_database_url_and_real_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    db = "postgres://u:p@h/db"
    with pytest.raises(ValueError, match="DATABASE_URL is not set.*JWT_SECRET"):
        Settings(env="prod")
    with pytest.raises(ValueError, match="JWT_SECRET"):
        Settings(env="prod", database_url=db, jwt_secret="short")
    with pytest.raises(ValueError, match="DATABASE_URL"):
        Settings(env="prod", jwt_secret="x" * 40)
    assert Settings(env="prod", database_url=db, jwt_secret="x" * 40).env == "prod"
