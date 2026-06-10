PAYLOAD = {
    "first_name": "Ada",
    "last_name": "Lovelace",
    "email": "ada@example.com",
    "password": "supersecret",
}


async def test_register_creates_user(client):
    resp = await client.post("/register", data=PAYLOAD)

    assert resp.status_code == 201
    assert "ada@example.com" in resp.text


async def test_register_duplicate_email_returns_conflict(client):
    first = await client.post("/register", data=PAYLOAD)
    assert first.status_code == 201

    second = await client.post("/register", data=PAYLOAD)

    assert second.status_code == 409
    assert "already registered" in second.text
