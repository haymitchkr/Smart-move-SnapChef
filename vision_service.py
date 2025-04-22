import os
import logging
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

logger = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_API_KEY)

PROMPT = (
    "На изображении представлены продукты питания. "
    "Выведи список ингредиентов через запятую. "
    "Включай только те продукты и ингредиенты, которые можно использовать для приготовления еды в текущем виде на фото. "
    "Не включай в список живых животных, людей, несъедобные предметы, упаковки, растения, если они не являются готовыми к употреблению продуктами. "
    "Если на фото только живое животное, человек или несъедобные объекты — ответь строго: Нет ингредиентов. "
    "Примеры: если на фото живой петух — не включай 'курица' в список; если на фото яблоко — включи 'яблоко'; если на фото человек — ответь: Нет ингредиентов."
)

NO_INGREDIENTS_PHRASES = [
    'нет ингредиентов',
    'ингредиенты не найдены',
]

async def download_photo(file_path: str, telegram_token: str) -> bytes:
    """Скачивает фото из Telegram по file_path."""
    import httpx
    url = f"https://api.telegram.org/file/bot{telegram_token}/{file_path}"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
            resp.raise_for_status()
            logger.info(f"Photo downloaded: {file_path}")
            return resp.content
    except Exception as e:
        logger.error(f"Download photo error: {e}")
        return b''

async def extract_ingredients_from_image(image_bytes: bytes) -> list:
    """
    Отправляет изображение в Gemini Vision API через google-generativeai и извлекает ингредиенты.
    """
    headers = {"Content-Type": "application/json"}
    try:
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        logger.info("Sending image to Gemini Vision API...")
        response = await model.generate_content_async([
            PROMPT,
            {"mime_type": "image/jpeg", "data": image_bytes}
        ])
        text = response.text.strip()
        logger.info(f"Gemini response: {text}")
        # Фильтрация по фразам отсутствия ингредиентов
        if not text or any(phrase in text.lower() for phrase in NO_INGREDIENTS_PHRASES):
            return []
        return parse_ingredients(text)
    except Exception as e:
        logger.error(f"Gemini Vision API error: {e}")
        return []

def parse_ingredients(text: str) -> list:
    """Парсит список ингредиентов из текста Gemini."""
    if not text:
        return []
    # Ожидаем строку с ингредиентами через запятую
    if ',' in text:
        return [i.strip() for i in text.split(',') if i.strip()]
    # Если список по строкам
    return [i.strip('-• \,') for i in text.split('\n') if i.strip()]

async def extract_ingredients_from_text(text: str) -> list:
    """Парсит ингредиенты из текстового сообщения пользователя."""
    return parse_ingredients(text) 