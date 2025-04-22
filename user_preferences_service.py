from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from models import UserPreferences

async def get_preferences(session: AsyncSession, user_id: int) -> UserPreferences:
    result = await session.execute(select(UserPreferences).where(UserPreferences.user_id == user_id))
    prefs = result.scalars().first()
    if not prefs:
        prefs = UserPreferences(user_id=user_id)
        session.add(prefs)
        await session.commit()
        await session.refresh(prefs)
    return prefs

async def update_preference(session: AsyncSession, user_id: int, field: str, value):
    prefs = await get_preferences(session, user_id)
    setattr(prefs, field, value)
    await session.commit()
    await session.refresh(prefs)
    return prefs 