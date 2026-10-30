from . import analytics
from .schemas import Interpretation

def execute(i: Interpretation, db_path=None) -> dict:
    intent = i.intent
    if intent == "total_revenue":
        s = analytics.summary(db_path)
        return {"answer": f"Total net revenue is ${s['revenue']:,.2f} across {s['transactions']} eligible completed transactions.",
                "metrics": s, "table": [], "chart": None, "sql_explanation": "SUM(net_revenue) filtered to Completed rows with quantity > 0."}
    if intent == "top_product":
        rows = analytics.products(db_path); top = rows[0] if rows else None
        return {"answer": f"{top['product']} generated the highest revenue at ${top['revenue']:,.2f}." if top else "No eligible sales are available.",
                "metrics": top or {}, "table": rows, "chart": {"type":"bar","x_key":"product","y_key":"revenue","data":rows},
                "sql_explanation": "GROUP BY product, ordered by SUM(net_revenue) DESC with product tie-break."}
    if intent == "monthly_trend":
        rows = analytics.trends(db_path)
        return {"answer": "Here is the monthly net revenue trend from the imported eligible sales.", "metrics": {}, "table": rows,
                "chart": {"type":"line","x_key":"month","y_key":"revenue","data":rows}, "sql_explanation": "GROUP BY calendar month and order chronologically."}
    if intent == "top_region":
        rows = analytics.regions(db_path); top = rows[0] if rows else None
        return {"answer": f"{top['region']} generated the highest sales at ${top['revenue']:,.2f}." if top else "No eligible sales are available.",
                "metrics": top or {}, "table": rows, "chart": {"type":"bar","x_key":"region","y_key":"revenue","data":rows},
                "sql_explanation": "GROUP BY region, ordered by SUM(net_revenue) DESC with region tie-break."}
    p = analytics.comparison(i.parameters["start_month"], i.parameters["end_month"], db_path)
    pct = "not applicable because the baseline is zero" if p["percentage_change"] is None else f"{p['percentage_change']:.2f}%"
    return {"answer": f"Revenue changed by ${p['absolute_change']:,.2f} from {p['start_month']} to {p['end_month']} ({pct}).",
            "metrics": p, "table": [p], "chart": None, "sql_explanation": "Two parameterized monthly SUM queries; percentage uses the first month as baseline."}
