import os
import httpx
import logging
from generate_recipe import generate_recipe
from session_store import session_store
from vision_service import download_photo, extract_ingredients_from_image
from user_service import get_user_by_telegram_id, create_user
from recipe_history_service import get_user_history
from user_preferences_service import get_preferences, update_preference
from database import get_async_session

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_API = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}'

logger = logging.getLogger(__name__)

async def send_message(chat_id, text, reply_markup=None):
    data = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'HTML',
        'reply_markup': reply_markup or {}
    }
    try:
        async with httpx.AsyncClient() as client:
            await client.post(f'{TELEGRAM_API}/sendMessage', json=data)
    except Exception as e:
        logger.error(f"send_message error: {e}")

WAIT_INGREDIENTS = "WAIT_INGREDIENTS"
CONFIRMING = "CONFIRMING"
ADDING = "ADDING_INGREDIENTS"
REMOVING = "REMOVING_INGREDIENTS"
IDLE = "IDLE"

CMD_CONFIRM = "✅ Всё верно, готовим!"
CMD_ADD = "➕ Добавить ингредиент"
CMD_REMOVE = "➖ Убрать ингредиент"
CMD_CANCEL = "🛑 Передумал готовить"

MENU_COMMANDS = {
    "Главное": "main",
    "Помощь": "help",
    "Сохранённые": "saved",
    "Настройки": "settings"
}

