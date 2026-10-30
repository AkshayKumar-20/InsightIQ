import calendar
from datetime import date
from .database import connect

POLICY = "Net revenue = quantity × unit price − discount; only valid Completed transactions with positive quantity are included."
WHERE = "status = 'Completed' AND quantity > 0 AND lower(trim(region)) NOT IN ('nan', 'none', 'null', '') AND lower(trim(product)) NOT IN ('nan', 'none', 'null', '')"

def _rows(conn, sql, params=()):
    return [dict(r) for r in conn.execute(sql, params).fetchall()]

def summary(db_path=None):
    with connect(db_path) as c:
        r = c.execute(f"SELECT COALESCE(SUM(net_revenue),0) revenue, COUNT(*) transactions, COALESCE(SUM(quantity),0) quantity FROM transactions WHERE {WHERE}").fetchone()
        top = c.execute(f"SELECT product, SUM(net_revenue) revenue FROM transactions WHERE {WHERE} GROUP BY product ORDER BY revenue DESC, product LIMIT 1").fetchone()
        return {"revenue": round(r["revenue"],2), "transactions": r["transactions"], "quantity": r["quantity"],
                "top_product": dict(top) if top else None, "data_policy": POLICY}

def products(db_path=None):
    with connect(db_path) as c:
        return _rows(c, f"""SELECT product, ROUND(SUM(net_revenue),2) revenue, SUM(quantity) quantity, COUNT(*) transactions
          FROM transactions WHERE {WHERE} GROUP BY product ORDER BY revenue DESC, product""")

def regions(db_path=None):
    with connect(db_path) as c:
        return _rows(c, f"""SELECT region, ROUND(SUM(net_revenue),2) revenue, COUNT(*) transactions
          FROM transactions WHERE {WHERE} GROUP BY region ORDER BY revenue DESC, region""")

def trends(db_path=None):
    with connect(db_path) as c:
        return _rows(c, f"""SELECT substr(order_date,1,7) month, ROUND(SUM(net_revenue),2) revenue
          FROM transactions WHERE {WHERE} GROUP BY month ORDER BY month""")

def comparison(start_month: str, end_month: str, db_path=None):
    def valid(m): return len(m) == 7 and m[4] == "-" and m[:4].isdigit() and 1 <= int(m[5:]) <= 12
    if not valid(start_month) or not valid(end_month): raise ValueError("Months must use YYYY-MM format")
    with connect(db_path) as c:
        vals = {}
        for month in (start_month, end_month):
            vals[month] = c.execute(f"SELECT COALESCE(SUM(net_revenue),0) FROM transactions WHERE {WHERE} AND substr(order_date,1,7)=?", (month,)).fetchone()[0]
    absolute = round(vals[end_month] - vals[start_month], 2)
    pct = None if vals[start_month] == 0 else round(absolute / vals[start_month] * 100, 2)
    return {"start_month": start_month, "end_month": end_month, "start_revenue": round(vals[start_month],2),
            "end_revenue": round(vals[end_month],2), "absolute_change": absolute, "percentage_change": pct}
