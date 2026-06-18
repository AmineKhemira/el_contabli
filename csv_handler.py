import csv
import io
import httpx
from telegram import Update
from telegram.ext import ContextTypes
import pocketbase

# German Revolut CSV columns:
# Typ, Produkt, Startdatum, Datum des Abschlusses, Beschreibung, Betrag, Gebühr, Währung, Status, Guthaben
_COMPLETED_STATUSES = {"COMPLETED", "Abgeschlossen"}


async def handle_import(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg.document or not msg.document.file_name.endswith(".csv"):
        await msg.reply_text("Please attach a Revolut CSV file.")
        return

    tg_file = await context.bot.get_file(msg.document.file_id)
    async with httpx.AsyncClient() as client:
        resp = await client.get(tg_file.file_path)
        resp.raise_for_status()
        content = resp.text

    reader = csv.DictReader(io.StringIO(content))
    imported = 0
    skipped = 0
    for row in reader:
        if row.get("Status") not in _COMPLETED_STATUSES:
            skipped += 1
            continue
        await pocketbase.create_record("transactions", {
            "date": row["Datum des Abschlusses"][:10],
            "merchant": row["Beschreibung"],
            "amount": float(row["Betrag"]),
            "source": "revolut_csv",
        })
        imported += 1

    await msg.reply_text(f"✅ Imported *{imported}* transactions ({skipped} skipped).", parse_mode="Markdown")


async def handle_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    args = context.args  # optional: month like "2026-05"

    params: dict = {"sort": "-date", "perPage": 500}
    if args:
        month = args[0]  # e.g. 2026-05
        params["filter"] = f'date >= "{month}-01" && date <= "{month}-31"'

    records = await pocketbase.list_records("transactions", params)

    buf = io.StringIO()
    fields = ["date", "description", "amount", "currency", "type", "category"]
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(records)

    filename = f"transactions_{args[0] if args else 'all'}.csv"
    await msg.reply_document(
        document=buf.getvalue().encode(),
        filename=filename,
        caption="Here's your export 📊",
    )
