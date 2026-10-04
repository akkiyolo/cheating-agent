from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import RefreshToken, Role, User

_hasher = PasswordHash.recommended()
ALGORITHM = "HS256"


class AuthError(Exception):
    pass


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password, password_hash)
    except Exception:
        return False


def create_access_token(user: User) -> str:
    s = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": user.id,
        "username": user.username,
        "role": user.role.value,
        "iat": now,
        "exp": now + timedelta(minutes=s.access_token_minutes),
        "typ": "access",
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as e:
        raise AuthError("token expired") from e
    except jwt.InvalidTokenError as e:
        raise AuthError("invalid token") from e
    if payload.get("typ") != "access":
        raise AuthError("wrong token type")
    return payload


def _hash_refresh(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def issue_refresh_token(db: AsyncSession, user: User) -> str:
    token = secrets.token_urlsafe(48)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=_hash_refresh(token),
            expires_at=datetime.now(UTC) + timedelta(days=get_settings().refresh_token_days),
        )
    )
    await db.flush()
    return token


async def rotate_refresh_token(db: AsyncSession, token: str) -> tuple[User, str]:
    row = (
        await db.execute(select(RefreshToken).where(RefreshToken.token_hash == _hash_refresh(token)))
    ).scalar_one_or_none()
    if row is None or row.revoked:
        raise AuthError("invalid refresh token")
    expires = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=UTC)
    if expires < datetime.now(UTC):
        raise AuthError("refresh token expired")
    row.revoked = True
    user = await db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise AuthError("user inactive")
    return user, await issue_refresh_token(db, user)


async def authenticate(db: AsyncSession, username: str, password: str) -> User:
    user = (await db.execute(select(User).where(User.username == username))).scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        raise AuthError("invalid credentials")
    return user


async def ensure_user(db: AsyncSession, username: str, password: str, role: Role) -> User:
    user = (await db.execute(select(User).where(User.username == username))).scalar_one_or_none()
    if user is None:
        user = User(username=username, password_hash=hash_password(password), role=role)
        db.add(user)
        await db.flush()
    return user
