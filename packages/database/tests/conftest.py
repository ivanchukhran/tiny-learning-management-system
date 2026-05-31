import pytest
import pytest_asyncio
from database.base import Base
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from testcontainers.postgres import PostgresContainer


@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:16-alpine", driver="asyncpg") as pg:
        yield pg


@pytest_asyncio.fixture
async def engine(postgres_container):
    # function-scoped
    engine = create_async_engine(postgres_container.get_connection_url())
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session(engine):
    # Each test runs inside a transaction that is rolled back at the end → full isolation.
    connection = await engine.connect()
    transaction = await connection.begin()
    db = AsyncSession(bind=connection, expire_on_commit=False)
    try:
        yield db
    finally:
        await db.close()
        # only roll back if transaction is still active
        # to avoid "transaction already deassociated" warnings.
        if transaction.is_active:
            await transaction.rollback()
        await connection.close()
