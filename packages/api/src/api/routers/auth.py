from database.models import User
from database.repositories import (
    create_session,
    delete_session,
    delete_user_sessions,
    get_user,
)
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.constants import SESSION_COOKIE_NAME, SESSION_MAX_LIFETIME
from api.dependencies import get_current_user, get_session
from api.schemas.auth import LoginRequest
from api.schemas.user import UserRead
from api.security import (
    generate_session_token,
    hash_password,
    hash_token,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# Precomputed hash to verify against when the email is unknown, so login takes
# the same time whether or not the account exists (no enumeration oracle).
_DUMMY_HASH = hash_password("dummy-password-for-timing")


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=int(SESSION_MAX_LIFETIME.total_seconds()),
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )


@router.post("/login", response_model=UserRead)
async def login(
    payload: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_session),
):
    user = await get_user(db, User.email == payload.email)
    password_hash = user.password_hash if user is not None else _DUMMY_HASH
    valid = verify_password(payload.password, password_hash)
    if user is None or not valid:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    token = generate_session_token()
    await create_session(db, user.id, hash_token(token))
    await db.commit()
    _set_session_cookie(response, token)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    db: AsyncSession = Depends(get_session),
):
    if session_token is not None:
        await delete_session(db, hash_token(session_token))
        await db.commit()
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    await delete_user_sessions(db, current_user.id)
    await db.commit()
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")


@router.get("/me", response_model=UserRead)
async def me(current_user: User = Depends(get_current_user)):
    return current_user
