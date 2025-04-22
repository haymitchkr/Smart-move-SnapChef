from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from models import RecipeHistory

async def add_recipe_history(session: AsyncSession, user_id: int, ingredients: str, recipe: str) -> RecipeHistory:
    entry = RecipeHistory(user_id=user_id, ingredients=ingredients, recipe=recipe)
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return entry

async def get_user_history(session: AsyncSession, user_id: int, limit: int = 10):
    result = await session.execute(
        select(RecipeHistory).where(RecipeHistory.user_id == user_id).order_by(RecipeHistory.created_at.desc()).limit(limit)
    )
    return result.scalars().all() 