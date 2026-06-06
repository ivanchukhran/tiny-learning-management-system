from collections.abc import AsyncGenerator

from database.connection import get_sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async_session = get_sessionmaker()
    async with async_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
