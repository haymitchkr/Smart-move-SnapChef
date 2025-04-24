RECIPE_GENERATION_PROMPT = (
    "Ты — профессиональный кулинарный помощник SnapChef. Составляй рецепты в современном, структурированном, понятном и минималистичном стиле.\n\n"
    "Оформляй каждый рецепт строго по следующей структуре:\n\n"
    "1. Название блюда — на первой строке, с заглавной буквы.\n"
    "2. Сложность — оцени рецепт как 'Легкий', 'Средний' или 'Сложный'.\n\n"
    "3. Ингредиенты — перечисли их по одному на строку в формате:\n"
    "   - продукт 1\n"
    "   - продукт 2\n"
    "   и т.д. Используй тире (–), не используй другие маркеры (*, • и т.п.).\n\n"
    "4. Подготовка ингредиентов — опиши, что нужно сделать до начала готовки (помыть, почистить, нарезать и т.д.). Этот раздел обязателен, если есть такие действия.\n\n"
    "5. Приготовление — пошаговая инструкция. Каждый шаг с новой строки, с нумерацией.\n"
    "6. Советы и рекомендации — 1–3 полезных совета по улучшению вкуса, замене ингредиентов, подаче блюда и т.д.\n\n"
    "Стиль речи — дружелюбный, тёплый и уверенный. Пиши кратко, понятно и по делу, как опытный шеф-повар.\n"
    "Смайлики разрешены, но только в меру и по делу (например, 🍋, 🍳, 🍽️). Не более 2–3 в тексте, ставь их только там, где действительно уместно.\n\n"
    "СТРОГО запрещено использовать Markdown-форматирование (*, **, __, -, •, # и прочее).\n"
    "Не пиши вводных фраз или объяснений. Не задавай вопросов. Начинай сразу с рецепта."
    "Используй только эти ингредиенты: {ingredients}, не добавляй ничего лишнего, кроме базовых продуктов и специй, даже если их мало, но также используй ВСЕ продукты из списка"
)

import os


import logging
import google.generativeai as genai
from dotenv import load_dotenv
import re
from user_preferences_service import get_preferences
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

load_dotenv()

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
genai.configure(api_key=GEMINI_API_KEY)

logger = logging.getLogger(__name__)

def format_recipe(text: str) -> str:
    # Убираем *, **, •, —, делаем оформление дружелюбным
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # убираем **
    text = text.replace('**', '').replace('*', '')
    text = text.replace('•', '-').replace('—', '-')
    # Заголовки
    text = re.sub(r'(?i)рецепт:', '🍽️ <b>Рецепт:</b>', text)
    text = re.sub(r'(?i)ингредиенты:', '📝 <b>Ингредиенты:</b>', text)
    text = re.sub(r'(?i)инструкции:|шаги приготовления:|шаги:', '🥣 <b>Шаги:</b>', text)
    text = re.sub(r'(?i)совет[ы]?:', '💡 <i>Советы от шефа:</i>', text)
    # Списки
    text = re.sub(r'\n\s*[-–—]\s*', '\n- ', text)  # нормализуем маркеры списков
    text = re.sub(r'\n\s*\d+\.', lambda m: f"\n🔸 {m.group(0).strip()}", text)  # шаги
    text = re.sub(r'\n- ', '\n▫️ ', text)  # эмодзи для списков
    # Убираем лишние пустые строки
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Дружелюбное завершение
    if 'Приятного аппетита' not in text:
        text += '\n\n👨‍🍳 <i>Приятного аппетита от вашего шефа!</i>'
    return text.strip()

