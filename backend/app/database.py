import sqlite3
from pathlib import Path
from .config import DB_PATH

class ManagedConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()

SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
 transaction_id TEXT PRIMARY KEY, order_date TEXT NOT NULL, product TEXT NOT NULL,
 category TEXT NOT NULL, region TEXT NOT NULL, sales_channel TEXT NOT NULL,
 quantity INTEGER NOT NULL, unit_price REAL NOT NULL, discount_amount REAL NOT NULL,
 status TEXT NOT NULL, net_revenue REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS rejected_records (
 id INTEGER PRIMARY KEY AUTOINCREMENT, source_row INTEGER, transaction_id TEXT,
 reason TEXT NOT NULL, raw_json TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS ingestion_runs (
 id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT, rows_read INTEGER NOT NULL,
 imported INTEGER NOT NULL, rejected INTEGER NOT NULL, returned_count INTEGER NOT NULL,
 zero_quantity INTEGER NOT NULL, missing_price INTEGER NOT NULL,
 reporting_start TEXT, reporting_end TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(order_date);
CREATE INDEX IF NOT EXISTS idx_transactions_product ON transactions(product);
CREATE INDEX IF NOT EXISTS idx_transactions_region ON transactions(region);
CREATE TABLE IF NOT EXISTS generic_datasets (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 source TEXT NOT NULL,
 table_name TEXT NOT NULL UNIQUE,
 columns_json TEXT NOT NULL,
 row_count INTEGER NOT NULL,
 created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS conversations (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 title TEXT NOT NULL,
 dataset_ref TEXT,
 context_json TEXT,
 created_at TEXT DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS messages (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
 role TEXT NOT NULL CHECK(role IN ('user','assistant')),
 content TEXT NOT NULL,
 result_json TEXT,
 created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS app_state (
 key TEXT PRIMARY KEY,
 value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS profiles (
 id INTEGER PRIMARY KEY CHECK(id = 1),
 name TEXT NOT NULL DEFAULT 'User',
 email TEXT NOT NULL DEFAULT '',
 role TEXT NOT NULL DEFAULT 'Analyst',
 updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 email TEXT NOT NULL UNIQUE,
 name TEXT NOT NULL,
 role TEXT NOT NULL DEFAULT 'Analyst',
 password_hash TEXT NOT NULL,
 created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS auth_tokens (
 token TEXT PRIMARY KEY,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 created_at TEXT DEFAULT CURRENT_TIMESTAMP,
 expires_at TEXT
);
"""

def connect(path: Path | str | None = None) -> sqlite3.Connection:
    db_path = Path(path or DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False, factory=ManagedConnection)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def initialize(path: Path | str | None = None) -> None:
    with connect(path) as conn:
        conn.executescript(SCHEMA)
        user_columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
        if "role" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'Analyst'")
        conversation_columns = {row["name"] for row in conn.execute("PRAGMA table_info(conversations)")}
        if "dataset_ref" not in conversation_columns:
            conn.execute("ALTER TABLE conversations ADD COLUMN dataset_ref TEXT")
        if "context_json" not in conversation_columns:
            conn.execute("ALTER TABLE conversations ADD COLUMN context_json TEXT")
        token_columns = {row["name"] for row in conn.execute("PRAGMA table_info(auth_tokens)")}
        if "expires_at" not in token_columns:
            conn.execute("ALTER TABLE auth_tokens ADD COLUMN expires_at TEXT")
            conn.execute("UPDATE auth_tokens SET expires_at='' WHERE expires_at IS NULL")
