from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = Path(os.getenv("INSIGHTIQ_DB_PATH", ROOT / "data" / "insightiq.sqlite3"))
DATASET_PATH = Path(os.getenv("INSIGHTIQ_DATASET", ROOT / "data" / "sales_transactions.csv"))
LLM_API_KEY = os.getenv("OPENAI_API_KEY")
LLM_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
FRONTEND_ORIGINS = [x.strip() for x in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173").split(",") if x.strip()]