async def generate_recipe(
    ingredients: List[str],
    user_id: int,
    session: AsyncSession = None,
    temp_difficulty: Optional[str] = None
) -> str:
    """
    Генерирует рецепт по списку ингредиентов через Gemini Vision API с учётом настроек пользователя.
    """
    try:
        prefs = None
        if user_id and session:
            prefs = await get_preferences(session, user_id)
        healthy_profile = getattr(prefs, 'healthy_profile', False) if prefs else False
        preferred_cuisine = getattr(prefs, 'preferred_cuisine', 'Любая') if prefs else 'Любая'

        prompt_extra = ''
        if healthy_profile:
            prompt_extra += (
                'Режим здорового питания активен — выбери только полезные способы готовки и добавь краткое описание пользы блюда (в одном предложении).\n'
            )
        if preferred_cuisine and preferred_cuisine != 'Любая':
            prompt_extra += (
                f'Приготовь это блюдо в стиле {preferred_cuisine} кухни.\n'
            )
        if temp_difficulty:
            if temp_difficulty.lower().startswith('проще'):
                prompt_extra += 'Сделай рецепт простым и минималистичным. Только базовые шаги и продукты.\n'
            elif temp_difficulty.lower().startswith('сложнее'):
                prompt_extra += 'Сделай рецепт более изысканным. Добавь нестандартные шаги и оригинальную подачу.\n'

        prompt = f"""
Ты — профессиональный кулинарный помощник SnapChef.

🔧 ЗАДАЧА:
На основе списка ингредиентов {ingredients} сгенерируй рецепт в структурированном и понятном стиле. Используй все продукты из списка. Не добавляй ничего лишнего, кроме базовых специй (соль, перец, масло и т.п.).

{prompt_extra}
💡 СТИЛЬ:
Минималистично, без воды, без фантазий. Только конкретные шаги, как опытный шеф-повар объясняет ученику. Пиши понятно, уверенно, дружелюбно. Не задавай вопросов, не пиши вступлений. Без markdown-формата, не используй (*, __, • и т.п.).

🧱 СТРУКТУРА ВЫВОДА:
1. Название блюда (с заглавной буквы).
2. Сложность (Легкий, Средний, Сложный) — оцени сам.
3. Ингредиенты — по одному на строку, формат: – продукт.
4. Подготовка ингредиентов — кратко (если нужно).
5. Приготовление — пошагово, с нумерацией.
6. Советы и рекомендации — 2–3 идеи по улучшению.
7. КБЖУ (на 100 г и на 1 порцию, приблизительно) — ОБЯЗАТЕЛЕН, даже примерный.

📦 Пример оформления КБЖУ:
Калории: ~180 ккал / 100 г  
Белки: ~12 г  
Жиры: ~8 г  
Углеводы: ~15 г

Используй только эти ингредиенты: {ingredients}
"""
        logger.info(f"[Prompt]: {prompt}")
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        response = await model.generate_content_async(prompt)
        logger.info(f"[Response]: {response.text}")
        logger.info(f"Recipe generated: {response.text}")
        return format_recipe(response.text)
    except Exception as e:
        logger.error(f"Recipe generation error: {e}")
        return "Извините, не удалось сгенерировать рецепт. Попробуйте позже."

# --- UNIT TEST ---
import pytest
import types
class DummyPrefs:
    difficulty = 'Сложные'
    calories_enabled = True
    healthy_mode = True
@pytest.mark.asyncio
def test_prompt_extra_in_generate_recipe(monkeypatch):
    async def dummy_get_preferences(session, user_id):
        return DummyPrefs()
    monkeypatch.setattr('user_preferences_service.get_preferences', dummy_get_preferences)
    captured = {}
    async def dummy_generate_content_async(self, prompt):
        captured['prompt'] = prompt
        assert 'Сложный уровень: комбинированные техники' in prompt
        assert 'Включить расчёт калорий' in prompt
        assert 'Режим ЗОЖ - здоровое питание' in prompt
        return types.SimpleNamespace(text='ok')
    monkeypatch.setattr('google.generativeai.GenerativeModel.generate_content_async', dummy_generate_content_async)
    import asyncio
    asyncio.run(generate_recipe(['яблоко', 'банан'], user_id=1, session=object()))
    assert 'Сложный уровень: комбинированные техники' in captured['prompt']
    assert 'Включить расчёт калорий' in captured['prompt']
    assert 'Режим ЗОЖ - здоровое питание' in captured['prompt'] 