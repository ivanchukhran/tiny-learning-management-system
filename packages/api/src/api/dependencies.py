from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from database.connection import get_sessionmaker
from database.models import User
from database.repositories import get_valid_session, touch_session
from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.constants import (
    SESSION_BUMP_THRESHOLD,
    SESSION_COOKIE_NAME,
    SESSION_IDLE_WINDOW,
    SESSION_MAX_LIFETIME,
)
from api.security import hash_token


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async_session = get_sessionmaker()
    async with async_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def get_current_user(
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    db: AsyncSession = Depends(get_session),
) -> User:
    if session_token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    now = datetime.now(timezone.utc)
    session = await get_valid_session(
        db,
        hash_token(session_token),
        idle_cutoff=now - SESSION_IDLE_WINDOW,
        absolute_cutoff=now - SESSION_MAX_LIFETIME,
    )
    if session is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired session")

    # Lazy idle-bump: persist activity only when last_seen_at is stale enough,
    # committed on its own so it survives even read-only (non-committing) endpoints.
    if now - session.last_seen_at > SESSION_BUMP_THRESHOLD:
        await touch_session(db, session.id)
        await db.commit()

    return session.user
