def test_quality_policy(db_path):
    from app.ingestion import latest_summary
    s = latest_summary(db_path)
    assert s["imported"] == 5
    assert s["rejected"] == 2
    assert s["zero_quantity"] == 1
    assert s["missing_price"] == 1


def test_invalid_dates_duplicates_and_negative_values_are_rejected(tmp_path):
    from app.database import connect
    from app.ingestion import ingest_csv

    csv = tmp_path / "invalid.csv"
    csv.write_text(
        "Transaction_Id,Order_date,Product,Category,Region,Sales_channel,Quantity,Unit_price,Discount_amount,Status\n"
        "TX1,01-01-2026,Alpha,A,North,Online,1,10,0,Completed\n"
        "TX1,02-01-2026,Alpha,A,North,Online,1,10,0,Completed\n"
        "TX2,not-a-date,Beta,B,South,Store,1,10,0,Completed\n"
        "TX3,03-01-2026,Gamma,C,West,Online,-1,10,0,Completed\n"
    )
    db = tmp_path / "invalid.sqlite3"
    stats = ingest_csv(csv, db)
    assert stats["imported"] == 1
    assert stats["rejected"] == 3
    with connect(db) as connection:
        reasons = [row["reason"] for row in connection.execute("SELECT reason FROM rejected_records")]
    assert any("duplicate transaction identifier" in reason for reason in reasons)
    assert any("invalid date" in reason for reason in reasons)
    assert any("negative quantity" in reason for reason in reasons)
