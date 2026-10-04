from __future__ import annotations

import httpx

from app.models import AssessmentSession
from app.sandbox.runner import SandboxResult
from app.services import assessment_service as svc
from tests.conftest import auth, login


async def _start(client: httpx.AsyncClient, tokens: dict) -> str:
    r = await client.get("/assessments", headers=auth(tokens))
    assert r.status_code == 200
    aid = r.json()[0]["id"]
    r = await client.post(f"/assessments/{aid}/start", headers=auth(tokens))
    assert r.status_code == 200
    return r.json()["session_id"]


async def test_auth_flow(client: httpx.AsyncClient) -> None:
    r = await client.post("/auth/login", json={"username": "candidate", "password": "nope"})
    assert r.status_code == 401
    tokens = await login(client)
    r = await client.get("/auth/me", headers=auth(tokens))
    assert r.json()["role"] == "CANDIDATE"
    r = await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 200
    # refresh tokens rotate: the old one is single-use
    r = await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 401
    assert (await client.get("/assessments")).status_code == 401


async def test_full_session_flow(client: httpx.AsyncClient, db, monkeypatch) -> None:
    async def fake_run(self, language, code, tests):  # coding graded without Docker here
        n = len(tests)
        ok = "correct" in code
        return SandboxResult(language=language, compiled=True, passed=ok, tests_passed=n if ok else 0,
                             tests_failed=0 if ok else n)

    monkeypatch.setattr("app.sandbox.runner.DockerSandbox.run", fake_run)
    tokens = await login(client)
    sid = await _start(client, tokens)
    # starting again resumes the same in-progress session
    assert await _start(client, tokens) == sid

    r = await client.get(f"/sessions/{sid}", headers=auth(tokens))
    assert r.json()["status"] == "in_progress" and r.json()["total"] == 21
    qs = (await client.get(f"/sessions/{sid}/questions", headers=auth(tokens))).json()["questions"]
    assert all("answer_key" not in q for q in qs)

    # answer every question correctly using the server-side keys (test-only access)
    async with db.sessionmaker() as s:
        sess = await s.get(AssessmentSession, sid)
        keyed = {q["uid"]: q for q in sess.question_set}
    for q in qs:
        k = keyed[q["uid"]]["answer_key"]
        if k["type"] == "choice":
            resp = {"option_ids": k["correct"]} if k["multi"] else {"option_id": k["correct"][0]}
        elif k["type"] == "numeric":
            resp = {"value": str(k["value"])}
        elif k["type"] == "text":
            resp = {"value": k["accepted"][0]}
        else:
            resp = {"language": "python", "code": "print('correct')"}
        r = await client.post(f"/sessions/{sid}/answers", headers=auth(tokens),
                              json={"question_uid": q["uid"], "response": resp})
        assert r.status_code == 200, r.text
    # autosave overwrite bumps revision
    r = await client.post(f"/sessions/{sid}/answers", headers=auth(tokens),
                          json={"question_uid": qs[0]["uid"], "response": {"value": "x"}})
    assert r.json()["revision"] == 2
    r = await client.post(f"/sessions/{sid}/answers", headers=auth(tokens),
                          json={"question_uid": qs[0]["uid"], "response": _restore(keyed[qs[0]["uid"]])})

    r = await client.post(f"/sessions/{sid}/review", headers=auth(tokens),
                          json={"question_uid": qs[1]["uid"], "marked": True})
    assert r.json()["review_marks"] == [qs[1]["uid"]]

    assert (await client.get(f"/sessions/{sid}/results", headers=auth(tokens))).status_code == 409
    r = await client.post(f"/sessions/{sid}/submit", headers=auth(tokens))
    assert r.json()["status"] == "submitted"
    res = (await client.get(f"/sessions/{sid}/results", headers=auth(tokens))).json()
    assert res["score"] == res["max_score"] == 25.0
    assert res["accuracy"] == 1.0
    # no further answers after submission
    r = await client.post(f"/sessions/{sid}/answers", headers=auth(tokens),
                          json={"question_uid": qs[0]["uid"], "response": {"value": "1"}})
    assert r.status_code == 409


def _restore(q: dict) -> dict:
    k = q["answer_key"]
    if k["type"] == "choice":
        return {"option_ids": k["correct"]} if k["multi"] else {"option_id": k["correct"][0]}
    if k["type"] == "numeric":
        return {"value": str(k["value"])}
    if k["type"] == "text":
        return {"value": k["accepted"][0]}
    return {"language": "python", "code": "print('correct')"}


async def test_other_users_cannot_read_session(client: httpx.AsyncClient, db) -> None:
    tokens = await login(client)
    sid = await _start(client, tokens)
    async with db.sessionmaker() as s:
        from app.models import Role
        from app.services.auth import ensure_user

        await ensure_user(s, "mallory", "pw-mallory", Role.CANDIDATE)
        await s.commit()
    other = await login(client, "mallory", "pw-mallory")
    assert (await client.get(f"/sessions/{sid}", headers=auth(other))).status_code == 403
    researcher = await login(client, "researcher", "researcher-pass")
    assert (await client.get(f"/sessions/{sid}", headers=auth(researcher))).status_code == 200


async def test_deadline_expiry_autosubmits(client: httpx.AsyncClient, db) -> None:
    svc.set_preset("candidate", duration_s=1)
    tokens = await login(client)
    sid = await _start(client, tokens)
    async with db.sessionmaker() as s:
        from datetime import UTC, datetime, timedelta

        sess = await s.get(AssessmentSession, sid)
        sess.deadline = datetime.now(UTC) - timedelta(seconds=1)
        await s.commit()
    r = await client.get(f"/sessions/{sid}", headers=auth(tokens))
    assert r.json()["status"] == "expired"


async def test_network_failure_fault(client: httpx.AsyncClient) -> None:
    svc.set_preset("candidate", faults=["NETWORK_FAILURE"])
    tokens = await login(client)
    sid = await _start(client, tokens)
    qs = (await client.get(f"/sessions/{sid}/questions", headers=auth(tokens))).json()["questions"]
    codes = []
    for q in qs[:5]:
        r = await client.post(f"/sessions/{sid}/answers", headers=auth(tokens),
                              json={"question_uid": q["uid"], "response": {"value": "1"}})
        codes.append(r.status_code)
    assert codes == [200, 200, 200, 503, 200]
    r = await client.post(f"/sessions/{sid}/answers", headers=auth(tokens),
                          json={"question_uid": qs[3]["uid"], "response": {"value": "1"}})
    assert r.status_code == 200  # retry succeeds


async def test_image_endpoint(client: httpx.AsyncClient) -> None:
    tokens = await login(client)
    sid = await _start(client, tokens)
    qs = (await client.get(f"/sessions/{sid}/questions", headers=auth(tokens))).json()["questions"]
    img = next(q for q in qs if q["kind"] == "image")
    r = await client.get(f"/sessions/{sid}/questions/{img['uid']}/image.png", headers=auth(tokens))
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
