from database.models import User
from database.repositories import create_or_promote_admin

REGISTER_PAYLOAD = {
    "first_name": "Ada",
    "last_name": "Lovelace",
    "email": "ada@example.com",
    "password": "supersecret",
}
LOGIN_PAYLOAD = {"email": "ada@example.com", "password": "supersecret"}


async def test_admin_ping_allows_admin(client, session):
    register = await client.post("/register", data=REGISTER_PAYLOAD)
    assert register.status_code == 201

    # Registration creates a non-admin user; promote it before logging in.
    await create_or_promote_admin(session, email="ada@example.com")
    await session.commit()

    login = await client.post("/login", data=LOGIN_PAYLOAD)
    assert login.status_code == 200

    resp = await client.get("/admin/ping")

    assert resp.status_code == 200
    assert resp.json() == {"message": "pong"}


async def test_admin_ping_forbids_non_admin(client):
    register = await client.post("/register", data=REGISTER_PAYLOAD)
    assert register.status_code == 201

    login = await client.post("/login", data=LOGIN_PAYLOAD)
    assert login.status_code == 200

    resp = await client.get("/admin/ping")

    assert resp.status_code == 403


async def test_admin_ping_requires_authentication(client):
    resp = await client.get("/admin/ping")

    assert resp.status_code == 401


async def test_admin_ping_reflects_promotion_on_next_request(client, session):
    # is_admin is read fresh from the user row by get_current_user on every
    # request, so promoting mid-session flips the guard without re-login.
    register = await client.post("/register", data=REGISTER_PAYLOAD)
    assert register.status_code == 201
    login = await client.post("/login", data=LOGIN_PAYLOAD)
    assert login.status_code == 200

    # Not yet admin -> 403.
    assert (await client.get("/admin/ping")).status_code == 403

    # Promote, then the same logged-in session now passes.
    await create_or_promote_admin(session, email="ada@example.com")
    await session.commit()

    assert (await client.get("/admin/ping")).status_code == 200


async def test_admin_promotion_persists_is_admin(client, session):
    register = await client.post("/register", data=REGISTER_PAYLOAD)
    assert register.status_code == 201

    user, created = await create_or_promote_admin(session, email="ada@example.com")
    await session.commit()

    assert created is False
    refreshed = await session.get(User, user.id)
    assert refreshed is not None
    assert refreshed.is_admin is True
