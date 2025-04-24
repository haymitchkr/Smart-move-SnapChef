import os
import logging
from fastapi import FastAPI, Request, BackgroundTasks
from dotenv import load_dotenv
from telegram_service import handle_update
import httpx
import subprocess
from database import get_async_session

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

@app.on_event('startup')
async def startup():
    # Автоматически применяем миграции Alembic
    subprocess.run(["alembic", "upgrade", "head"])
    # Ставим вебхук
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook'
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json={'url': WEBHOOK_URL})
        logger.info(f'Webhook set: {r.text}')

@app.post('/webhook')
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    print(">>> /webhook endpoint called")
    logger.info(">>> /webhook endpoint called")
    update = await request.json()
    logger.info(f'Update: {update}')
    if 'callback_query' in update:
        from telegram_service import handle_callback_query
        background_tasks.add_task(handle_callback_query, update['callback_query'])
    else:
        background_tasks.add_task(handle_update, update)
    return {"ok": True} 