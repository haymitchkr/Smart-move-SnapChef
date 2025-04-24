import os
import httpx
from dotenv import load_dotenv
import time

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_PATH = "/webhook"
PORT = 8000
ENV_PATH = ".env"
STATIC_NGROK_DOMAIN = "moccasin-sunny-bat.ngrok-free.app"

async def set_webhook():
    webhook_url = f"https://{STATIC_NGROK_DOMAIN}{WEBHOOK_PATH}"
    print(f"🔗 Устанавливаем webhook: {webhook_url}")
    async with httpx.AsyncClient() as client:
        # Сбросить старый webhook
        print("🧹 Сбрасываем старый webhook...")
        await client.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook", json={"url": ""})
        resp = await client.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook",
            json={"url": webhook_url}
        )
        print(f"✅ Ответ Telegram: {resp.json()}")
    update_env(webhook_url)

async def clear_old_updates():
    print("🧹 Очищаем старые апдейты Telegram...")
    async with httpx.AsyncClient() as client:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
        resp = await client.get(url, params={"offset": -1})
        print(f"✅ Очередь апдейтов очищена: {resp.json()}")


def update_env(webhook_url):
    print(f"📄 Обновляем {ENV_PATH} переменной WEBHOOK_URL...")
    lines = []
    found = False

    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r") as f:
            for line in f:
                if line.startswith("WEBHOOK_URL="):
                    lines.append(f"WEBHOOK_URL={webhook_url}\n")
                    found = True
                else:
                    lines.append(line)

    if not found:
        lines.append(f"WEBHOOK_URL={webhook_url}\n")

    with open(ENV_PATH, "w") as f:
        f.writelines(lines)
    print("✅ .env обновлён!")

if __name__ == "__main__":
    import asyncio
    asyncio.run(set_webhook())
    asyncio.run(clear_old_updates())
    print("⚙️ Запускаем FastAPI...")
    import subprocess
    subprocess.call(["uvicorn", "main:app", "--host", "0.0.0.0", "--port", str(PORT)])
