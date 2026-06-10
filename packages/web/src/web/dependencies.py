from collections.abc import AsyncGenerator

from database.connection import get_sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    # Each app owns its own request-scoped session generator; the engine and
    # sessionmaker themselves are shared (database.connection). This is framework
    # glue, not auth logic, so it is intentionally not in `core`.
    async_session = get_sessionmaker()
    async with async_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
