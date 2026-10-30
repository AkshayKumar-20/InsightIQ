import re
from .config import LLM_API_KEY
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
    # Provider integration is intentionally opt-in; fallback remains deterministic and safe.
    if LLM_API_KEY:
        # A production deployment may add a provider client here. Never execute model SQL.
        return fallback(question), "fallback"
    return fallback(question), "fallback"
