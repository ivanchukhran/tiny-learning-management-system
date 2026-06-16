from core.constants import SESSION_COOKIE_NAME

REGISTER_PAYLOAD = {
    "first_name": "Ada",
    "last_name": "Lovelace",
    "email": "ada@example.com",
    "password": "supersecret",
}
LOGIN_PAYLOAD = {"email": "ada@example.com", "password": "supersecret"}


async def test_login_sets_session_cookie(client):
    register = await client.post("/register", data=REGISTER_PAYLOAD)
    assert register.status_code == 201

    resp = await client.post("/login", data=LOGIN_PAYLOAD)

    assert resp.status_code == 200
    assert "ada@example.com" in resp.text
    assert SESSION_COOKIE_NAME in resp.cookies


async def test_login_wrong_password_returns_unauthorized(client):
    register = await client.post("/register", data=REGISTER_PAYLOAD)
    assert register.status_code == 201

    resp = await client.post(
        "/login", data={"email": "ada@example.com", "password": "wrongpassword"}
    )

    assert resp.status_code == 401
    assert "Invalid credentials" in resp.text
    assert SESSION_COOKIE_NAME not in resp.cookies


async def test_login_unknown_email_returns_unauthorized(client):
    resp = await client.post(
        "/login", data={"email": "nobody@example.com", "password": "supersecret"}
    )

    assert resp.status_code == 401
    assert "Invalid credentials" in resp.text
    assert SESSION_COOKIE_NAME not in resp.cookies
