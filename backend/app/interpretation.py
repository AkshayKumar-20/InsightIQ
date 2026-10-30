import re
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from .config import OPENROUTER_API_KEY, OPENROUTER_MODEL
from .schemas import Interpretation

SUPPORTED = ["total_revenue", "top_product", "monthly_trend", "top_region", "revenue_comparison"]

def fallback(question: str) -> Interpretation:
    q = question.lower().strip()
    if not q: raise ValueError("Question cannot be empty")
    if any(x in q for x in ("total revenue", "revenue total", "how much revenue")):
        return Interpretation(intent="total_revenue")
    if "highest revenue" in q and ("product" in q or "item" in q): return Interpretation(intent="top_product")
    if ("monthly" in q or "month" in q) and ("trend" in q or "revenue" in q): return Interpretation(intent="monthly_trend")
    if ("region" in q or "regional" in q) and ("highest" in q or "top" in q or "sales" in q): return Interpretation(intent="top_region")
    months = re.findall(r"\b(20\d{2}-\d{2})\b", q)
    if ("between" in q or "change" in q or "compare" in q) and len(months) >= 2:
        return Interpretation(intent="revenue_comparison", parameters={"start_month": months[0], "end_month": months[1]})
    raise ValueError("I can answer total revenue, top product, monthly trend, top region, or revenue comparison questions.")

def interpret(question: str) -> tuple[Interpretation, str]:
    if OPENROUTER_API_KEY and OPENROUTER_MODEL:
        try:
            prompt = (
                "Classify the user's business question into exactly one allowed intent. "
                "Return JSON only with keys intent and parameters. Never return SQL. "
                "Allowed intents: total_revenue, top_product, monthly_trend, top_region, "
                "revenue_comparison. For revenue_comparison, parameters must contain "
                "start_month and end_month in YYYY-MM format. "
                f"User question: {question}"
            )
            request = Request(
                "https://openrouter.ai/api/v1/chat/completions",
                data=json.dumps({
                    "model": OPENROUTER_MODEL,
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": "You are a strict intent classifier."},
                        {"role": "user", "content": prompt},
                    ],
                }).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
            content = payload["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            interpretation = Interpretation.model_validate(parsed)
            return interpretation, "openrouter"
        except (HTTPError, URLError, TimeoutError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            # Provider failures must not stop deterministic local analytics.
            pass
    return fallback(question), "fallback"
