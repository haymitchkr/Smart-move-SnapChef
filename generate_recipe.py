RECIPE_GENERATION_PROMPT = (
    "Ты — профессиональный кулинарный помощник ( шеф-повар )SnapChef. Составляй рецепты в современном, структурированном, понятном и минималистичном стиле.\n\n"
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
    "Стиль речи — дружелюбный, тёплый и уверенный. Пиши, как опытный шеф-повар, который объясняет всё с заботой, но без сюсюканья.\n"
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

async def generate_recipe(ingredients: list, user_id: int = None, session=None) -> str:
    """
    Генерирует рецепт по списку ингредиентов через Gemini Vision API с учётом настроек пользователя.
    """
    try:
        prompt_extra = ''
        if user_id and session:
            prefs = await get_preferences(session, user_id)
            difficulty_map = {
                'Простые': 'Лёгкий уровень: простые шаги, минимум технических приёмов, без длительного тушения и выпечки.',
                'Средние': 'Средний уровень: включает умеренные техники (запекание, тушение), время приготовления ~40–60 мин.',
                'Сложные': 'Сложный уровень: комбинированные техники (маринование, гриль, поэтапная подготовка), время >60 мин.'
            }
            difficulty_desc = difficulty_map.get(prefs.difficulty, '')
            calories_desc = (
                'Включить расчёт калорий: укажи общий калораж и ккал на одну порцию (150 г).' if prefs.calories_enabled
                else 'Не рассчитывать калории.'
            )
            healthy_desc = (
                'Режим ЗОЖ - здоровое питание: минимальное количество масла, больше овощей, меньше соли и сахара.' if prefs.healthy_mode
                else 'Без ограничений по здоровому питанию.'
            )
            prompt_extra = (
                'Настройки пользователя:\n'
                f'- Уровень сложности: {difficulty_desc}\n'
                f'- Калории: {calories_desc}\n'
                f'- ЗОЖ‑режим: {healthy_desc}\n'
            )
        full_prompt = (
            prompt_extra + "\n"
            + RECIPE_GENERATION_PROMPT + "\n"
            + "Ингредиенты:\n"
            + "\n".join(f"– {i}" for i in ingredients)
        )
        logger.info(f"[Prompt]: {full_prompt}")
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        response = await model.generate_content_async(full_prompt)
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