import os
import json
import logging
from typing import Optional
from redis.asyncio import Redis
from dotenv import load_dotenv

load_dotenv()

REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))

logger = logging.getLogger(__name__)

class SessionStore:
    def __init__(self):
        self.redis: Optional[Redis] = None

    async def connect(self):
        if not self.redis:
            self.redis = Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
            logger.info('Redis connected')

    async def set_session(self, chat_id: int, data: dict):
        try:
            await self.connect()
            await self.redis.set(f"session:{chat_id}", json.dumps(data))
            logger.info(f"Session set for {chat_id}: {data}")
        except Exception as e:
            logger.error(f"Redis set_session error: {e}")

    async def get_session(self, chat_id: int) -> Optional[dict]:
        try:
            await self.connect()
            raw = await self.redis.get(f"session:{chat_id}")
            if raw:
                logger.info(f"Session get for {chat_id}: {raw}")
                return json.loads(raw)
        except Exception as e:
            logger.error(f"Redis get_session error: {e}")
        return None

    UPDATE_INGREDIENTS_LUA = """
    local key = KEYS[1]
    local add = cjson.decode(ARGV[1])
    local session = redis.call('GET', key)
    if not session then
        session = {ingredients = {}}
    else
        session = cjson.decode(session)
    end
    local set = {}
    for _, v in ipairs(session.ingredients or {}) do set[v] = true end
    for _, v in ipairs(add) do set[v] = true end
    local result = {}
    for k, _ in pairs(set) do table.insert(result, k) end
    session.ingredients = result
    redis.call('SET', key, cjson.encode(session))
    return cjson.encode(session)
    """

    async def update_ingredients(self, chat_id: int, new_ingredients: list):
        try:
            await self.connect()
            key = f"session:{chat_id}"
            result = await self.redis.eval(self.UPDATE_INGREDIENTS_LUA, 1, key, json.dumps(new_ingredients))
            logger.info(f"Session updated for {chat_id}: {result}")
        except Exception as e:
            logger.error(f"Redis update_ingredients error: {e}")

    REMOVE_INGREDIENTS_LUA = """
    local key = KEYS[1]
    local remove = cjson.decode(ARGV[1])
    local session = redis.call('GET', key)
    if not session then return nil end
    session = cjson.decode(session)
    local ingredients = {}
    for _, v in ipairs(session.ingredients or {}) do
        local found = false
        for _, r in ipairs(remove) do
            if v == r then found = true break end
        end
        if not found then table.insert(ingredients, v) end
    end
    session.ingredients = ingredients
    redis.call('SET', key, cjson.encode(session))
    return cjson.encode(session)
    """

    async def remove_ingredients(self, chat_id: int, remove_ingredients: list):
        try:
            await self.connect()
            key = f"session:{chat_id}"
            result = await self.redis.eval(self.REMOVE_INGREDIENTS_LUA, 1, key, json.dumps(remove_ingredients))
            logger.info(f"Session ingredients removed for {chat_id}: {result}")
        except Exception as e:
            logger.error(f"Redis remove_ingredients error: {e}")

    async def set_state(self, chat_id: int, state: str):
        try:
            await self.connect()
            session = await self.get_session(chat_id) or {}
            session['state'] = state
            await self.set_session(chat_id, session)
            logger.info(f"State set for {chat_id}: {state}")
        except Exception as e:
            logger.error(f"Redis set_state error: {e}")

    async def get_state(self, chat_id: int) -> str:
        session = await self.get_session(chat_id) or {}
        return session.get('state', 'idle')

    async def clear_session(self, chat_id: int):
        try:
            await self.connect()
            await self.redis.delete(f"session:{chat_id}")
            logger.info(f"Session cleared for {chat_id}")
        except Exception as e:
            logger.error(f"Redis clear_session error: {e}")

session_store = SessionStore() 