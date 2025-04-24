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
    # Удаляем markdown и лишние символы
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = text.replace('**', '').replace('*', '')
    text = text.replace('•', '-')
    text = text.replace('—', '-')
    text = text.replace('__', '')

    # Функция для очистки строки от emoji и заголовков
    def clean_line(line, block_emoji, block_title):
        # Удаляем emoji и заголовок в начале строки
        pattern = rf'^{re.escape(block_emoji)}\s*{re.escape(block_title)}:?\s*'
        return re.sub(pattern, '', line, flags=re.IGNORECASE).strip()

    # Парсим блоки по ключевым словам
    blocks = {
        'title': '',
        'difficulty': '',
        'ingredients': '',
        'prep': '',
        'steps': '',
        'tips': '',
        'kbju': ''
    }
    lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
    # 1. Название (первая строка)
    if lines:
        blocks['title'] = re.sub(r'^📌\s*', '', lines[0]).strip()
    # 2. Сложность
    diff_match = next((l for l in lines if re.match(r'(?i)^Сложность[:\s]', l)), None)
    if diff_match:
        blocks['difficulty'] = re.sub(r'(?i)^Сложность[:\s]*', '', diff_match).strip()
    if not blocks['difficulty']:
        blocks['difficulty'] = 'Средний'
    # 3. Ингредиенты
    ing_start = next((i for i, l in enumerate(lines) if re.search(r'(?i)ингредиенты', l)), None)
    prep_start = next((i for i, l in enumerate(lines) if re.search(r'(?i)подготовка', l)), None)
    steps_start = next((i for i, l in enumerate(lines) if re.search(r'(?i)шаги|инструкции', l)), None)
    tips_start = next((i for i, l in enumerate(lines) if re.search(r'(?i)советы', l)), None)
    kbju_start = next((i for i, l in enumerate(lines) if re.search(r'(?i)кбжу', l)), None)

    # Ингредиенты
    if ing_start is not None:
        end = prep_start or steps_start or tips_start or kbju_start or len(lines)
        block_lines = lines[ing_start+1:end]
        # Очищаем каждую строку от emoji/заголовка
        block_lines = [clean_line(l, '📝', 'Ингредиенты') for l in block_lines if l]
        ings = [re.sub(r'^[-–\d.\s]*', '', i) for i in block_lines]
        blocks['ingredients'] = '\n'.join(f'– {i}' for i in ings if i)
    # Подготовка
    if prep_start is not None:
        end = steps_start or tips_start or kbju_start or len(lines)
        block_lines = lines[prep_start+1:end]
        block_lines = [clean_line(l, '🔪', 'Подготовка ингредиентов') for l in block_lines if l]
        preps = [re.sub(r'^[-–\d.\s]*', '', i) for i in block_lines]
        blocks['prep'] = '\n'.join(f'– {i}' for i in preps if i)
    # Шаги
    if steps_start is not None:
        end = tips_start or kbju_start or len(lines)
        block_lines = lines[steps_start+1:end]
        block_lines = [clean_line(l, '🥣', 'Шаги приготовления') for l in block_lines if l]
        steps = [re.sub(r'^[-–\d.\s]*', '', s) for s in block_lines]
        blocks['steps'] = '\n'.join(f'{idx+1}. {s}' for idx, s in enumerate(steps) if s)
    # Советы
    if tips_start is not None:
        end = kbju_start or len(lines)
        block_lines = lines[tips_start+1:end]
        block_lines = [clean_line(l, '💡', 'Советы от шефа') for l in block_lines if l]
        tips = [re.sub(r'^[-–\d.\s]*', '', t) for t in block_lines]
        blocks['tips'] = '\n'.join(f'– {t}' for t in tips if t)
    # КБЖУ
    if kbju_start is not None:
        end = len(lines)
        kbju_lines = lines[kbju_start:end]
        kbju_text = '\n'.join(kbju_lines)
        kbju_text = re.sub(r'(?i)кбжу[:\s-]*', '', kbju_text)
        kbju_text = re.sub(r'\n+', '\n', kbju_text)
        blocks['kbju'] = kbju_text.strip()

    # Форматирование КБЖУ по шаблону
    def format_kbju_block(kbju_raw):
        kbju_100g = {'cal': '', 'prot': '', 'fat': '', 'carb': ''}
        kbju_portion = {'cal': '', 'prot': '', 'fat': '', 'carb': ''}
        m_100g = re.search(r'([Нн]а 100 ?г[^\n]*)', kbju_raw)
        if m_100g:
            s = m_100g.group(1)
            kbju_100g['cal'] = re.search(r'(\d+\s*ккал)', s) and re.search(r'(\d+\s*ккал)', s).group(1) or ''
            kbju_100g['prot'] = re.search(r'(\d+\s*г\s*белк)', s) and re.search(r'(\d+\s*г\s*белк)', s).group(1) or ''
            kbju_100g['fat'] = re.search(r'(\d+\s*г\s*жир)', s) and re.search(r'(\d+\s*г\s*жир)', s).group(1) or ''
            kbju_100g['carb'] = re.search(r'(\d+\s*г\s*углевод)', s) and re.search(r'(\d+\s*г\s*углевод)', s).group(1) or ''
        m_portion = re.search(r'([Нн]а [1-9][0-9]* ?порц[^\n]*)', kbju_raw)
        if m_portion:
            s = m_portion.group(1)
            kbju_portion['cal'] = re.search(r'(\d+\s*ккал)', s) and re.search(r'(\d+\s*ккал)', s).group(1) or ''
            kbju_portion['prot'] = re.search(r'(\d+\s*г\s*белк)', s) and re.search(r'(\d+\s*г\s*белк)', s).group(1) or ''
            kbju_portion['fat'] = re.search(r'(\d+\s*г\s*жир)', s) and re.search(r'(\d+\s*г\s*жир)', s).group(1) or ''
            kbju_portion['carb'] = re.search(r'(\d+\s*г\s*углевод)', s) and re.search(r'(\d+\s*г\s*углевод)', s).group(1) or ''
        if not any(kbju_100g.values()) and not any(kbju_portion.values()):
            return '~250 ккал, ~12 г белков, ~8 г жиров, ~20 г углеводов'
        result = 'На 100 г:'
        if any(kbju_100g.values()):
            if kbju_100g['cal']:
                result += f'\n - {kbju_100g["cal"]}'
            if kbju_100g['prot']:
                result += f'\n - {kbju_100g["prot"]}'
            if kbju_100g['fat']:
                result += f'\n - {kbju_100g["fat"]}'
            if kbju_100g['carb']:
                result += f'\n - {kbju_100g["carb"]}'
        else:
            result += '\n~250 ккал, ~12 г белков, ~8 г жиров, ~20 г углеводов'
        result += '\nНа порцию (300 г):'
        if any(kbju_portion.values()):
            if kbju_portion['cal']:
                result += f'\n - {kbju_portion["cal"]}'
            if kbju_portion['prot']:
                result += f'\n - {kbju_portion["prot"]}'
            if kbju_portion['fat']:
                result += f'\n - {kbju_portion["fat"]}'
            if kbju_portion['carb']:
                result += f'\n - {kbju_portion["carb"]}'
        else:
            result += '\n~750 ккал, ~36 г белков, ~24 г жиров, ~60 г углеводов'
        return result

    # Итоговая сборка по шаблону
    result = ''
    result += f'📌 {blocks["title"]}\n\n' if blocks['title'] else ''
    result += f'⚡️ Сложность: {blocks["difficulty"]}\n\n'
    result += f'📝 Ингредиенты:\n{blocks["ingredients"]}\n\n'
    result += f'🔪 Подготовка ингредиентов:\n{blocks["prep"]}\n\n'
    result += f'🥣 Шаги приготовления:\n{blocks["steps"]}\n\n'
    result += f'💡 Советы от шефа:\n{blocks["tips"]}\n\n'
    result += f'🍽 КБЖУ (приблизительно):\n{format_kbju_block(blocks["kbju"])}\n\n'
    result += '👨‍🍳 Приятного аппетита от вашего шефа!'
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result.strip()

