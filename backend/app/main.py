from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import assessments, auth, code
from app.config import get_settings
from app.db import get_db
from app.services.assessment_service import seed_database


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    s = get_settings()
    db = get_db()
    if s.env != "prod":
        await db.create_all()  # prod uses `alembic upgrade head`
    async with db.sessionmaker() as session:
        await seed_database(session, admin_password=s.admin_password, researcher_password=s.researcher_password,
                            candidate_password=s.candidate_password, duration_s=s.assessment_duration_s)
    yield
    await db.dispose()


def _mount_frontend(app: FastAPI, dist: Path) -> None:
    """Serve the built single-page app: static assets, real files, and index.html for client-side routes."""
    index = dist / "index.html"
    if not index.is_file():
        raise RuntimeError(f"FRONTEND_DIST={dist} does not contain index.html")
    root = dist.resolve()
    app.mount("/assets", StaticFiles(directory=root / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:  # sync: filesystem checks run in the threadpool
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Not Found")
        candidate = (root / path).resolve()
        if path and candidate.is_relative_to(root) and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="Mock Assessment Platform", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Standalone API: routes at "/". Single-image deployment: API under "/api", front end at "/".
    prefix = "/api" if s.frontend_dist else ""
    for r in (auth.router, assessments.router, code.router):
        app.include_router(r, prefix=prefix)

    @app.get(f"{prefix}/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    if s.frontend_dist:
        _mount_frontend(app, Path(s.frontend_dist))
    return app


app = create_app()
