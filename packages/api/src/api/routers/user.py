from enum import Enum

from database.models import User
from database.repositories import create_user, get_user
from database.repositories import delete_user_sessions
from database.repositories.user import (
    delete_user,
    list_users,
    restore_user,
    update_user,
)
from database.schemas import UserCreateDb, UserUpdateDb
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_session
from api.schemas.user import PasswordUpdate, UserCreate, UserRead, UserUpdate
from core.security import hash_password

router = APIRouter()


class SortDirection(str, Enum):
    asc = "asc"
    desc = "desc"


class UserSortField(str, Enum):
    """Whitelist of columns clients may sort by. FastAPI validates the query
    value against these names (invalid -> 422). Each value equals a real User
    column name and is resolved with getattr(User, value), so there is no
    separate name->column map to keep in sync."""

    id = "id"
    email = "email"
    first_name = "first_name"
    last_name = "last_name"
    created_at = "created_at"


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user_endpoint(
    payload: UserCreate, session: AsyncSession = Depends(get_session)
):
    dto = UserCreateDb(
        **payload.model_dump(exclude={"password"}),
        password_hash=hash_password(payload.password),
    )
    try:
        user = await create_user(session, dto)
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    return user


@router.get("/users", response_model=list[UserRead])
async def list_users_endpoint(
    session: AsyncSession = Depends(get_session),
    sort: UserSortField = UserSortField.id,
    order: SortDirection = SortDirection.asc,
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    column = getattr(User, sort.value)
    order_by = column.desc() if order is SortDirection.desc else column.asc()
    return await list_users(session, order_by=order_by, limit=limit, offset=offset)


@router.get("/users/{user_id}", response_model=UserRead)
async def get_user_endpoint(user_id: int, session=Depends(get_session)):
    user = await get_user(session, User.id == user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user


@router.patch("/users/{user_id}", response_model=UserRead)
async def update_user_endpoint(
    user_id: int,
    payload: UserUpdate,
    session: AsyncSession = Depends(get_session),
):
    dto = UserUpdateDb(**payload.model_dump(exclude_unset=True))
    try:
        user = await update_user(session, dto, User.id == user_id)
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user


@router.put("/users/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
async def update_password_endpoint(
    user_id: int,
    payload: PasswordUpdate,
    session: AsyncSession = Depends(get_session),
):
    dto = UserUpdateDb(password_hash=hash_password(payload.password))
    user = await update_user(session, dto, User.id == user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    # A password change invalidates every existing session for the user (ADR-019):
    # forces re-login everywhere, locking out anyone holding a stolen session.
    await delete_user_sessions(session, user_id)
    await session.commit()


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_endpoint(
    user_id: int,
    session: AsyncSession = Depends(get_session),
):
    deleted = await delete_user(session, User.id == user_id)
    if deleted == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    await session.commit()


@router.post("/users/{user_id}/restore", response_model=UserRead)
async def restore_user_endpoint(
    user_id: int,
    session: AsyncSession = Depends(get_session),
):
    restored = await restore_user(session, User.id == user_id)
    if restored == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    # The row is now visible to the global filter (deleted_at is NULL), so a
    # normal get_user re-reads it for the response body.
    user = await get_user(session, User.id == user_id)
    await session.commit()
    return user
