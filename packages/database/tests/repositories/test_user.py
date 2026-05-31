import pytest
from database.models.user import User
from database.repositories.user import create_user
from database.schemas.user import UserCreate
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError


async def test_create_user_persists_row(session):
    data = UserCreate(
        first_name="Ada",
        last_name="Lovelace",
        email="ada@example.com",
        password_hash="hashed-value",
    )

    user = await create_user(session, data)

    assert user.id is not None  # flush() populated the PK
    assert user.created_at is not None  # server_default fetched via RETURNING
    assert user.updated_at is not None  # the same

    fetched = await session.scalar(select(User).where(User.id == user.id))
    assert fetched is not None
    assert fetched.email == "ada@example.com"


async def test_create_user_duplicate_email_raises(session):
    base = dict(first_name="A", last_name="B", password_hash="h")
    await create_user(session, UserCreate(email="dup@example.com", **base))

    with pytest.raises(IntegrityError):
        await create_user(session, UserCreate(email="dup@example.com", **base))
