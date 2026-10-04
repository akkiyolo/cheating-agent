from __future__ import annotations

import asyncio
import random
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models import Answer, Assessment, AssessmentQuestion, AssessmentSession, Question, Role, User
from app.sandbox.runner import DockerSandbox, SandboxUnavailable, TestCase
from app.services import question_bank as qb
from app.services.auth import ensure_user
from app.services.grading import grade_static

DEFAULT_SLUG = "general-aptitude"

# Fault classes handled by the assessment (server or client side). Agent-side faults live in the agent.
SITE_FAULTS = {"STALE_DOM", "DELAYED_RENDER", "MISSING_ELEMENT", "NETWORK_DELAY", "NETWORK_FAILURE",
               "UNEXPECTED_MODAL", "PAGE_RELOAD"}

# Per-user preset applied to the *next* session the user starts (researcher-controlled).
_presets: dict[str, dict[str, Any]] = {}


def set_preset(username: str, *, faults: list[str] | None = None, seed: int | None = None,
               fresh: bool = True, duration_s: int | None = None) -> None:
    _presets[username] = {"faults": [f for f in (faults or []) if f in SITE_FAULTS], "seed": seed,
                          "fresh": fresh, "duration_s": duration_s}


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


async def seed_database(db: AsyncSession, *, admin_password: str = "admin-pass",
                        researcher_password: str = "researcher-pass", candidate_password: str = "candidate-pass",
                        duration_s: int = 3600) -> None:
    await ensure_user(db, "admin", admin_password, Role.ADMIN)
    await ensure_user(db, "researcher", researcher_password, Role.RESEARCHER)
    await ensure_user(db, "candidate", candidate_password, Role.CANDIDATE)
    for tpl in qb.TEMPLATES.values():
        if await db.get(Question, tpl.id) is None:
            db.add(Question(id=tpl.id, kind=tpl.kind, topic=tpl.topic, difficulty=tpl.difficulty,
                            parametric=tpl.parametric))
    a = (await db.execute(select(Assessment).where(Assessment.slug == DEFAULT_SLUG))).scalar_one_or_none()
    if a is None:
        a = Assessment(slug=DEFAULT_SLUG, title="General Aptitude & Programming Assessment",
                       description="21 questions: multiple choice, numerical, multi-select, short text, image, "
                                   "table and coding.",
                       duration_s=duration_s, composition=dict(qb.DEFAULT_COMPOSITION))
        db.add(a)
        await db.flush()
        for tpl in qb.TEMPLATES.values():
            db.add(AssessmentQuestion(assessment_id=a.id, question_id=tpl.id))
    await db.commit()


async def start_session(db: AsyncSession, assessment: Assessment, user: User) -> AssessmentSession:
    preset = _presets.pop(user.username, None)
    existing = (
        await db.execute(
            select(AssessmentSession).where(AssessmentSession.user_id == user.id,
                                            AssessmentSession.assessment_id == assessment.id,
                                            AssessmentSession.status == "in_progress")
        )
    ).scalars().all()
    if existing and not (preset and preset.get("fresh")):
        return existing[-1]
    for s in existing:  # a fresh research run abandons stale sessions
        s.status = "abandoned"
    pool = (await db.execute(select(AssessmentQuestion.question_id)
                             .where(AssessmentQuestion.assessment_id == assessment.id))).scalars().all()
    seed = (preset or {}).get("seed")
    if seed is None:
        seed = random.SystemRandom().randint(1, 2**31 - 1)
    qset = qb.generate_question_set(seed, assessment.composition, list(pool), assessment.shuffle_questions,
                                    assessment.shuffle_options)
    duration = (preset or {}).get("duration_s") or assessment.duration_s
    now = datetime.now(UTC)
    sess = AssessmentSession(assessment_id=assessment.id, user_id=user.id, seed=seed, started_at=now,
                             deadline=now + timedelta(seconds=duration), question_set=qset, review_marks=[],
                             faults=(preset or {}).get("faults", []), fault_state={})
    db.add(sess)
    await db.commit()
    return sess


def remaining_seconds(sess: AssessmentSession) -> float:
    return max(0.0, (_aware(sess.deadline) - datetime.now(UTC)).total_seconds())


