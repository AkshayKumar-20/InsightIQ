import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.config import DATASET_PATH
from app.ingestion import ingest_csv

if __name__ == "__main__":
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else DATASET_PATH
    print(ingest_csv(source))








