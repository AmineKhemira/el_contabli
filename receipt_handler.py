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
        "store": data.get("store"),
        "date": data.get("date"),
        "total": data.get("total"),
        "source": "photo",
        "store_category": "supermarket",
    })

    items = data.get("items") or []
    for item in items:
        await pocketbase.create_record("receipt_items", {
            "receipt_id": receipt["id"],
            "name": item.get("name"),
            "quantity": item.get("quantity", 1),
            "price": item.get("price"),
            "category": item.get("category"),
            "wasted": False,
        })

    summary = "\n".join(f"  • {i.get('name')} — {i.get('price')}" for i in items)
    await msg.reply_text(
        f"✅ *{data.get('store')}* — {data.get('date')}\n"
        f"Total: *{data.get('total')}*\n\n"
        f"{summary}",
        parse_mode="Markdown",
    )
