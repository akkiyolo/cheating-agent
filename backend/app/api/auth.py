from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.api.deps import DB, CurrentUser
from app.services.auth import (
    AuthError,
    authenticate,
    create_access_token,
    issue_refresh_token,
    rotate_refresh_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: str
    username: str


class RefreshIn(BaseModel):
    refresh_token: str


@router.post("/login", response_model=TokenOut)
async def login(body: LoginIn, db: DB) -> TokenOut:
    try:
        user = await authenticate(db, body.username, body.password)
    except AuthError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password") from e
    refresh = await issue_refresh_token(db, user)
    await db.commit()
    return TokenOut(access_token=create_access_token(user), refresh_token=refresh, role=user.role.value,
                    username=user.username)


@router.post("/refresh", response_model=TokenOut)
async def refresh(body: RefreshIn, db: DB) -> TokenOut:
    try:
        user, new_refresh = await rotate_refresh_token(db, body.refresh_token)
    except AuthError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e)) from e
    await db.commit()
    return TokenOut(access_token=create_access_token(user), refresh_token=new_refresh, role=user.role.value,
                    username=user.username)


@router.get("/me")
async def me(user: CurrentUser) -> dict:
    return {"id": user.id, "username": user.username, "role": user.role.value}
