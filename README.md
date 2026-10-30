# InsightIQ — AI-Powered Business Intelligence Assistant

InsightIQ is a full-stack conversational CSV intelligence application. Users upload a CSV, inspect its detected structure, and ask natural-language questions answered from the active dataset. The interface is built with React and Vite; the API uses FastAPI, Pandas, and SQLite.

The implemented query engine is deterministic and local. It does not execute arbitrary SQL or require an external LLM. Sales-shaped files use trusted sales analytics; other valid CSVs use the generic profiling and query engine.

## Problem and objectives

Business users often have useful CSV data but need to understand it without writing SQL or building a dashboard first. InsightIQ addresses this by:

- profiling uploaded files automatically;
- identifying usable numeric, categorical, text, and date columns;
- answering common analytical questions in natural language;
- keeping answers tied to the selected conversation dataset; and
- presenting grounded answers with tables, metrics, and relevant charts.

## Key features

- CSV upload with validation, delimiter/encoding detection, and safe error handling.
- Automatic schema profiling, row/column counts, missing-value counts, duplicate detection, and summaries.
- Generic questions for counts, sums, averages, minimums, maximums, filters, grouping, ranking, samples, unique values, missing values, dates, and comparisons.
- Trusted sales analytics for net revenue, products, regions, trends, and month comparisons.
- Conversation history with dataset association, rename, delete, chronological messages, and follow-up context.
- React chat interface with responsive sidebar, CSV upload, active dataset details, charts, tables, retry, copy, settings, and authentication.
- Parameterized SQLite values and validated dynamic identifiers to prevent unsafe query execution.

## Technology stack

| Area | Actual technology |
|---|---|
| Frontend | React, Vite, Recharts, Lucide React, CSS |
| Backend | Python, FastAPI, Pydantic |
| Data processing | Pandas |
| Database | SQLite |
| Tests | pytest, FastAPI TestClient |
| Deployment configuration | Render Blueprint in `render.yaml` |

## Requirements

- Python 3.11 or newer recommended.
- Node.js and npm.
- Windows users should use `npm.cmd` if PowerShell blocks `npm.ps1`.
- A writable project data directory for SQLite and uploaded files.

## Project structure

```text
insightiq/
├── backend/
│   ├── app/
│   │   ├── analytics.py       # Trusted sales queries
│   │   ├── database.py        # SQLite schema and connections
│   │   ├── generic.py         # Generic CSV profiling and query engine
│   │   ├── ingestion.py       # Sales CSV ingestion
│   │   ├── interpretation.py  # Allowlisted sales intent interpretation
│   │   ├── main.py            # FastAPI routes
│   │   ├── schemas.py         # Pydantic API models
│   │   └── services.py        # Sales response generation
│   ├── requirements.txt
│   └── tests/
├── data/
│   ├── insightiq.sqlite3
│   └── uploads/
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/Chart.jsx
│   │   └── services/api.js
│   └── package.json
├── scripts/import_data.py
├── ARCHITECTURE.md
├── TESTING.md
├── AI_USAGE_AND_DEVELOPMENT.md
└── render.yaml
```

## Installation

From the repository root:

```powershell
python -m pip install -r backend\requirements.txt
cd frontend
npm.cmd install
cd ..
```

## Environment configuration

The repository includes safe examples:

- root `.env.example`
- `backend\.env.example`

The backend reads these variables:

```text
INSIGHTIQ_DB_PATH=data/insightiq.sqlite3
INSIGHTIQ_DATASET=data/sales_transactions.csv
FRONTEND_ORIGINS=http://localhost:5173
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
```

The current runtime code uses `INSIGHTIQ_DB_PATH`, `INSIGHTIQ_DATASET`, and `FRONTEND_ORIGINS`. The OpenAI variables are placeholders and are not used to execute runtime queries.

The frontend reads:

```powershell
$env:VITE_API_URL = "http://localhost:8000"
```

Do not commit real secrets, production `.env` files, private CSVs, SQLite databases, or uploaded customer data.

## Start the backend

From the repository root:

```powershell
$env:PYTHONPATH = "backend"
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Alternatively:

```powershell
cd backend
python -m uvicorn app.main:app --reload
```

The API is available at `http://localhost:8000`.

To import the bundled sales data:

```powershell
python scripts\import_data.py
```

To import another sales-compatible CSV:

```powershell
python scripts\import_data.py "C:\path\to\sales.csv"
```

## Start the frontend

