import httpx
from telegram import Update
from telegram.ext import ContextTypes
from claude_client import parse_receipt
import pocketbase


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    await msg.reply_text("Processing receipt... 🧾")

    photo = msg.photo[-1]  # largest resolution
    tg_file = await context.bot.get_file(photo.file_id)

    async with httpx.AsyncClient() as client:
        resp = await client.get(tg_file.file_path)
        resp.raise_for_status()
        image_bytes = resp.content

    try:
        data = await parse_receipt(image_bytes)
    except Exception as e:
        await msg.reply_text(f"❌ Could not parse receipt: {e}")
        return

    receipt = await pocketbase.create_record("receipts", {
        "merchant": data.get("merchant"),
        "date": data.get("date"),
        "total": data.get("total"),
        "currency": data.get("currency") or "EUR",
        "raw": data,
    })

    items = data.get("items") or []
    for item in items:
        await pocketbase.create_record("receipt_items", {
            "receipt": receipt["id"],
            "name": item.get("name"),
            "quantity": item.get("quantity", 1),
            "unit_price": item.get("unit_price"),
            "total_price": item.get("total_price"),
        })

    summary = "\n".join(f"  • {i.get('name')} — {i.get('total_price')}" for i in items)
    await msg.reply_text(
        f"✅ *{data.get('merchant')}* — {data.get('date')}\n"
        f"Total: *{data.get('total')} {data.get('currency', 'EUR')}*\n\n"
        f"{summary}",
        parse_mode="Markdown",
    )
