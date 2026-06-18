import datetime
from telegram import Update
from telegram.ext import ContextTypes
from claude_client import monthly_report
import pocketbase


async def handle_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    args = context.args

    if args:
        month = args[0]  # YYYY-MM
    else:
        today = datetime.date.today()
        month = f"{today.year}-{today.month - 1:02d}" if today.month > 1 else f"{today.year - 1}-12"

    await msg.reply_text(f"Generating report for *{month}*... ⏳", parse_mode="Markdown")

    transactions = await pocketbase.list_records("transactions", {
        "filter": f'date >= "{month}-01" && date <= "{month}-31"',
        "perPage": 1000,
    })
    budgets = await pocketbase.list_records("budgets", {"perPage": 100})

    if not transactions:
        await msg.reply_text(f"No transactions found for {month}.")
        return

    report_text = await monthly_report(month, transactions, budgets)
    # Telegram message limit is 4096 chars
    if len(report_text) > 4000:
        for chunk in [report_text[i:i+4000] for i in range(0, len(report_text), 4000)]:
            await msg.reply_text(chunk, parse_mode="Markdown")
    else:
        await msg.reply_text(report_text, parse_mode="Markdown")
