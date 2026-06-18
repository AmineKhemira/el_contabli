import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
POCKETBASE_URL = os.environ["POCKETBASE_URL"].rstrip("/")
POCKETBASE_EMAIL = os.environ["POCKETBASE_EMAIL"]
POCKETBASE_PASSWORD = os.environ["POCKETBASE_PASSWORD"]
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")
