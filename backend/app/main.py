from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


def create_app() -> FastAPI:
    app = FastAPI(title="Mock Assessment Platform", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for r in (auth.router, assessments.router, code.router):
        app.include_router(r)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