async def load_answers(db: AsyncSession, sess: AssessmentSession) -> dict[str, Answer]:
    rows = (await db.execute(select(Answer).where(Answer.session_id == sess.id))).scalars().all()
    return {a.question_uid: a for a in rows}


class SaveFault(Exception):
    pass


async def save_answer(db: AsyncSession, sess: AssessmentSession, uid: str, response: dict[str, Any]) -> Answer:
    if uid not in {q["uid"] for q in sess.question_set}:
        raise KeyError(uid)
    faults = set(sess.faults or [])
    if "NETWORK_DELAY" in faults:
        await asyncio.sleep(1.5)
    if "NETWORK_FAILURE" in faults:
        st = dict(sess.fault_state or {})
        saved_uids = st.setdefault("saved_uids", [])
        if uid not in saved_uids:
            saved_uids.append(uid)
        # The first save attempt for the 4th distinct question fails once with a 503.
        if len(saved_uids) == 4 and not st.get("network_failure_fired"):
            st["network_failure_fired"] = True
            sess.fault_state = st
            flag_modified(sess, "fault_state")
            await db.commit()
            raise SaveFault("injected network failure")
        sess.fault_state = st
        flag_modified(sess, "fault_state")
    ans = (await db.execute(select(Answer).where(Answer.session_id == sess.id, Answer.question_uid == uid))
           ).scalar_one_or_none()
    if ans is None:
        ans = Answer(session_id=sess.id, question_uid=uid, response=response)
        db.add(ans)
    else:
        ans.response = response
        ans.revision += 1
        flag_modified(ans, "response")
    await db.commit()
    return ans


async def grade_session(db: AsyncSession, sess: AssessmentSession, sandbox: DockerSandbox | None = None) -> None:
    answers = await load_answers(db, sess)
    sandbox = sandbox or DockerSandbox()
    total = max_total = 0.0
    detail: list[dict[str, Any]] = []
    for i, q in enumerate(sess.question_set):
        a = answers.get(q["uid"])
        pts_max = float(q.get("points", 1.0))
        max_total += pts_max
        entry: dict[str, Any] = {"number": i + 1, "uid": q["uid"], "kind": q["kind"], "answered": a is not None,
                                 "points_max": pts_max}
        if q["kind"] == "coding":
            ok, pts = False, 0.0
            info: dict[str, Any] = {}
            resp = a.response if a else None
            if resp and resp.get("code", "").strip():
                tests = [TestCase(**t) for t in q["answer_key"]["tests"]]
                try:
                    r = await sandbox.run(resp.get("language", "python"), resp["code"], tests)
                    frac = r.tests_passed / len(tests) if tests else 0.0
                    ok, pts = r.passed, round(pts_max * frac, 3)
                    info = {"tests_passed": r.tests_passed, "tests_total": len(tests), "compiled": r.compiled}
                except SandboxUnavailable as e:
                    info = {"error": f"sandbox unavailable: {e}"}
            entry.update(correct=ok, points=pts, **info)
        else:
            ok, pts = grade_static(q, a.response if a else None)
            entry.update(correct=ok, points=pts)
        if a is not None:
            a.correct, a.points = entry["correct"], entry["points"]
        total += entry["points"]
        detail.append(entry)
    sess.score, sess.max_score = round(total, 3), max_total
    by_kind: dict[str, dict[str, float]] = {}
    for item in detail:
        k = by_kind.setdefault(item["kind"], {"correct": 0, "total": 0, "points": 0.0, "points_max": 0.0})
        k["total"] += 1
        k["correct"] += 1 if item["correct"] else 0
        k["points"] += item["points"]
        k["points_max"] += item["points_max"]
    sess.result_detail = {"questions": detail, "by_kind": by_kind,
                          "accuracy": sum(1 for item in detail if item["correct"]) / len(detail) if detail else 0}
    await db.commit()


async def submit(db: AsyncSession, sess: AssessmentSession, *, expired: bool = False) -> AssessmentSession:
    if sess.status in ("submitted", "expired"):
        return sess
    sess.status = "expired" if expired else "submitted"
    sess.submitted_at = datetime.now(UTC)
    await db.commit()
    await grade_session(db, sess)
    return sess


async def enforce_deadline(db: AsyncSession, sess: AssessmentSession) -> AssessmentSession:
    if sess.status == "in_progress" and remaining_seconds(sess) <= 0:
        await submit(db, sess, expired=True)
    return sess
