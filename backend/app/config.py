from pathlib import Path
import os
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / "backend" / ".env")
DB_PATH = Path(os.getenv("INSIGHTIQ_DB_PATH", ROOT / "data" / "insightiq.sqlite3"))
DATASET_PATH = Path(os.getenv("INSIGHTIQ_DATASET", ROOT / "data" / "sales_transactions.csv"))
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "")
FRONTEND_ORIGINS = [x.strip() for x in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173").split(",") if x.strip()]
