# telegram_service.py (новая версия)
import os
import logging
import httpx
from session_store import session_store
from vision_service import download_photo, extract_ingredients_from_image
from generate_recipe import generate_recipe
from database import get_async_session
from user_service import get_user_by_telegram_id
from user_preferences_service import get_preferences, update_preference
from recipe_history_service import save_user_recipe, get_user_history
from config.texts import BUTTONS, WELCOME_TEXT, HELP_TEXT, SETTING_STATUS_TEMPLATE, HEALTHY_ON_TEXT, HEALTHY_OFF_TEXT, CUISINE_OPTIONS, CUISINE_SET_TEXT
import json

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
logger = logging.getLogger(__name__)

STATES = {
    'MAIN': 'MAIN',
    'WAIT': 'WAIT_INGREDIENTS',
    'CONFIRM': 'CONFIRMING',
    'ADD': 'ADDING',
    'REMOVE': 'REMOVING',
    'SETTINGS': 'SETTINGS',
    'AFTER_RECIPE': 'AFTER_RECIPE'
}

MENU = {
    'MAIN': [[BUTTONS['start']], [BUTTONS['settings'], BUTTONS['saved']], [BUTTONS['help']]],
    'SETTINGS': [[BUTTONS['back']]],
    'WAIT_INGREDIENTS': [[BUTTONS['back']]],
    'CONFIRMING': [
        [BUTTONS['confirm']],
        [BUTTONS['add'], BUTTONS['remove']],
        [BUTTONS['cancel']]
    ],
    'AFTER_RECIPE': [
        [BUTTONS['confirm']],
        [BUTTONS['add'], BUTTONS['remove']],
        [BUTTONS['cancel']]
    ]
}

def build_keyboard(state):
    if state == "AFTER_RECIPE":
        return {
            "keyboard": [
                [{"text": "💾 Сохранить рецепт"}],
                [{"text": "🔄 Другой рецепт"}],
                [{"text": "⬇️ Проще"}, {"text": "⬆️ Сложнее"}],
                [{"text": "🛑 Завершить готовку"}]
            ],
            "resize_keyboard": True
        }
    return {"keyboard": [[{"text": btn} for btn in row] for row in MENU.get(state, [])], "resize_keyboard": True}

