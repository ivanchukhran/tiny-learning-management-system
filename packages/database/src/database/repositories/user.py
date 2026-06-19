from collections.abc import Sequence
from typing import Any

from sqlalchemy import ColumnExpressionArgument, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User
from database.schemas import UserCreateDb, UserUpdateDb


async def create_user(session: AsyncSession, data: UserCreateDb) -> User:
    user = User(**data.model_dump())
    session.add(user)
    await session.flush()
    return user


async def create_or_promote_admin(
    session: AsyncSession,
    *,
    email: str,
    first_name: str | None = None,
    last_name: str | None = None,
    password_hash: str | None = None,
) -> tuple[User, bool]:
    """Ensure an admin exists for ``email`` (idempotent). Returns ``(user, created)``.

    - Existing user -> set ``is_admin=True``, return ``created=False``. The password
      is left untouched, so re-running never clobbers a password the admin changed.
    - Missing user -> create with ``is_admin=True``, return ``created=True``. This
      path requires ``first_name``, ``last_name`` and ``password_hash`` (raises
      ``ValueError`` otherwise).

    Pure persistence (ADR-018): the caller hashes the password and owns the
    transaction (no commit here).
    """
    user = await get_user(session, User.email == email)
    if user is not None:
        user.is_admin = True
        await session.flush()
        return user, False

    missing = [
        field
        for field, value in (
            ("first_name", first_name),
            ("last_name", last_name),
            ("password_hash", password_hash),
        )
        if value is None
    ]
    if missing:
        raise ValueError(f"creating a new admin requires: {', '.join(missing)}")
    assert first_name is not None and last_name is not None
    assert password_hash is not None

    user = User(
        first_name=first_name,
        last_name=last_name,
        email=email,
        password_hash=password_hash,
        is_admin=True,
    )
    session.add(user)
    await session.flush()
    return user, True


async def get_user(
    session: AsyncSession, *criteria: ColumnExpressionArgument[bool]
) -> User | None:
    statement = select(User).where(*criteria)
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def list_users(
    session: AsyncSession,
    *criteria: ColumnExpressionArgument[bool],
    order_by: ColumnExpressionArgument[Any] | None = None,
    limit: int = 100,
    offset: int = 0,
) -> Sequence[User]:
    if order_by is None:
        order_by = User.id
    statement = (
        select(User).where(*criteria).order_by(order_by).limit(limit).offset(offset)
    )
    result = await session.execute(statement)
    return result.scalars().all()


async def update_user(
    session: AsyncSession,
    values: UserUpdateDb,
    *criteria: ColumnExpressionArgument[bool],
) -> User | None:
    user = await get_user(session, *criteria)
    if user is None:
        return None
    for field, value in values.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    await session.flush()
    await session.refresh(user, ["updated_at"])
    return user


async def update_users(
    session: AsyncSession,
    values: UserUpdateDb,
    *criteria: ColumnExpressionArgument[bool],
) -> int:
    statement = (
        update(User).where(*criteria).values(**values.model_dump(exclude_unset=True))
    )
    result = await session.execute(statement)
    return result.rowcount  # pyright: ignore[reportAttributeAccessIssue]


async def delete_user(session, *criteria: ColumnExpressionArgument[bool]):
    statement = update(User).where(*criteria).values(deleted_at=func.now())
    result = await session.execute(statement)
    return result.rowcount


async def restore_user(
    session: AsyncSession, *criteria: ColumnExpressionArgument[bool]
) -> int:
    # include_deleted bypasses the global soft-delete filter; without it the
    # WHERE clause would gain `deleted_at IS NULL` and match zero deleted rows.
    statement = (
        update(User)
        .where(*criteria)
        .values(deleted_at=None)
        .execution_options(include_deleted=True)
    )
    result = await session.execute(statement)
    return result.rowcount  # pyright: ignore[reportAttributeAccessIssue]
