import base64
import json
import re
import anthropic
from config import ANTHROPIC_API_KEY

_client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

RECEIPT_PROMPT = """You are a receipt parser. Extract all information from this receipt image.
Return ONLY valid JSON (no markdown, no backticks) with this exact structure:
{
  "store": "store name",
  "date": "YYYY-MM-DD",
  "total": 0.00,
  "items": [
    {"name": "item name", "quantity": 1, "price": 0.00, "category": "other"}
  ]
}
If a field is unknown use null. Date format must be YYYY-MM-DD.
For each item assign a category from this list: dairy, meat, vegetables, fruit, snacks, drinks, hygiene, cleaning, pharmacy, bakery, frozen, pasta, condiments, other."""


def _strip_json(text: str) -> str:
    text = text.strip()
    # strip markdown code fences Claude sometimes adds
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


async def parse_receipt(image_bytes: bytes, media_type: str = "image/jpeg") -> dict:
    b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    msg = await _client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": b64},
                    },
                    {"type": "text", "text": RECEIPT_PROMPT},
                ],
            }
        ],
    )
    raw = msg.content[0].text
    return json.loads(_strip_json(raw))


MONTHLY_REPORT_PROMPT = """You are a personal finance advisor. Analyse the following transactions for {month}.
Return a concise Telegram-friendly report (use *bold* and emojis) covering:
- Total income vs expenses
- Top 5 spending categories
- Unusual or large transactions
- Budget adherence (budgets provided below)
- One actionable saving tip

Transactions (JSON):
{transactions}

Budgets (JSON):
{budgets}"""


async def monthly_report(month: str, transactions: list, budgets: list) -> str:
    prompt = MONTHLY_REPORT_PROMPT.format(
        month=month,
        transactions=json.dumps(transactions, ensure_ascii=False),
        budgets=json.dumps(budgets, ensure_ascii=False),
    )
    msg = await _client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text