async def handle_update(update, session=None):
    message = update.get("message")
    if not message:
        return
    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()
    session_data = await session_store.get_session(chat_id) or {"state": IDLE, "ingredients": []}
    state = session_data["state"]

    if text in MENU_COMMANDS:
        if text == "Главное":
            await send_message(chat_id, "👨‍🍳 Добро пожаловать в SnapChef!\nЯ помогу подобрать рецепт по фото или списку продуктов.\nВыберите действие из меню ниже.", reply_markup=build_reply_keyboard(IDLE))
            session_data["state"] = WAIT_INGREDIENTS
        elif text == "Помощь":
            await send_message(chat_id, "❓ <b>Помощь</b>\n1. Отправьте фото продуктов или напишите их через запятую.\n2. Следуйте подсказкам бота.\n3. Используйте меню для доступа к сохранённым рецептам и настройкам.", reply_markup=build_reply_keyboard(IDLE))
        elif text == "Сохранённые":
            async for db_session in get_async_session():
                user = await get_user_by_telegram_id(db_session, str(chat_id))
                if not user:
                    await send_message(chat_id, "У вас пока нет сохранённых рецептов.", reply_markup=build_reply_keyboard(IDLE))
                    break
                saved = await get_user_history(db_session, user.id, limit=10)
                if not saved:
                    await send_message(chat_id, "У вас пока нет сохранённых рецептов.", reply_markup=build_reply_keyboard(IDLE))
                    break
                for rec in saved:
                    title = rec.recipe.split('\n', 1)[0][:64]
                    date = rec.created_at.strftime('%Y-%m-%d')
                    await send_message(chat_id, f"<b>{title}</b>\nДата: {date}", reply_markup=build_reply_keyboard(IDLE))
        elif text == "Настройки":
            async for db_session in get_async_session():
                user = await get_user_by_telegram_id(db_session, str(chat_id))
                if not user:
                    await send_message(chat_id, "Пользователь не найден.", reply_markup=build_reply_keyboard(IDLE))
                    break
                prefs = await get_preferences(db_session, user.id)
                diff = getattr(prefs, 'difficulty', None) or 'Любая'
                calories = getattr(prefs, 'calories_enabled', False)
                healthy = getattr(prefs, 'healthy_mode', False)
                msg = (
                    f'⚙️ <b>Ваши настройки</b>\n'
                    f'Сложность: <b>{diff}</b>\n'
                    f'Подсчёт калорий: <b>{"включён" if calories else "выключён"}</b>\n'
                    f'ЗОЖ‑режим: <b>{"включён" if healthy else "выключён"}</b>'
                )
                await send_message(chat_id, msg, reply_markup=build_reply_keyboard(IDLE))
        await session_store.set_session(chat_id, session_data)
        return

    if state == WAIT_INGREDIENTS:
        if text in MENU_COMMANDS:
            return
        if text and text not in MENU_COMMANDS:
            new_ings = await extract_ingredients(message)
            if new_ings:
                session_data["ingredients"].extend(new_ings)
                session_data["state"] = CONFIRMING
                await send_confirmation(chat_id, session_data["ingredients"])
                await session_store.set_session(chat_id, session_data)
            else:
                await send_message(chat_id, "Не удалось распознать ингредиенты. Попробуйте ещё раз.", reply_markup=build_reply_keyboard(WAIT_INGREDIENTS))
        return

    if state == CONFIRMING:
        if text == CMD_CONFIRM:
            recipe_text = await generate_recipe(
                session_data["ingredients"],
                user_id=chat_id,
                session=session
            )
            await send_message(chat_id, recipe_text)
            session_data["ingredients"] = []
            session_data["state"] = IDLE
            await session_store.set_session(chat_id, session_data)
            return
        if text == CMD_ADD:
            session_data["state"] = ADDING
            await send_message(chat_id, "Пришлите фото или текст, чтобы добавить ингредиенты", reply_markup=build_reply_keyboard(ADDING))
            await session_store.set_session(chat_id, session_data)
            return
        if text == CMD_REMOVE:
            session_data["state"] = REMOVING
            await send_message(chat_id, "Напишите, какой ингредиент убрать", reply_markup=build_reply_keyboard(REMOVING))
            await session_store.set_session(chat_id, session_data)
            return
        if text == CMD_CANCEL:
            session_data["ingredients"] = []
            session_data["state"] = IDLE
            await send_message(chat_id, "Понял вас! Если захотите готовить — нажмите «Главное меню»", reply_markup=build_reply_keyboard(IDLE))
            await session_store.set_session(chat_id, session_data)
            return
        return

    if state == ADDING:
        if text in MENU_COMMANDS:
            # Обработка команд меню даже в этом состоянии
            if text == "Главное":
                await send_message(chat_id, "👨‍🍳 Добро пожаловать в SnapChef!\nЯ помогу подобрать рецепт по фото или списку продуктов.\nВыберите действие из меню ниже.", reply_markup=build_reply_keyboard(IDLE))
                session_data["state"] = WAIT_INGREDIENTS
            elif text == "Помощь":
                await send_message(chat_id, "❓ <b>Помощь</b>\n1. Отправьте фото продуктов или напишите их через запятую.\n2. Следуйте подсказкам бота.\n3. Используйте меню для доступа к сохранённым рецептам и настройкам.", reply_markup=build_reply_keyboard(IDLE))
            elif text == "Сохранённые":
                await send_message(chat_id, "💾 Здесь будут ваши сохранённые рецепты.", reply_markup=build_reply_keyboard(IDLE))
            elif text == "Настройки":
                await send_message(chat_id, "⚙️ Здесь будут ваши настройки.", reply_markup=build_reply_keyboard(IDLE))
            await session_store.set_session(chat_id, session_data)
            return
        new_ings = await extract_ingredients(message)
        session_data["ingredients"].extend(new_ings)
        session_data["state"] = CONFIRMING
        await send_confirmation(chat_id, session_data["ingredients"])
        await session_store.set_session(chat_id, session_data)
        return

    if state == REMOVING:
        if text in MENU_COMMANDS:
            # Обработка команд меню даже в этом состоянии
            if text == "Главное":
                await send_message(chat_id, "👨‍🍳 Добро пожаловать в SnapChef!\nЯ помогу подобрать рецепт по фото или списку продуктов.\nВыберите действие из меню ниже.", reply_markup=build_reply_keyboard(IDLE))
                session_data["state"] = WAIT_INGREDIENTS
            elif text == "Помощь":
                await send_message(chat_id, "❓ <b>Помощь</b>\n1. Отправьте фото продуктов или напишите их через запятую.\n2. Следуйте подсказкам бота.\n3. Используйте меню для доступа к сохранённым рецептам и настройкам.", reply_markup=build_reply_keyboard(IDLE))
            elif text == "Сохранённые":
                await send_message(chat_id, "💾 Здесь будут ваши сохранённые рецепты.", reply_markup=build_reply_keyboard(IDLE))
            elif text == "Настройки":
                await send_message(chat_id, "⚙️ Здесь будут ваши настройки.", reply_markup=build_reply_keyboard(IDLE))
            await session_store.set_session(chat_id, session_data)
            return
        ing_to_remove = text.strip().lower()
        if ing_to_remove in [i.lower() for i in session_data["ingredients"]]:
            session_data["ingredients"] = [i for i in session_data["ingredients"] if i.lower() != ing_to_remove]
        else:
            await send_message(chat_id, f"Ингредиента «{ing_to_remove}» нет в списке.")
        session_data["state"] = CONFIRMING
        await send_confirmation(chat_id, session_data["ingredients"])
        await session_store.set_session(chat_id, session_data)
        return

    if state == IDLE:
        await send_message(chat_id, "Пришлите фото или текст с ингредиентами для начала.", reply_markup=build_reply_keyboard(IDLE))
        session_data["state"] = WAIT_INGREDIENTS
        await session_store.set_session(chat_id, session_data)
        return

    # --- Настройки пользователя ---
    if text == "Сложность":
        async for db_session in get_async_session():
            user = await get_user_by_telegram_id(db_session, str(chat_id))
            if not user:
                await send_message(chat_id, "Пользователь не найден.", reply_markup=build_reply_keyboard(IDLE))
                break
            prefs = await get_preferences(db_session, user.id)
            diff = getattr(prefs, 'difficulty', None) or 'Любая'
            msg = f"Текущая сложность: <b>{diff}</b>\nВыберите новую: 'Любая', 'Простые', 'Средние', 'Сложные'"
            await send_message(chat_id, msg, reply_markup={
                'keyboard': [[{'text': d}] for d in ['Любая', 'Простые', 'Средние', 'Сложные']] + [[{'text': 'Назад'}]],
                'resize_keyboard': True
            })
        return
    if text in ['Любая', 'Простые', 'Средние', 'Сложные']:
        async for db_session in get_async_session():
            user = await get_user_by_telegram_id(db_session, str(chat_id))
            if not user:
                await send_message(chat_id, "Пользователь не найден.", reply_markup=build_reply_keyboard(IDLE))
                break
            await update_preference(db_session, user.id, 'difficulty', text)
            await send_message(chat_id, f"Сложность установлена: <b>{text}</b>", reply_markup=build_reply_keyboard(IDLE))
        return
    if text == "ЗОЖ":
        async for db_session in get_async_session():
            user = await get_user_by_telegram_id(db_session, str(chat_id))
            if not user:
                await send_message(chat_id, "Пользователь не найден.", reply_markup=build_reply_keyboard(IDLE))
                break
            prefs = await get_preferences(db_session, user.id)
            new_val = not prefs.healthy_mode
            await update_preference(db_session, user.id, 'healthy_mode', new_val)
            msg = f"ЗОЖ‑режим {'включён' if new_val else 'выключён'}."
            await send_message(chat_id, msg, reply_markup=build_reply_keyboard(IDLE))
        return
    if text == "Калории":
        async for db_session in get_async_session():
            user = await get_user_by_telegram_id(db_session, str(chat_id))
            if not user:
                await send_message(chat_id, "Пользователь не найден.", reply_markup=build_reply_keyboard(IDLE))
                break
            prefs = await get_preferences(db_session, user.id)
            new_val = not prefs.calories_enabled
            await update_preference(db_session, user.id, 'calories_enabled', new_val)
            msg = f"Подсчёт калорий {'включён' if new_val else 'выключён'}."
            await send_message(chat_id, msg, reply_markup=build_reply_keyboard(IDLE))
        return
    if text == "Назад":
        await send_message(chat_id, "⚙️ Здесь будут ваши настройки.", reply_markup=build_reply_keyboard(IDLE))
        return

