import pytest
import pytest_asyncio
from database.base import Base
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from testcontainers.postgres import PostgresContainer
from web.dependencies import get_session
from web.main import app


@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:16-alpine", driver="asyncpg") as pg:
        yield pg


@pytest_asyncio.fixture
async def engine(postgres_container):
    # function-scoped: connections are created on the same loop the test runs on
    engine = create_async_engine(postgres_container.get_connection_url())
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session(engine):
    # Outer transaction rolled back at teardown for isolation. The endpoints
    # commit, so the session joins via SAVEPOINT (create_savepoint): each
    # commit() releases/restarts a savepoint inside the outer transaction
    # instead of ending it, keeping every test fully isolated.
    connection = await engine.connect()
    transaction = await connection.begin()
    db = AsyncSession(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield db
    finally:
        await db.close()
        if transaction.is_active:
            await transaction.rollback()
        await connection.close()


@pytest_asyncio.fixture
async def client(session):
    async def _override_get_session():
        yield session

    app.dependency_overrides[get_session] = _override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