async def generate_recipe(
    ingredients: List[str],
    user_id: int,
    session: AsyncSession = None,
    temp_difficulty: Optional[str] = None,
    query: Optional[str] = None
) -> str:
    """
    Генерирует рецепт по списку ингредиентов или по пользовательскому запросу через Gemini Vision API с учётом настроек пользователя.
    """
    try:
        prefs = None
        if user_id and session:
            prefs = await get_preferences(session, user_id)
        healthy_profile = getattr(prefs, 'healthy_profile', False) if prefs else False
        preferred_cuisine = getattr(prefs, 'preferred_cuisine', 'Любая') if prefs else 'Любая'

        if query:
            prompt = f"""
Ты — профессиональный кулинарный помощник SnapChef.

Составь подробный, современный рецепт по запросу пользователя: \"{query}\".

Строго соблюдай следующую структуру (каждый блок с новой строки, без HTML и markdown, только текст и emoji):

📌 Название блюда (с заглавной буквы)

⚡️ Сложность: Легкий / Средний / Сложный

📝 Ингредиенты:
– продукт 1
– продукт 2
...

🔪 Подготовка ингредиентов:
– шаг 1
– шаг 2
...

🥣 Шаги приготовления:
1. шаг 1
2. шаг 2
...

💡 Советы от шефа:
– совет 1
– совет 2

🍽 КБЖУ (приблизительно):
На 100 г: ... ккал, ... г белков, ... г жиров, ... г углеводов
На порцию (300 г): ... ккал, ... г белков, ... г жиров, ... г углеводов

👨‍🍳 Приятного аппетита от вашего шефа!

Требования:
- Не используй HTML, markdown, спецсимволы, только текст и emoji в начале блока.
- Не добавляй вводных фраз, не пиши "Вот рецепт" и т.п.
- Всегда указывай сложность (Легкий, Средний, Сложный) после ⚡️ Сложность:.
- Всегда указывай КБЖУ (даже примерные значения, если точных нет).
- {('Готовь только полезными способами, не используй жарку, минимизируй жиры, делай рецепт максимально здоровым.' if healthy_profile else '')}
- {f'Оформи рецепт в стиле {preferred_cuisine} кухни.' if preferred_cuisine and preferred_cuisine != 'Любая' else ''}
"""
        else:
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

Строго соблюдай следующую структуру (каждый блок с новой строки, без HTML и markdown, только текст и emoji):

📌 Название блюда (с заглавной буквы)

⚡️ Сложность: Легкий / Средний / Сложный

📝 Ингредиенты:
– продукт 1
– продукт 2
...

🔪 Подготовка ингредиентов:
– шаг 1
– шаг 2
...

🥣 Шаги приготовления:
1. шаг 1
2. шаг 2
...

💡 Советы от шефа:
– совет 1
– совет 2

🍽 КБЖУ (приблизительно):
На 100 г: ... ккал, ... г белков, ... г жиров, ... г углеводов
На порцию (300 г): ... ккал, ... г белков, ... г жиров, ... г углеводов

👨‍🍳 Приятного аппетита от вашего шефа!

Требования:
- Не используй HTML, markdown, спецсимволы, только текст и emoji в начале блока.
- Не добавляй вводных фраз, не пиши "Вот рецепт" и т.п.
- Всегда указывай сложность (Легкий, Средний, Сложный) после ⚡️ Сложность:.
- Всегда указывай КБЖУ (даже примерные значения, если точных нет).
- Используй только эти ингредиенты: {ingredients}
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