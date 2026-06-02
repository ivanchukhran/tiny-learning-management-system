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
    # Default to the PK so pagination has a stable sort; without any ordering
    # LIMIT/OFFSET pages can overlap or skip rows across requests.
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
