import logging
import hmac
import hashlib
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

import config
from receipt_handler import handle_photo
from csv_handler import handle_import, handle_export
from report_handler import handle_report
import pocketbase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_bot_app: Application | None = None


def build_bot() -> Application:
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(
        MessageHandler(filters.Document.MimeType("text/csv") | filters.Document.FileExtension("csv"), handle_import)
    )
    app.add_handler(CommandHandler("import", handle_import))
    app.add_handler(CommandHandler("export", handle_export))
    app.add_handler(CommandHandler("report", handle_report))
    app.add_handler(CommandHandler("start", _cmd_start))
    return app


async def _cmd_start(update, context):
    await update.message.reply_text(
        "👋 *El Contabli* at your service!\n\n"
        "📸 Send a receipt photo to log it\n"
        "📎 `/import` — attach a Revolut CSV\n"
        "📊 `/export [YYYY-MM]` — download transactions\n"
        "📈 `/report [YYYY-MM]` — monthly AI report",
        parse_mode="Markdown",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _bot_app
    _bot_app = build_bot()
    await _bot_app.initialize()
    yield
    await _bot_app.shutdown()


web = FastAPI(lifespan=lifespan)


@web.post("/webhook/telegram/{secret}")
async def telegram_webhook(secret: str, request: Request):
    if config.WEBHOOK_SECRET and not hmac.compare_digest(secret, config.WEBHOOK_SECRET):
        raise HTTPException(status_code=403)
    body = await request.json()
    update = Update.de_json(body, _bot_app.bot)
    await _bot_app.process_update(update)
    return {"ok": True}


@web.post("/transaction")
async def tasker_transaction(request: Request):
    """Tasker / Revolut push notification webhook."""
    data = await request.json()
    # Expected fields: amount, currency, description, date (ISO)
    required = {"amount", "description"}
    if not required.issubset(data):
        raise HTTPException(status_code=422, detail=f"Missing fields: {required - data.keys()}")

    record = await pocketbase.create_record("transactions", {
        "date": data.get("date", ""),
        "description": data["description"],
        "amount": float(data["amount"]),
        "currency": data.get("currency", "EUR"),
        "type": "income" if float(data["amount"]) > 0 else "expense",
        "source": "tasker",
    })
    return {"id": record["id"]}


@web.get("/health")
async def health():
    return {"status": "ok"}