async def send_message(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    async with httpx.AsyncClient() as client:
        await client.post(f"{TELEGRAM_API}/sendMessage", json=payload)

# --- FSM переход ---
async def to_state(chat_id, new_state, message_text, session_data=None):
    """Переход FSM в новое состояние с логированием и комментарием."""
    if session_data is None:
        session_data = await session_store.get_session(chat_id) or {"state": "MAIN", "ingredients": []}
    logger.info(f"[FSM] {chat_id} переход: {session_data['state']} -> {new_state}")
    # Комментарий: сохраняем новое состояние пользователя
    session_data["state"] = new_state
    await send_message(chat_id, message_text, reply_markup=build_keyboard(new_state))
    await session_store.set_session(chat_id, session_data)

# --- FSM handle_update ---
async def handle_update(update, session=None):
    logger.info(f"handle_update called: {update}")
    message = update.get("message")
    if not message or (not message.get("text") and not message.get("photo")):
        if message and "chat" in message:
            await send_message(message["chat"]["id"], "Я вас не понял. Попробуйте использовать меню ниже.")
        return
    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()
    session_data = await session_store.get_session(chat_id) or {"state": "MAIN", "ingredients": []}
    state = session_data["state"]

    # FSM: допустимые команды для каждого состояния
    FSM_COMMANDS = {
        "MAIN": ["/start", BUTTONS["start"], BUTTONS["settings"], BUTTONS["saved"], BUTTONS["help"]],
        "SETTINGS": ["Сложность", "🔁 Назад в меню", "Любая", "Простые", "Средние", "Сложные"],
        "WAIT_INGREDIENTS": ["🔁 Назад в меню"],
        "CONFIRMING": [BUTTONS["confirm"], BUTTONS["add"], BUTTONS["remove"], BUTTONS["cancel"]],
        "AFTER_RECIPE": ["💾 Сохранить рецепт", "🔄 Другой рецепт", "🛑 Завершить готовку"],
        "ADD": [],
        "REMOVE": [],
    }

    # MAIN
    if state == "MAIN":
        if text not in FSM_COMMANDS["MAIN"]:
            return
        if text == "/start":
            await to_state(chat_id, "MAIN", WELCOME_TEXT, session_data)
            return
        if text == "🍳 Начать готовку":
            await to_state(chat_id, "WAIT_INGREDIENTS", "Пришлите фото или текст с ингредиентами.", session_data)
            return
        if text == "⚙️ Настройки":
            await to_state(chat_id, "SETTINGS", "Настройки профиля. Выберите, что хотите изменить:", session_data)
            async for db_session in get_async_session():
                user = await get_user_by_telegram_id(db_session, str(chat_id))
                if user:
                    await send_settings(chat_id, db_session, user.id)
                break
            return
        if text == "💾 Сохранённые":
            async for db_session in get_async_session():
                user = await get_user_by_telegram_id(db_session, str(chat_id))
                if not user:
                    await send_message(chat_id, "Пользователь не найден.", reply_markup=build_keyboard("MAIN"))
                    break
                recipes = await get_user_history(db_session, user.id, limit=10)
                if not recipes:
                    await send_message(chat_id, "У вас пока нет сохранённых рецептов.", reply_markup=build_keyboard("MAIN"))
                    break
                msg = "<b>Ваши сохранённые рецепты:</b>\n\n"
                keyboard = {"inline_keyboard": []}
                for r in recipes:
                    title = r.recipe.split("\n")[0][:40]  # первые 40 символов первой строки
                    date = r.created_at.strftime("%d.%m.%Y") if hasattr(r, 'created_at') else ""
                    btn_text = f"{title} ({date})"
                    keyboard["inline_keyboard"].append([
                        {"text": btn_text, "callback_data": f"show_recipe_{r.id}"}
                    ])
                await send_message(chat_id, msg, reply_markup=keyboard)
            return
        if text == "❓ Помощь":
            await send_message(chat_id, HELP_TEXT, reply_markup=build_keyboard("MAIN"))
            return

    # SETTINGS
    if state == "SETTINGS":
        if text in ["Любая", "Простые", "Средние", "Сложные"]:
            async for db_session in get_async_session():
                user = await get_user_by_telegram_id(db_session, str(chat_id))
                if not user:
                    await send_message(chat_id, "Пользователь не найден.", reply_markup=build_keyboard("SETTINGS"))
                    break
                await update_preference(db_session, user.id, 'difficulty', text)
                logger.info(f"[FSM] {chat_id} выбрал сложность: {text}")
                await send_settings(chat_id, db_session, user.id)
            return
        if text not in FSM_COMMANDS["SETTINGS"]:
            if message.get("photo"):
                await send_message(chat_id, "Сейчас вы в настройках, используйте кнопки ниже.", reply_markup=build_keyboard("SETTINGS"))
            return
        if text == "Сложность":
            await send_message(chat_id, "Выберите сложность:", reply_markup={
                'keyboard': [[{'text': d}] for d in ['Любая', 'Простые', 'Средние', 'Сложные']] + [[{'text': '🔁 Назад в меню'}]],
                'resize_keyboard': True
            })
            return
        if text == "🔁 Назад в меню":
            await to_state(chat_id, "MAIN", "Вы вернулись в главное меню.", session_data)
            return

    # WAIT_INGREDIENTS
    if state == "WAIT_INGREDIENTS":
        if text in FSM_COMMANDS["WAIT_INGREDIENTS"]:
            if text == "🔁 Назад в меню":
                await to_state(chat_id, "MAIN", "Вы вернулись в главное меню.", session_data)
            return
        # Только фото или текст — ингредиенты
        if message.get("photo") or (text and text not in BUTTONS.values()):
            if message.get("photo"):
                await send_message(chat_id, "📷 Фото получено! Сейчас гляну…")
            new_ings = await extract_ingredients(message)
            if new_ings:
                session_data["ingredients"].extend(new_ings)
                await to_state(chat_id, "CONFIRMING", "Распознанные ингредиенты:\n" + "\n".join(f"– {i}" for i in session_data["ingredients"]) + "\nВсё ли верно? Выберите действие:", session_data)
            else:
                await send_message(chat_id, "❌ Хмм, не вижу съедобного. Попробуй другое фото.", reply_markup=build_keyboard("WAIT_INGREDIENTS"))
            return
        # Всё остальное игнорируем
        return

    # ADD
    if state == "ADD":
        if text and text not in BUTTONS.values():
            session_data["ingredients"].append(text)
            await to_state(chat_id, "CONFIRMING", "Ингредиент добавлен.\n" + "\n".join(f"– {i}" for i in session_data["ingredients"]) + "\nВсё ли верно? Выберите действие:", session_data)
        return

    # REMOVE
    if state == "REMOVE":
        if text and text not in BUTTONS.values():
            ing_lower = text.lower()
            found = False
            for i in session_data["ingredients"]:
                if i.lower() == ing_lower:
                    session_data["ingredients"].remove(i)
                    found = True
                    break
            if found:
                await to_state(chat_id, "CONFIRMING", f"Ингредиент '{text}' удалён.\n" + "\n".join(f"– {i}" for i in session_data["ingredients"]) + "\nВсё ли верно? Выберите действие:", session_data)
            else:
                await to_state(chat_id, "CONFIRMING", f"Ингредиент '{text}' не найден в списке.\n" + "\n".join(f"– {i}" for i in session_data["ingredients"]) + "\nВсё ли верно? Выберите действие:", session_data)
        return

    # CONFIRMING
    if state == "CONFIRMING":
        if text not in FSM_COMMANDS["CONFIRMING"]:
            await send_message(chat_id, "Пожалуйста, выберите вариант из меню ниже или загрузите продукты. 👇", reply_markup=build_keyboard("CONFIRMING"))
            return
        if text == BUTTONS["add"]:
            session_data["state"] = "ADD"
            logger.info(f"[FSM] {chat_id} -> ADD (добавление ингредиента)")
            await send_message(chat_id, "Пришлите ингредиент для добавления…", reply_markup=build_keyboard("ADD"))
            await session_store.set_session(chat_id, session_data)
            return
        if text == BUTTONS["remove"]:
            session_data["state"] = "REMOVE"
            logger.info(f"[FSM] {chat_id} -> REMOVE (удаление ингредиента)")
            await send_message(chat_id, "Напишите ингредиент для удаления…", reply_markup=build_keyboard("REMOVE"))
            await session_store.set_session(chat_id, session_data)
            return
        if text == "✅ Всё верно, готовим!":
            await send_message(chat_id, "👨‍🍳 Думаю… Сейчас придумаем что-то вкусненькое!")
            try:
                recipe_text = await generate_recipe(
                    session_data["ingredients"],
                    user_id=chat_id,
                    session=session
                )
                session_data["last_recipe"] = recipe_text
                await send_message(chat_id, recipe_text, reply_markup=build_keyboard("AFTER_RECIPE"))
                await to_state(chat_id, "AFTER_RECIPE", "Что дальше? Выберите действие:", session_data)
            except Exception as e:
                logger.error(f"Ошибка генерации рецепта: {e}")
                await send_message(chat_id, "⚠️ Что-то пошло не так. Попробуйте ещё раз.", reply_markup=build_keyboard("CONFIRMING"))
            return
        if text == "🛑 Передумал готовить":
            session_data["ingredients"] = []
            await to_state(chat_id, "MAIN", "Готовка отменена. Вы в главном меню.", session_data)
            return

    # AFTER_RECIPE
    if state == "AFTER_RECIPE":
        if text not in FSM_COMMANDS["AFTER_RECIPE"] + ["⬇️ Проще", "⬆️ Сложнее"]:
            await send_message(chat_id, "Пожалуйста, выберите вариант из меню ниже или загрузите продукты. 👇", reply_markup=build_keyboard("AFTER_RECIPE"))
            return
        if text == "💾 Сохранить рецепт":
            try:
                await save_recipe(chat_id, session_data.get("ingredients", []), session_data.get("last_recipe", ""))
                await send_message(chat_id, "✅ Рецепт сохранён в ваши избранные.", reply_markup=build_keyboard("AFTER_RECIPE"))
            except Exception as e:
                logger.error(f"Ошибка сохранения рецепта: {e}")
                await send_message(chat_id, "⚠️ Что-то пошло не так. Попробуйте ещё раз.", reply_markup=build_keyboard("AFTER_RECIPE"))
            return
        if text == "🔄 Другой рецепт":
            await send_message(chat_id, "👨‍🍳 Думаю… Сейчас придумаем что-то вкусненькое!")
            try:
                recipe_text = await generate_recipe(
                    session_data["ingredients"],
                    user_id=chat_id,
                    session=session
                )
                session_data["last_recipe"] = recipe_text
                await send_message(chat_id, recipe_text, reply_markup=build_keyboard("AFTER_RECIPE"))
            except Exception as e:
                logger.error(f"Ошибка генерации рецепта: {e}")
                await send_message(chat_id, "⚠️ Что-то пошло не так. Попробуйте ещё раз.", reply_markup=build_keyboard("AFTER_RECIPE"))
            return
        if text in ["⬇️ Проще", "⬆️ Сложнее"]:
            # Получаем текущую сложность (приоритет temp_difficulty, затем из профиля)
            DIFFICULTY_ORDER = ["Простые", "Средние", "Сложные"]
            async for db_session in get_async_session():
                user = await get_user_by_telegram_id(db_session, str(chat_id))
                prefs = await get_preferences(db_session, user.id) if user else None
                current = session_data.get("temp_difficulty")
                if not current:
                    current = getattr(prefs, "difficulty", "Средние")
                    if current not in DIFFICULTY_ORDER:
                        current = "Средние"
                idx = DIFFICULTY_ORDER.index(current)
                if text == "⬇️ Проще" and idx > 0:
                    new_difficulty = DIFFICULTY_ORDER[idx - 1]
                elif text == "⬆️ Сложнее" and idx < len(DIFFICULTY_ORDER) - 1:
                    new_difficulty = DIFFICULTY_ORDER[idx + 1]
                else:
                    new_difficulty = current
                session_data["temp_difficulty"] = new_difficulty
                await send_message(chat_id, f"👨‍🍳 Думаю… Сейчас придумаем что-то вкусненькое! (Сложность: {new_difficulty})")
                try:
                    recipe_text = await generate_recipe(
                        session_data["ingredients"],
                        user_id=chat_id,
                        session=session,
                        temp_difficulty=new_difficulty
                    )
                    session_data["last_recipe"] = recipe_text
                    await send_message(chat_id, recipe_text, reply_markup=build_keyboard("AFTER_RECIPE"))
                except Exception as e:
                    logger.error(f"Ошибка генерации рецепта: {e}")
                    await send_message(chat_id, "⚠️ Что-то пошло не так. Попробуйте ещё раз.", reply_markup=build_keyboard("AFTER_RECIPE"))
                break
            return
        if text == "🛑 Завершить готовку":
            session_data["ingredients"] = []
            await to_state(chat_id, "MAIN", "Готовка завершена. Вы в главном меню.", session_data)
            return

    # Если состояние неизвестно — вернуть в MAIN
    if state not in FSM_COMMANDS:
        await to_state(chat_id, "MAIN", "Вы в главном меню. Выберите действие:", session_data)
        return

    # В каждом активном состоянии обработка мусорного ввода
    if state in FSM_COMMANDS and text not in FSM_COMMANDS[state]:
        await send_message(chat_id, "Пожалуйста, выберите вариант из меню ниже или загрузите продукты. 👇", reply_markup=build_keyboard(state))
        return

async def extract_ingredients(msg):
    if msg.get("photo"):
        file_id = msg["photo"][-1]["file_id"]
        async with httpx.AsyncClient() as client:
            r = await client.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile", params={"file_id": file_id})
            path = r.json()["result"]["file_path"]
        photo = await download_photo(path, TELEGRAM_BOT_TOKEN)
        return await extract_ingredients_from_image(photo)
    if msg.get("text"):
        return [i.strip() for i in msg["text"].split(",") if i.strip()]
    return []

def build_settings_inline_keyboard(healthy_profile, cuisine, difficulty):
    return {
        "inline_keyboard": [
            [
                {
                    "text": f"🥗 Здоровое питание: {'✅' if healthy_profile else '❌'}",
                    "callback_data": "toggle_healthy_profile"
                }
            ],
            [
                {
                    "text": f"🍱 Кухня: {cuisine}",
                    "callback_data": "choose_cuisine"
                }
            ],
            [
                {
                    "text": f"🎚️ Сложность: {difficulty}",
                    "callback_data": "choose_difficulty"
                }
            ]
        ]
    }

async def send_settings(chat_id, db_session, user_id, message_id=None):
    CUISINE_OPTIONS = ["Любая", "Европейская", "Азиатская", "Мексиканская", "Восточная", "Индийская"]
    DIFFICULTY_OPTIONS = ["Любая", "Простые", "Средние", "Сложные"]
    prefs = await get_preferences(db_session, user_id)
    healthy_profile = getattr(prefs, 'healthy_profile', False)
    cuisine = getattr(prefs, 'preferred_cuisine', 'Любая')
    difficulty = getattr(prefs, 'difficulty', 'Любая')
    if cuisine not in CUISINE_OPTIONS:
        cuisine = "Любая"
    if difficulty not in DIFFICULTY_OPTIONS:
        difficulty = "Любая"
    healthy_text = 'Вкл' if healthy_profile else 'Выкл'
    msg = f"<b>🥗 Здоровое питание:</b> {healthy_text}\n<b>🍱 Кухня:</b> {cuisine}\n<b>🎚️ Сложность:</b> {difficulty}"
    keyboard = build_settings_inline_keyboard(healthy_profile, cuisine, difficulty)
    if message_id:
        await edit_message_text(chat_id, message_id, msg, keyboard)
    else:
        await send_message(chat_id, msg, reply_markup=keyboard)

async def edit_message_text(chat_id, message_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    async with httpx.AsyncClient() as client:
        await client.post(f"{TELEGRAM_API}/editMessageText", json=payload)

async def save_recipe(chat_id, ingredients, recipe_text):
    async for db_session in get_async_session():
        user = await get_user_by_telegram_id(db_session, str(chat_id))
        if not user:
            return
        await save_user_recipe(db_session, user.id, recipe_text, ingredients)

# Обработка callback-запросов для inline-кнопок
async def handle_callback_query(callback_query, session=None):
    chat_id = callback_query["message"]["chat"]["id"]
    message_id = callback_query["message"]["message_id"]
    data = callback_query["data"]
    if data.startswith("show_recipe_"):
        recipe_id = int(data.replace("show_recipe_", ""))
        async for db_session in get_async_session():
            user = await get_user_by_telegram_id(db_session, str(chat_id))
            if not user:
                await send_message(chat_id, "Пользователь не найден.")
                break
            from sqlalchemy.future import select
            from models import RecipeHistory
            result = await db_session.execute(select(RecipeHistory).where(RecipeHistory.id == recipe_id, RecipeHistory.user_id == user.id))
            recipe = result.scalars().first()
            if not recipe:
                await send_message(chat_id, "Рецепт не найден.")
                break
            await send_message(chat_id, f"<b>Полный рецепт:</b>\n\n{recipe.recipe}")
        return
    if data == "toggle_healthy_profile":
        async for db_session in get_async_session():
            user = await get_user_by_telegram_id(db_session, str(chat_id))
            if not user:
                await edit_message_text(chat_id, message_id, "Пользователь не найден.")
                break
            prefs = await get_preferences(db_session, user.id)
            new_val = not getattr(prefs, 'healthy_profile', False)
            await update_preference(db_session, user.id, 'healthy_profile', new_val)
            logger.info(f"[SETTINGS] {chat_id} переключил здоровое питание: {new_val}")
            text = "Режим здорового питания включён." if new_val else "Режим здорового питания выключен."
            await edit_message_text(chat_id, message_id, text)
            await send_settings(chat_id, db_session, user.id)
        return
    if data == "choose_cuisine":
        CUISINE_OPTIONS = ["Любая", "Европейская", "Азиатская", "Мексиканская", "Восточная", "Индийская"]
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": c, "callback_data": f"set_cuisine_{c}"} for c in CUISINE_OPTIONS
                ]
            ]
        }
        await edit_message_text(chat_id, message_id, "Выберите кухню:", keyboard)
        return
    if data.startswith("set_cuisine_"):
        cuisine = data.replace("set_cuisine_", "")
        CUISINE_OPTIONS = ["Любая", "Европейская", "Азиатская", "Мексиканская", "Восточная", "Индийская"]
        if cuisine not in CUISINE_OPTIONS:
            cuisine = "Любая"
        async for db_session in get_async_session():
            user = await get_user_by_telegram_id(db_session, str(chat_id))
            if not user:
                await edit_message_text(chat_id, message_id, "Пользователь не найден.")
                break
            await update_preference(db_session, user.id, 'preferred_cuisine', cuisine)
            logger.info(f"[SETTINGS] {chat_id} выбрал кухню: {cuisine}")
            text = f"Вы выбрали кухню: {cuisine}."
            await edit_message_text(chat_id, message_id, text)
            await send_settings(chat_id, db_session, user.id)
        return
    if data == "settings_back":
        await edit_message_text(chat_id, message_id, "Вы вернулись в главное меню.")
        return
    if data == "choose_difficulty":
        DIFFICULTY_OPTIONS = ["Любая", "Простые", "Средние", "Сложные"]
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": d, "callback_data": f"set_difficulty_{d}"} for d in DIFFICULTY_OPTIONS
                ]
            ]
        }
        await edit_message_text(chat_id, message_id, "Выберите сложность:", keyboard)
        return
    if data.startswith("set_difficulty_"):
        difficulty = data.replace("set_difficulty_", "")
        DIFFICULTY_OPTIONS = ["Любая", "Простые", "Средние", "Сложные"]
        if difficulty not in DIFFICULTY_OPTIONS:
            difficulty = "Любая"
        async for db_session in get_async_session():
            user = await get_user_by_telegram_id(db_session, str(chat_id))
            if not user:
                await edit_message_text(chat_id, message_id, "Пользователь не найден.")
                break
            await update_preference(db_session, user.id, 'difficulty', difficulty)
            logger.info(f"[SETTINGS] {chat_id} выбрал сложность: {difficulty}")
            text = f"Вы выбрали сложность: {difficulty}."
            await edit_message_text(chat_id, message_id, text)
            await send_settings(chat_id, db_session, user.id)
        return
