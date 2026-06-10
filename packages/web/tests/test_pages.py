from httpx import ASGITransport, AsyncClient
from web.main import app


async def test_login_page_renders():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/login")

    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "<h1>Login</h1>" in resp.text