async def extract_ingredients(message):
    if message.get("photo"):
        photo_sizes = message["photo"]
        file_id = photo_sizes[-1]["file_id"]
        token = TELEGRAM_BOT_TOKEN
        url = f"https://api.telegram.org/bot{token}/getFile"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params={"file_id": file_id})
            file_path = resp.json()["result"]["file_path"]
        photo_bytes = await download_photo(file_path, token)
        return await extract_ingredients_from_image(photo_bytes)
    elif message.get("text"):
        text = message["text"].strip()
        if text in MENU_COMMANDS:
            return []
        return [i.strip() for i in text.split(",") if i.strip()]
    return []

async def send_confirmation(chat_id, ingredients):
    text = "Распознанные ингредиенты:\n" + "\n".join(f"– {i}" for i in ingredients) + "\nВсё ли верно? Выберите действие:"
    await send_message(chat_id, text, reply_markup=build_reply_keyboard(CONFIRMING))

def build_reply_keyboard(state):
    if state == CONFIRMING:
        return {
            'keyboard': [
                [{'text': '✅ Всё верно, готовим!'}],
                [{'text': '➕ Добавить ингредиент'}, {'text': '➖ Убрать ингредиент'}],
                [{'text': '🛑 Передумал готовить'}]
            ],
            'resize_keyboard': True
        }
    if state == IDLE:
        return {
            'keyboard': [
                [{'text': 'Главное'}],
                [{'text': 'Помощь'}, {'text': 'Сохранённые'}],
                [{'text': 'Настройки'}],
                [{'text': 'Сложность'}, {'text': 'ЗОЖ'}, {'text': 'Калории'}]
            ],
            'resize_keyboard': True
        }
    if state in (ADDING, REMOVING):
        return {'keyboard': [[{'text': 'Назад'}]], 'resize_keyboard': True}
    return {'keyboard': [], 'resize_keyboard': True} 