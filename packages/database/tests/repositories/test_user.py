import pytest
from database.models.user import User
from database.repositories.user import (
    create_user,
    delete_user,
    get_user,
    list_users,
    restore_user,
    update_user,
    update_users,
)
from database.schemas.user import UserCreateDb, UserUpdateDb
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, MultipleResultsFound


async def test_create_user_persists_row(session):
    data = UserCreateDb(
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
    await create_user(session, UserCreateDb(email="dup@example.com", **base))

    with pytest.raises(IntegrityError):
        await create_user(session, UserCreateDb(email="dup@example.com", **base))


async def test_get_user_by_id_returns_match(session):
    base = dict(first_name="Ada", last_name="Lovelace", password_hash="hashed-value")
    user = await create_user(session, UserCreateDb(email="ada@example.com", **base))
    fetched = await get_user(session, User.id == user.id)
    assert fetched is not None
    assert fetched.email == "ada@example.com"


async def test_get_user_by_email_returns_match(session):
    base = dict(first_name="Ada", last_name="Lovelace", password_hash="hashed-value")
    user = await create_user(session, UserCreateDb(email="ada@example.com", **base))
    fetched = await get_user(session, User.email == "ada@example.com")
    assert fetched is not None
    assert fetched.id == user.id


async def test_get_user_returns_no_match(session):
    base = dict(first_name="Ada", last_name="Lovelace", password_hash="hashed-value")
    await create_user(session, UserCreateDb(email="ada@example.com", **base))
    fetched = await get_user(session, User.email == "nonexistent@example.com")
    assert fetched is None


async def test_get_user_multiple_matches_raise(session):
    base = dict(first_name="Ada", last_name="Lovelace", password_hash="hashed-value")
    await create_user(session, UserCreateDb(email="ada@example.com", **base))
    await create_user(session, UserCreateDb(email="ada2@example.com", **base))
    with pytest.raises(MultipleResultsFound):
        await get_user(session, User.first_name == "Ada")


async def test_update_user_updates_record(session):
    base = dict(
        first_name="Ada",
        last_name="Lovelace",
        email="ada@example.com",
        password_hash="hashed-value",
    )
    user = await create_user(session, UserCreateDb(**base))
    update_data = UserUpdateDb(first_name="Jane", last_name="Doe")
    updated = await update_user(session, update_data, User.id == user.id)
    assert updated is not None
    assert updated.first_name == "Jane"
    assert updated.last_name == "Doe"


async def test_list_users_returns_all_matches(session):
    base = dict(first_name="Ada", last_name="Smith", password_hash="hashed-value")
    for i in range(3):
        await create_user(session, UserCreateDb(email=f"u{i}@example.com", **base))
    users = await list_users(session, User.last_name == "Smith")
    assert len(users) == 3


async def test_list_users_empty_returns_empty_sequence(session):
    users = await list_users(session, User.last_name == "Nobody")
    assert users == []


async def test_update_user_partial_leaves_untouched_fields(session):
    base = dict(
        first_name="Ada",
        last_name="Lovelace",
        email="ada@example.com",
        password_hash="hashed-value",
    )
    user = await create_user(session, UserCreateDb(**base))
    await update_user(session, UserUpdateDb(first_name="Jane"), User.id == user.id)
    assert user.first_name == "Jane"
    assert user.last_name == "Lovelace"  # NOT nulled by the partial update
    assert user.email == "ada@example.com"


async def test_update_user_not_found_returns_none(session):
    result = await update_user(
        session, UserUpdateDb(first_name="Jane"), User.id == 999_999
    )
    assert result is None


async def test_update_user_refreshes_updated_at(session):
    base = dict(
        first_name="Ada",
        last_name="Lovelace",
        email="ada@example.com",
        password_hash="hashed-value",
    )
    user = await create_user(session, UserCreateDb(**base))
    updated = await update_user(
        session, UserUpdateDb(first_name="Jane"), User.id == user.id
    )
    assert updated is not None
    # func.now() is transaction-constant, so within one test transaction the
    # refreshed updated_at equals created_at; the point is that it is populated.
    assert updated.updated_at is not None
    assert updated.updated_at == updated.created_at


async def test_update_users_returns_affected_count(session):
    base = dict(first_name="Ada", last_name="Smith", password_hash="hashed-value")
    for i in range(3):
        await create_user(session, UserCreateDb(email=f"u{i}@example.com", **base))
    n = await update_users(
        session, UserUpdateDb(last_name="Jones"), User.last_name == "Smith"
    )
    assert n == 3
    assert await list_users(session, User.last_name == "Smith") == []
    assert len(await list_users(session, User.last_name == "Jones")) == 3


async def test_update_users_no_match_returns_zero(session):
    n = await update_users(
        session, UserUpdateDb(last_name="Jones"), User.last_name == "Nobody"
    )
    assert n == 0


async def test_update_users_empty_values_touches_only_timestamp(session):
    # A UserUpdateDb with nothing set dumps to {}, but updated_at's onupdate
    # still forms a valid SET clause -> the UPDATE matches rows and bumps the
    # timestamp without changing any caller-supplied field. It does NOT error.
    base = dict(
        first_name="Ada",
        last_name="Lovelace",
        email="ada@example.com",
        password_hash="hashed-value",
    )
    await create_user(session, UserCreateDb(**base))

    n = await update_users(session, UserUpdateDb(), User.last_name == "Lovelace")

    assert n == 1
    survivor = await get_user(session, User.last_name == "Lovelace")
    assert survivor is not None
    assert survivor.first_name == "Ada"  # untouched


async def _get_including_deleted(session, user_id: int) -> User | None:
    # Bypass the global soft-delete filter to read the physical row.
    statement = (
        select(User).where(User.id == user_id).execution_options(include_deleted=True)
    )
    return await session.scalar(statement)


async def test_delete_user_sets_deleted_at(session):
    base = dict(
        first_name="Ada",
        last_name="Lovelace",
        email="ada@example.com",
        password_hash="hashed-value",
    )
    user = await create_user(session, UserCreateDb(**base))
    await delete_user(session, User.id == user.id)
    row = await _get_including_deleted(session, user.id)
    assert row is not None  # physically still present
    assert row.deleted_at is not None


async def test_delete_user_hidden_from_get(session):
    base = dict(
        first_name="Ada",
        last_name="Lovelace",
        email="ada@example.com",
        password_hash="hashed-value",
    )
    user = await create_user(session, UserCreateDb(**base))
    await delete_user(session, User.id == user.id)
    # the global with_loader_criteria filter hides it from ordinary reads
    assert await get_user(session, User.id == user.id) is None


async def test_delete_user_hidden_from_list(session):
    base = dict(first_name="Ada", last_name="Smith", password_hash="hashed-value")
    for i in range(2):
        await create_user(session, UserCreateDb(email=f"u{i}@example.com", **base))
    await delete_user(session, User.last_name == "Smith")
    assert await list_users(session, User.last_name == "Smith") == []


async def test_delete_user_returns_count(session):
    base = dict(first_name="Ada", last_name="Smith", password_hash="hashed-value")
    for i in range(2):
        await create_user(session, UserCreateDb(email=f"u{i}@example.com", **base))
    n = await delete_user(session, User.last_name == "Smith")
    assert n == 2


async def test_restore_revives_soft_deleted(session):
    base = dict(
        first_name="Ada",
        last_name="Lovelace",
        email="ada@example.com",
        password_hash="hashed-value",
    )
    user = await create_user(session, UserCreateDb(**base))
    await delete_user(session, User.id == user.id)
    assert await get_user(session, User.id == user.id) is None  # hidden

    n = await restore_user(session, User.id == user.id)

    assert n == 1
    revived = await get_user(session, User.id == user.id)
    assert revived is not None
    assert revived.deleted_at is None