In a second terminal:

```powershell
cd frontend
npm.cmd run dev
```

Open the Vite URL, normally `http://localhost:5173`.

For a different backend:

```powershell
$env:VITE_API_URL = "http://localhost:8000"
npm.cmd run dev
```

## Using InsightIQ

1. Open the frontend.
2. Sign in or create an account.
3. Click the attachment button and select a `.csv` file.
4. Confirm the active filename, row count, column count, missing values, and duplicates.
5. Ask a question such as `How many records?`, `What is the average Salary?`, or `Show the first five rows`.
6. Use the sidebar to return to a conversation. Each conversation retains its dataset reference and context.

## API endpoints

### Health and metadata

- `GET /health` — basic health response.
- `GET /api/health` — API health response.
- `GET /api/metadata` — active dataset, profile, supported questions, and reporting metadata.

### Upload and analytics

- `POST /api/upload` — upload a CSV; accepts optional `conversation_id`.
- `GET /api/analytics/summary` — sales KPI summary.
- `GET /api/analytics/trends` — monthly sales trend.
- `GET /api/analytics/monthly` — alias for trends.
- `GET /api/analytics/products` — product revenue results.
- `GET /api/analytics/regions` — regional revenue results.
- `GET /api/analytics/comparison` — compare two `YYYY-MM` sales periods.
- `GET /api/data-quality` — sales import quality and rejection information.

### Questions and conversations

- `POST /api/ask` — question endpoint used by the backend compatibility path.
- `POST /api/chat` — frontend chat endpoint; accepts `question` and optional `conversation_id`.
- `GET /api/conversations` — list conversations.
- `POST /api/conversations` — create a conversation.
- `GET /api/conversations/{id}` — retrieve conversation messages in insertion order.
- `PATCH /api/conversations/{id}` — rename a conversation.
- `DELETE /api/conversations/{id}` — delete a conversation.
- `POST /api/conversations/{id}/messages` — persist a user or assistant message.

### Authentication and profile

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `GET /api/profile`
- `PUT /api/profile`

## Data storage

By default:

- SQLite database: `data\insightiq.sqlite3`
- Uploaded CSVs: `data\uploads\`

Generic datasets are stored in generated SQLite tables and described in `generic_datasets`. Production deployments need persistent disk storage for SQLite and uploads. The provided Render configuration mounts `/var/data` for the backend database.

## Screenshots

No screenshot files are currently committed. Add assessment screenshots under `docs/screenshots/` and reference them here, for example:

```text
docs/screenshots/chat-home.png
docs/screenshots/uploaded-dataset.png
docs/screenshots/conversation-history.png
```

## Testing

Backend:

```powershell
$env:PYTHONPATH = "backend"
python -m pytest -q
```

Focused generic CSV tests:

```powershell
$env:PYTHONPATH = "backend"
python -m pytest backend\tests\test_generic_datasets.py -q
```

Frontend production build:

```powershell
cd frontend
npm.cmd run build
```

The repository does not currently include a frontend component-test runner. See `TESTING.md` for the test scope and manual smoke workflow.

## Troubleshooting

### Frontend cannot reach the API

Confirm the backend is running on port 8000 and set:

```powershell
$env:VITE_API_URL = "http://localhost:8000"
```

Restart Vite after changing environment variables.

### Port 8000 is already in use

Find the process using the port, stop that specific process if appropriate, or run the backend on another port and set the matching `VITE_API_URL`:

```powershell
python -m uvicorn app.main:app --app-dir backend --port 8001
$env:VITE_API_URL = "http://localhost:8001"
```

### CSV upload fails

Confirm the file has a `.csv` extension, a named header row, valid text encoding, and consistent rows. Empty, malformed, binary, and unnamed-column files are rejected intentionally.

### Questions return an unsupported-query error

Use a question tied to detected schema columns, such as `average Salary`, `count records`, `show HR`, `highest Price`, or `show records from 2025`. The assistant does not fabricate answers for unsupported operations.

## Future enhancements

- Add a dedicated frontend component-test and browser end-to-end test setup.
- Improve ambiguous column/entity clarification.
- Add pagination and larger-dataset performance controls.
- Add production-grade password hashing, authorization, rate limiting, and audit logging.
- Add persistent object storage and backups for uploaded files and SQLite data.
- Add structured monitoring and deployment health checks.

Do not push or deploy automatically from this repository. Review changes and configure secrets in the target hosting platform first.
