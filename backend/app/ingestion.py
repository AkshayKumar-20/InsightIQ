import json
import sqlite3
from pathlib import Path
import pandas as pd
from .database import connect, initialize

REQUIRED = ["Transaction_Id", "Order_date", "Product", "Category", "Region", "Sales_channel",
            "Quantity", "Unit_price", "Discount_amount", "Status"]
VALID_STATUS = {"Completed", "Returned"}

def ingest_csv(source: Path | str, db_path: Path | str | None = None) -> dict:
    source = Path(source)
    if not source.exists():
        raise FileNotFoundError(f"Dataset not found: {source}")
    df = pd.read_csv(source)
    df.columns = [str(c).strip() for c in df.columns]
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")
    initialize(db_path)
    stats = {"rows_read": len(df), "imported": 0, "rejected": 0, "returned": 0,
             "zero_quantity": 0, "missing_price": 0}
    with connect(db_path) as conn:
        conn.execute("DELETE FROM transactions")
        conn.execute("DELETE FROM rejected_records")
        for i, raw in df.iterrows():
            row = {k: raw[k] for k in REQUIRED}
            txid = str(row["Transaction_Id"]).strip() if pd.notna(row["Transaction_Id"]) else ""
            reasons = []
            if not txid: reasons.append("missing transaction identifier")
            if txid and conn.execute("SELECT 1 FROM transactions WHERE transaction_id=?", (txid,)).fetchone():
                reasons.append("duplicate transaction identifier")
            date = pd.to_datetime(row["Order_date"], dayfirst=True, errors="coerce")
            if pd.isna(date): reasons.append("invalid date")
            for field in ("Quantity", "Unit_price", "Discount_amount"):
                if pd.isna(row[field]):
                    if field == "Unit_price": stats["missing_price"] += 1
                    reasons.append(f"missing {field}")
            quantity_missing = pd.isna(row["Quantity"])
            try: quantity = int(row["Quantity"])
            except (TypeError, ValueError): quantity = 0; reasons.append("invalid quantity")
            try: price = float(row["Unit_price"])
            except (TypeError, ValueError): price = 0; reasons.append("invalid unit price")
            try: discount = float(row["Discount_amount"])
            except (TypeError, ValueError): discount = 0; reasons.append("invalid discount")
            if quantity < 0: reasons.append("negative quantity")
            if price < 0: reasons.append("negative unit price")
            if discount < 0: reasons.append("negative discount")
            status = str(row["Status"]).strip()
            for field in ("Product", "Category", "Region", "Sales_channel"):
                if pd.isna(row[field]) or not str(row[field]).strip() or str(row[field]).strip().lower() in {"nan", "none", "null"}:
                    reasons.append(f"missing {field}")
            if status not in VALID_STATUS: reasons.append("invalid status")
            if quantity == 0 and not quantity_missing: stats["zero_quantity"] += 1
            if status == "Returned": stats["returned"] += 1
            gross = quantity * price
            if discount > gross: reasons.append("discount exceeds gross value")
            if reasons:
                stats["rejected"] += 1
                conn.execute("INSERT INTO rejected_records(source_row,transaction_id,reason,raw_json) VALUES(?,?,?,?)",
                             (i + 2, txid or None, "; ".join(reasons), json.dumps({k: str(v) for k,v in row.items()})))
                continue
            net = round(gross - discount, 2)
            conn.execute("""INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                         (txid, date.strftime("%Y-%m-%d"), str(row["Product"]).strip(),
                          str(row["Category"]).strip(), str(row["Region"]).strip(),
                          str(row["Sales_channel"]).strip(), quantity, price, discount, status, net))
            stats["imported"] += 1
        period = conn.execute("SELECT MIN(order_date), MAX(order_date) FROM transactions").fetchone()
        conn.execute("""INSERT INTO ingestion_runs(source,rows_read,imported,rejected,returned_count,zero_quantity,missing_price,reporting_start,reporting_end)
                        VALUES(?,?,?,?,?,?,?,?,?)""",
                     (str(source), stats["rows_read"], stats["imported"], stats["rejected"], stats["returned"],
                      stats["zero_quantity"], stats["missing_price"], period[0], period[1]))
    return stats

def latest_summary(db_path=None) -> dict:
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM ingestion_runs ORDER BY id DESC LIMIT 1").fetchone()
        if not row: return {"dataset_available": False}
        return {"dataset_available": True, **dict(row)}
