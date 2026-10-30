import pytest
from pathlib import Path
from app.database import initialize
from app.ingestion import ingest_csv

@pytest.fixture
def db_path(tmp_path):
    csv = tmp_path / "sales.csv"
    csv.write_text("""Transaction_Id,Order_date,Product,Category,Region,Sales_channel,Quantity,Unit_price,Discount_amount,Status
TX1,01-01-2026,Alpha,A,North,Online,2,10,1,Completed
TX2,15-01-2026,Beta,B,South,Store,1,30,0,Completed
TX3,01-02-2026,Alpha,A,North,Online,1,20,0,Completed
TX4,02-02-2026,Beta,B,South,Store,2,5,0,Returned
TX5,03-02-2026,Gamma,C,West,Online,0,100,0,Completed
TX6,04-02-2026,Gamma,C,West,Online,,100,0,Completed
TX7,05-02-2026,Gamma,C,West,Online,1,,0,Completed
""")
    db = tmp_path / "test.sqlite3"
    ingest_csv(csv, db)
    return db
