from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.models import Assessment, AssessmentSession, Role
from app.services import assessment_service as svc
from app.services import images
from app.services.question_bank import public_view

router = APIRouter(tags=["assessment"])


async def _own_session(db: DB, user: CurrentUser, session_id: str) -> AssessmentSession:
    sess = await db.get(AssessmentSession, session_id)
    if sess is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "session not found")
    if sess.user_id != user.id and user.role not in (Role.ADMIN, Role.RESEARCHER):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not your session")
    return await svc.enforce_deadline(db, sess)


@router.get("/assessments")
async def list_assessments(db: DB, user: CurrentUser) -> list[dict[str, Any]]:
    rows = (await db.execute(select(Assessment))).scalars().all()
    return [{"id": a.id, "slug": a.slug, "title": a.title, "description": a.description,
             "duration_s": a.duration_s, "question_count": sum(a.composition.values())} for a in rows]


@router.post("/assessments/{assessment_id}/start")
async def start(assessment_id: str, db: DB, user: CurrentUser) -> dict[str, Any]:
    a = await db.get(Assessment, assessment_id)
    if a is None:
        a = (await db.execute(select(Assessment).where(Assessment.slug == assessment_id))).scalar_one_or_none()
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "assessment not found")
    sess = await svc.start_session(db, a, user)
    return {"session_id": sess.id}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, db: DB, user: CurrentUser) -> dict[str, Any]:
    sess = await _own_session(db, user, session_id)
    a = await db.get(Assessment, sess.assessment_id)
    answers = await svc.load_answers(db, sess)
    return {
        "id": sess.id,
        "assessment": {"id": a.id, "title": a.title} if a else None,
        "status": sess.status,
        "remaining_s": svc.remaining_seconds(sess),
        "deadline": sess.deadline.isoformat(),
        "total": len(sess.question_set),
        "answered": len(answers),
        "review_marks": sess.review_marks or [],
        "faults": sess.faults or [],
    }


@router.get("/sessions/{session_id}/questions")
async def get_questions(session_id: str, db: DB, user: CurrentUser) -> dict[str, Any]:
    sess = await _own_session(db, user, session_id)
    if sess.status != "in_progress":
        raise HTTPException(status.HTTP_409_CONFLICT, f"session is {sess.status}")
    answers = await svc.load_answers(db, sess)
    n = len(sess.question_set)
    return {
        "questions": [public_view(q, i, n) for i, q in enumerate(sess.question_set)],
        "responses": {uid: {"response": a.response, "revision": a.revision} for uid, a in answers.items()},
    }


@router.get("/sessions/{session_id}/questions/{uid}/image.png")
async def question_image(session_id: str, uid: str, db: DB, user: CurrentUser) -> Response:
    sess = await _own_session(db, user, session_id)
    q = next((q for q in sess.question_set if q["uid"] == uid), None)
    if q is None or "image" not in q:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no image")
    return Response(images.render(q["image"]), media_type="image/png", headers={"Cache-Control": "private"})


class AnswerIn(BaseModel):
    question_uid: str
    response: dict[str, Any]


@router.post("/sessions/{session_id}/answers")
async def post_answer(session_id: str, body: AnswerIn, db: DB, user: CurrentUser) -> dict[str, Any]:
    sess = await _own_session(db, user, session_id)
    if sess.status != "in_progress":
        raise HTTPException(status.HTTP_409_CONFLICT, f"session is {sess.status}")
    try:
        ans = await svc.save_answer(db, sess, body.question_uid, body.response)
    except KeyError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown question") from e
    except svc.SaveFault as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Temporary network failure, please retry") from e
    return {"saved": True, "question_uid": ans.question_uid, "revision": ans.revision}


class ReviewIn(BaseModel):
    question_uid: str
    marked: bool


@router.post("/sessions/{session_id}/review")
async def mark_review(session_id: str, body: ReviewIn, db: DB, user: CurrentUser) -> dict[str, Any]:
    sess = await _own_session(db, user, session_id)
    marks = set(sess.review_marks or [])
    if body.marked:
        marks.add(body.question_uid)
    else:
        marks.discard(body.question_uid)
    sess.review_marks = sorted(marks)
    await db.commit()
    return {"review_marks": sess.review_marks}


@router.post("/sessions/{session_id}/submit")
async def submit(session_id: str, db: DB, user: CurrentUser) -> dict[str, Any]:
    sess = await _own_session(db, user, session_id)
    sess = await svc.submit(db, sess)
    return {"status": sess.status, "submitted_at": sess.submitted_at.isoformat() if sess.submitted_at else None}


@router.get("/sessions/{session_id}/results")
async def results(session_id: str, db: DB, user: CurrentUser) -> dict[str, Any]:
    sess = await _own_session(db, user, session_id)
    if sess.status not in ("submitted", "expired"):
        raise HTTPException(status.HTTP_409_CONFLICT, "results available after submission")
    detail = sess.result_detail or {}
    return {
        "status": sess.status,
        "score": sess.score,
        "max_score": sess.max_score,
        "accuracy": detail.get("accuracy"),
        "by_kind": detail.get("by_kind"),
        "questions": [{k: v for k, v in q.items() if k != "uid"} for q in detail.get("questions", [])],
    }
