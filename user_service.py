from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from models import User, UserPreferences

async def get_user_by_telegram_id(session: AsyncSession, telegram_id: str) -> User | None:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalars().first()

async def create_user(session: AsyncSession, telegram_id: str, name: str = None) -> User:
    user = User(telegram_id=telegram_id, name=name)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user

async def get_state(user_id: int, session: AsyncSession) -> str:
    prefs = await session.execute(select(UserPreferences).where(UserPreferences.user_id == user_id))
    prefs = prefs.scalars().first()
    if prefs and getattr(prefs, 'first_run', True):
        return 'FIRST_RUN'
    # Здесь можно добавить логику по другим этапам (например, по данным из session_store)
    # Пока возвращаем IDLE по умолчанию
    return 'IDLE' 