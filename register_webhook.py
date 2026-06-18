"""One-shot script: set the Telegram webhook URL."""
import asyncio
import sys
from telegram import Bot
from config import TELEGRAM_BOT_TOKEN, WEBHOOK_SECRET

async def main():
    if len(sys.argv) < 2:
        print("Usage: python register_webhook.py https://your-tunnel.trycloudflare.com")
        sys.exit(1)
    base = sys.argv[1].rstrip("/")
    url = f"{base}/webhook/telegram/{WEBHOOK_SECRET}"
    async with Bot(TELEGRAM_BOT_TOKEN) as bot:
        await bot.set_webhook(url)
        info = await bot.get_webhook_info()
        print(f"Webhook set: {info.url}")

asyncio.run(main())
