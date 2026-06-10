from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager

from database.models import Session


async def create_session(db: AsyncSession, user_id: int, token_hash: str) -> Session:
    session = Session(user_id=user_id, hash=token_hash)
    db.add(session)
    await db.flush()
    return session


async def get_valid_session(
    db: AsyncSession,
    token_hash: str,
    *,
    idle_cutoff: datetime,
    absolute_cutoff: datetime,
) -> Session | None:
    # INNER join to User (not joinedload's outer join) so the global soft-delete
    # filter on User drops the whole row for a deleted user -- the session simply
    # doesn't resolve. contains_eager populates Session.user from that join.
    # Validity windows arrive as derived cutoffs; the policy lives in the api layer.
    statement = (
        select(Session)
        .join(Session.user)
        .options(contains_eager(Session.user))
        .where(
            Session.hash == token_hash,
            Session.last_seen_at > idle_cutoff,
            Session.created_at > absolute_cutoff,
        )
    )
    result = await db.execute(statement)
    return result.scalar_one_or_none()


async def touch_session(db: AsyncSession, session_id: int) -> None:
    # Lazy-bump the idle anchor; the caller decides whether it is stale enough to
    # write. The absolute ceiling (created_at) is never touched.
    statement = (
        update(Session).where(Session.id == session_id).values(last_seen_at=func.now())
    )
    await db.execute(statement)


async def delete_session(db: AsyncSession, token_hash: str) -> int:
    # Single logout: drop one row by its hash.
    statement = delete(Session).where(Session.hash == token_hash)
    result = await db.execute(statement)
    return result.rowcount  # pyright: ignore[reportAttributeAccessIssue]


async def delete_user_sessions(db: AsyncSession, user_id: int) -> int:
    # "Log out everywhere" / password change: drop every session for the user.
    statement = delete(Session).where(Session.user_id == user_id)
    result = await db.execute(statement)
    return result.rowcount  # pyright: ignore[reportAttributeAccessIssue]
