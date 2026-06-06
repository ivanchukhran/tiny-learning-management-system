from database.models import User
from database.repositories.user import get_user


def _payload(**overrides) -> dict:
    base = {
        "first_name": "Ada",
        "last_name": "Lovelace",
        "email": "ada@example.com",
        "password": "supersecret",
    }
    base.update(overrides)
    return base


async def _create(client, **overrides) -> dict:
    resp = await client.post("/users", json=_payload(**overrides))
    assert resp.status_code == 201, resp.text
    return resp.json()


# --------------------------------------------------------------------------- #
# POST /users
# --------------------------------------------------------------------------- #
async def test_create_user_returns_201_and_body(client):
    resp = await client.post("/users", json=_payload())

    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] > 0
    assert body["email"] == "ada@example.com"
    assert "password" not in body  # write-only, never returned
    assert "password_hash" not in body


async def test_create_user_duplicate_email_returns_409(client):
    await _create(client)

    resp = await client.post("/users", json=_payload())

    assert resp.status_code == 409


async def test_create_user_short_password_returns_422(client):
    resp = await client.post("/users", json=_payload(password="short"))

    assert resp.status_code == 422


async def test_create_user_invalid_email_returns_422(client):
    resp = await client.post("/users", json=_payload(email="not-an-email"))

    assert resp.status_code == 422


# --------------------------------------------------------------------------- #
# GET /users/{id} and GET /users
# --------------------------------------------------------------------------- #
async def test_get_user_returns_200(client):
    created = await _create(client)

    resp = await client.get(f"/users/{created['id']}")

    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


async def test_get_user_not_found_returns_404(client):
    resp = await client.get("/users/999999")

    assert resp.status_code == 404


async def test_list_users_paginates(client):
    for i in range(3):
        await _create(client, email=f"u{i}@example.com")

    resp = await client.get("/users", params={"limit": 2, "offset": 0})

    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_list_users_sort_desc(client):
    for email in ("c@example.com", "a@example.com", "b@example.com"):
        await _create(client, email=email)

    resp = await client.get("/users", params={"sort": "email", "order": "desc"})

    emails = [u["email"] for u in resp.json()]
    assert emails == ["c@example.com", "b@example.com", "a@example.com"]


async def test_list_users_invalid_sort_returns_422(client):
    resp = await client.get("/users", params={"sort": "password_hash"})

    assert resp.status_code == 422


# --------------------------------------------------------------------------- #
# PATCH /users/{id}
# --------------------------------------------------------------------------- #
async def test_update_user_patches_fields(client):
    created = await _create(client)

    resp = await client.patch(f"/users/{created['id']}", json={"first_name": "Jane"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["first_name"] == "Jane"
    assert body["last_name"] == "Lovelace"  # untouched


async def test_update_user_not_found_returns_404(client):
    resp = await client.patch("/users/999999", json={"first_name": "Jane"})

    assert resp.status_code == 404


async def test_update_user_duplicate_email_returns_409(client):
    await _create(client, email="taken@example.com")
    target = await _create(client, email="other@example.com")

    resp = await client.patch(
        f"/users/{target['id']}", json={"email": "taken@example.com"}
    )

    assert resp.status_code == 409


# --------------------------------------------------------------------------- #
# PUT /users/{id}/password
# --------------------------------------------------------------------------- #
async def test_update_password_returns_204_and_changes_hash(client, session):
    created = await _create(client)
    before = await get_user(session, User.id == created["id"])
    assert before is not None
    old_hash = before.password_hash

    resp = await client.put(
        f"/users/{created['id']}/password", json={"password": "brandnewsecret"}
    )

    assert resp.status_code == 204
    after = await get_user(session, User.id == created["id"])
    assert after is not None
    assert after.password_hash != old_hash


async def test_update_password_not_found_returns_404(client):
    resp = await client.put("/users/999999/password", json={"password": "whatever123"})

    assert resp.status_code == 404


async def test_update_password_short_returns_422(client):
    created = await _create(client)

    resp = await client.put(
        f"/users/{created['id']}/password", json={"password": "short"}
    )

    assert resp.status_code == 422


# --------------------------------------------------------------------------- #
# DELETE /users/{id} and POST /users/{id}/restore
# --------------------------------------------------------------------------- #
async def test_delete_user_returns_204_and_hides(client):
    created = await _create(client)

    resp = await client.delete(f"/users/{created['id']}")

    assert resp.status_code == 204
    # soft-deleted -> hidden from normal reads
    assert (await client.get(f"/users/{created['id']}")).status_code == 404


async def test_delete_user_not_found_returns_404(client):
    resp = await client.delete("/users/999999")

    assert resp.status_code == 404


async def test_restore_user_returns_200_and_revives(client):
    created = await _create(client)
    await client.delete(f"/users/{created['id']}")

    resp = await client.post(f"/users/{created['id']}/restore")

    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]
    # visible again
    assert (await client.get(f"/users/{created['id']}")).status_code == 200


async def test_restore_user_not_found_returns_404(client):
    resp = await client.post("/users/999999/restore")

    assert resp.status_code == 404
