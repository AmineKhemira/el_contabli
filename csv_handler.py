import csv
import io
import logging
import httpx
from telegram import Update
from telegram.ext import ContextTypes
import pocketbase

logger = logging.getLogger(__name__)

# German Revolut CSV columns:
# Typ, Produkt, Startdatum, Datum des Abschlusses, Beschreibung, Betrag, Gebühr, Währung, Status, Guthaben
_COMPLETED_STATUSES = {"COMPLETED", "ABGESCHLOSSEN"}
_REQUIRED_COLUMNS = {"Status", "Datum des Abschlusses", "Beschreibung", "Betrag"}


def _decode_csv(raw: bytes) -> str:
    """Try UTF-8-BOM, then cp1252 (Windows Western European), then latin-1."""
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = raw.decode(encoding)
            logger.info("CSV decoded with encoding=%s", encoding)
            return text
        except UnicodeDecodeError:
            continue
    raise ValueError("Could not decode CSV with any known encoding")


async def handle_import(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg.document or not msg.document.file_name.endswith(".csv"):
        await msg.reply_text("Please attach a Revolut CSV file.")
        return

    filename = msg.document.file_name
    logger.info("Import started: file=%s size=%s", filename, msg.document.file_size)

    # --- Download ---
    try:
        tg_file = await context.bot.get_file(msg.document.file_id)
        async with httpx.AsyncClient() as client:
            resp = await client.get(tg_file.file_path)
            resp.raise_for_status()
            raw = resp.content
    except Exception as e:
        logger.error("Download failed: %s", e)
        await msg.reply_text(f"❌ Could not download file: {e}")
        return

    # --- Decode ---
    try:
        content = _decode_csv(raw)
    except ValueError as e:
        logger.error("Encoding error: %s", e)
        await msg.reply_text(f"❌ Encoding error: {e}")
        return

    # --- Parse CSV ---
    reader = csv.DictReader(io.StringIO(content))
    columns = reader.fieldnames or []
    logger.info("CSV columns detected: %s", columns)

    missing = _REQUIRED_COLUMNS - set(columns)
    if missing:
        logger.error("Missing columns: %s", missing)
        await msg.reply_text(
            f"❌ CSV is missing expected columns: `{', '.join(sorted(missing))}`\n"
            f"Found columns: `{', '.join(columns)}`",
            parse_mode="Markdown",
        )
        return

    imported = 0
    skipped = 0
    failed = 0

    for i, row in enumerate(reader):
        status = row.get("Status", "").strip()
        description = row.get("Beschreibung", "").strip()
        date_raw = row.get("Datum des Abschlusses", "").strip()
        betrag_raw = row.get("Betrag", "").strip()

        logger.debug("Row %d: status=%r date=%r merchant=%r amount=%r", i, status, date_raw, description, betrag_raw)

        if status.upper() not in _COMPLETED_STATUSES:
            logger.info("Row %d skipped: status=%r", i, status)
            skipped += 1
            continue

        # --- Parse amount ---
        try:
            # Revolut may use comma as decimal separator in German locale
            amount = float(betrag_raw.replace(",", "."))
        except ValueError:
            logger.warning("Row %d: cannot parse amount %r — skipping", i, betrag_raw)
            failed += 1
            continue

        # --- Parse date ---
        date = date_raw[:10] if len(date_raw) >= 10 else date_raw

        # --- Write to Pocketbase ---
        try:
            await pocketbase.create_record("transactions", {
                "date": date,
                "merchant": description,
                "amount": amount,
                "source": "revolut_csv",
            })
            logger.info("Row %d imported: date=%s merchant=%r amount=%s", i, date, description, amount)
            imported += 1
        except Exception as e:
            logger.error("Row %d: Pocketbase write failed: %s | data: date=%s merchant=%r amount=%s", i, e, date, description, amount)
            failed += 1

    logger.info("Import complete: imported=%d skipped=%d failed=%d", imported, skipped, failed)

    parts = [f"✅ Import complete for *{filename}*\n"]
    parts.append(f"  • Imported: *{imported}*")
    parts.append(f"  • Skipped (not completed): *{skipped}*")
    if failed:
        parts.append(f"  • Failed (errors): *{failed}*")
    await msg.reply_text("\n".join(parts), parse_mode="Markdown")


async def handle_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    args = context.args  # optional: month like "2026-05"

    params: dict = {"sort": "-date", "perPage": 500}
    if args:
        month = args[0]
        params["filter"] = f'date >= "{month}-01" && date <= "{month}-31"'

    logger.info("Export started: filter=%s", params.get("filter", "none"))

    try:
        records = await pocketbase.list_records("transactions", params)
    except Exception as e:
        logger.error("Export: Pocketbase fetch failed: %s", e)
        await msg.reply_text(f"❌ Could not fetch transactions: {e}")
        return

    if not records:
        await msg.reply_text("No transactions found for the requested period.")
        return

    logger.info("Export: fetched %d records", len(records))

    try:
        buf = io.StringIO()
        fields = ["date", "merchant", "amount", "category", "source", "notes"]
        writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)
        csv_bytes = buf.getvalue().encode("utf-8-sig")  # BOM so Excel opens it correctly
    except Exception as e:
        logger.error("Export: CSV serialisation failed: %s", e)
        await msg.reply_text(f"❌ Could not build CSV: {e}")
        return

    filename = f"transactions_{args[0] if args else 'all'}.csv"
    await msg.reply_document(
        document=csv_bytes,
        filename=filename,
        caption=f"📊 {len(records)} transactions exported.",
    )
    logger.info("Export complete: file=%s rows=%d", filename, len(records))
