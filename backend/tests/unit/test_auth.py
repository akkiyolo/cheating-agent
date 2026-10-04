import time

import jwt
import pytest

from app.config import get_settings
from app.models import Role, User
from app.services.auth import AuthError, create_access_token, decode_access_token, hash_password, verify_password


def test_password_hashing() -> None:
    h = hash_password("s3cret")
    assert h != "s3cret"
    assert verify_password("s3cret", h)
    assert not verify_password("wrong", h)
    assert not verify_password("s3cret", "not-a-hash")


def test_access_token_roundtrip_and_tamper() -> None:
    user = User(id="u1", username="alice", password_hash="x", role=Role.RESEARCHER)
    tok = create_access_token(user)
    payload = decode_access_token(tok)
    assert payload["sub"] == "u1" and payload["role"] == "RESEARCHER"
    with pytest.raises(AuthError):
        decode_access_token(tok[:-2] + ("A" if tok[-1] != "A" else "B") + tok[-1])


def test_expired_and_wrong_type_tokens_rejected() -> None:
    secret = get_settings().jwt_secret
    expired = jwt.encode({"sub": "u1", "typ": "access", "exp": int(time.time()) - 10}, secret, algorithm="HS256")
    with pytest.raises(AuthError, match="expired"):
        decode_access_token(expired)
    wrong = jwt.encode({"sub": "u1", "typ": "refresh", "exp": int(time.time()) + 60}, secret, algorithm="HS256")
    with pytest.raises(AuthError):
        decode_access_token(wrong)
