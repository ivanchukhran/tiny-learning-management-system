from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User
from database.schemas import UserCreate


async def create_user(session: AsyncSession, data: UserCreate):
    user = User(**data.model_dump())
    session.add(user)
    await session.flush()
    return user


async def update_user(session: AsyncSession):
    pass
