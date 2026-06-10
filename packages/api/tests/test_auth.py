import httpx
from api.main import app

EMAIL = "ada@example.com"
PASSWORD = "supersecret"


async def _register(client, email: str = EMAIL, password: str = PASSWORD) -> dict:
    resp = await client.post(
        "/users",
        json={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": email,
            "password": password,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _login(client, email: str = EMAIL, password: str = PASSWORD):
    return await client.post(
        "/auth/login", json={"email": email, "password": password}
    )


async def test_login_success_sets_cookie_and_returns_user(client):
    await _register(client)

    resp = await _login(client)

    assert resp.status_code == 200
    assert resp.json()["email"] == EMAIL
    assert "session" in resp.cookies


async def test_login_wrong_password_returns_401(client):
    await _register(client)

    resp = await _login(client, password="wrongpassword")

    assert resp.status_code == 401


async def test_login_unknown_email_returns_401(client):
    resp = await _login(client, email="nobody@example.com")

    assert resp.status_code == 401


async def test_deleted_user_cannot_login(client):
    user = await _register(client)
    assert (await client.delete(f"/users/{user['id']}")).status_code == 204

    resp = await _login(client)

    assert resp.status_code == 401


async def test_me_requires_session(client):
    resp = await client.get("/auth/me")

    assert resp.status_code == 401


async def test_me_returns_current_user_after_login(client):
    await _register(client)
    await _login(client)

    resp = await client.get("/auth/me")

    assert resp.status_code == 200
    assert resp.json()["email"] == EMAIL


async def test_logout_clears_session(client):
    await _register(client)
    await _login(client)
    assert (await client.get("/auth/me")).status_code == 200

    resp = await client.post("/auth/logout")

    assert resp.status_code == 204
    assert (await client.get("/auth/me")).status_code == 401


async def test_password_change_invalidates_sessions(client):
    user = await _register(client)
    await _login(client)
    assert (await client.get("/auth/me")).status_code == 200

    resp = await client.put(
        f"/users/{user['id']}/password", json={"password": "newpassword123"}
    )

    assert resp.status_code == 204
    assert (await client.get("/auth/me")).status_code == 401


async def test_logout_all_kills_other_sessions(client):
    await _register(client)
    await _login(client)  # session 1 (this client)

    # A second client logs in as the same user -> session 2. It shares the same
    # overridden DB session, so state is visible across both.
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="https://test") as other:
        assert (await _login(other)).status_code == 200
        assert (await other.get("/auth/me")).status_code == 200

        # client logs out everywhere
        assert (await client.post("/auth/logout-all")).status_code == 204

        # the other session is gone too
        assert (await other.get("/auth/me")).status_code == 401
