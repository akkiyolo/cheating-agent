from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import DB, CurrentUser
from app.models import AssessmentSession
from app.sandbox.runner import DockerSandbox, SandboxResult, SandboxUnavailable, TestCase

router = APIRouter(prefix="/code", tags=["code"])


class RunIn(BaseModel):
    language: str = Field(pattern="^(python|cpp|java)$")
    code: str = Field(max_length=100_000)
    test_cases: list[TestCase] = Field(default_factory=list, max_length=50)
    # When given, the question's *visible* examples are used as tests (hidden tests are never run here).
    session_id: str | None = None
    question_uid: str | None = None


@router.post("/run", response_model=SandboxResult)
async def run(body: RunIn, db: DB, user: CurrentUser) -> SandboxResult:
    tests = list(body.test_cases)
    if body.session_id and body.question_uid:
        sess = await db.get(AssessmentSession, body.session_id)
        if sess is None or sess.user_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "session not found")
        q = next((q for q in sess.question_set if q["uid"] == body.question_uid), None)
        if q is None or "coding" not in q:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "coding question not found")
        tests = [TestCase(input=e["input"], output=e["output"]) for e in q["coding"]["examples"]]
    try:
        return await DockerSandbox().run(body.language, body.code, tests)
    except SandboxUnavailable as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"sandbox unavailable: {e}") from e
