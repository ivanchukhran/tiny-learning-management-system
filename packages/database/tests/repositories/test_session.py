import hashlib
from datetime import datetime, timedelta, timezone

from database.models import User
from database.repositories.session import (
    create_session,
    delete_session,
    delete_user_sessions,
    get_valid_session,
    touch_session,
)
from database.repositories.user import create_user, delete_user
from database.schemas import UserCreateDb


def _hash(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


async def _make_user(session, email: str = "ada@example.com") -> User:
    return await create_user(
        session,
        UserCreateDb(
            first_name="Ada",
            last_name="Lovelace",
            email=email,
            password_hash="hashed-value",
        ),
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


# Generous cutoffs that a freshly-created session always passes.
_VALID = dict(
    idle_cutoff=_now() - timedelta(hours=1),
    absolute_cutoff=_now() - timedelta(hours=24),
)


async def test_create_session_persists_row(session):
    user = await _make_user(session)

    s = await create_session(session, user.id, _hash("tok"))

    assert s.id is not None
    assert s.user_id == user.id
    assert s.hash == _hash("tok")
    assert s.created_at is not None  # server_default via RETURNING
    assert s.last_seen_at is not None


async def test_get_valid_session_returns_match_and_eager_user(session):
    user = await _make_user(session)
    await create_session(session, user.id, _hash("tok"))

    found = await get_valid_session(session, _hash("tok"), **_VALID)

    assert found is not None
    # contains_eager populated the relationship: no lazy IO needed here
    assert found.user.email == "ada@example.com"


async def test_get_valid_session_unknown_hash_returns_none(session):
    found = await get_valid_session(session, _hash("nope"), **_VALID)
    assert found is None


async def test_get_valid_session_idle_expired_returns_none(session):
    user = await _make_user(session)
    await create_session(session, user.id, _hash("tok"))

    # idle_cutoff in the future -> last_seen_at (~now) is not greater -> expired
    found = await get_valid_session(
        session,
        _hash("tok"),
        idle_cutoff=_now() + timedelta(hours=1),
        absolute_cutoff=_now() - timedelta(hours=24),
    )

    assert found is None


async def test_get_valid_session_absolute_expired_returns_none(session):
    user = await _make_user(session)
    await create_session(session, user.id, _hash("tok"))

    # absolute_cutoff in the future -> created_at (~now) is not greater -> expired
    found = await get_valid_session(
        session,
        _hash("tok"),
        idle_cutoff=_now() - timedelta(hours=1),
        absolute_cutoff=_now() + timedelta(hours=1),
    )

    assert found is None


async def test_get_valid_session_soft_deleted_user_returns_none(session):
    # The headline guarantee: deleting the user kills their sessions for free,
    # because the inner join to User is filtered by the global soft-delete filter.
    user = await _make_user(session)
    await create_session(session, user.id, _hash("tok"))

    await delete_user(session, User.id == user.id)

    found = await get_valid_session(session, _hash("tok"), **_VALID)
    assert found is None


async def test_touch_session_bumps_last_seen(session):
    user = await _make_user(session)
    s = await create_session(session, user.id, _hash("tok"))
    original = s.last_seen_at

    await touch_session(session, s.id)
    await session.refresh(s, ["last_seen_at"])

    assert s.last_seen_at >= original


async def test_delete_session_removes_one_by_hash(session):
    user = await _make_user(session)
    await create_session(session, user.id, _hash("a"))
    await create_session(session, user.id, _hash("b"))

    deleted = await delete_session(session, _hash("a"))

    assert deleted == 1
    assert await get_valid_session(session, _hash("a"), **_VALID) is None
    assert await get_valid_session(session, _hash("b"), **_VALID) is not None


async def test_delete_session_unknown_hash_returns_zero(session):
    assert await delete_session(session, _hash("nope")) == 0


async def test_delete_user_sessions_removes_all(session):
    user = await _make_user(session)
    for i in range(3):
        await create_session(session, user.id, _hash(f"tok{i}"))

    deleted = await delete_user_sessions(session, user.id)

    assert deleted == 3
    assert await get_valid_session(session, _hash("tok0"), **_VALID) is None
