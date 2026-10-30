# InsightIQ

InsightIQ is an AI-powered CSV intelligence assistant. It provides a ChatGPT-style conversational workspace for uploading CSV files, profiling their structure, and asking grounded questions answered from the active dataset.

The application supports both the built-in sales schema and arbitrary valid CSV schemas. Generic CSV questions are interpreted and executed deterministically against a generated SQLite table; the application never executes user-provided SQL or fabricated model-generated SQL.

## Features

- Upload and validate CSV files with delimiter and encoding detection.
- Detect columns and infer numeric, categorical, text, and date types.
- Report row counts, column counts, missing values, duplicate rows, samples, and summaries.
- Keep the active filename and dataset tied to each conversation.
- Answer generic CSV questions about:
  - counts and row samples
  - sums, averages, minimums, and maximums
  - filters and date/year queries
  - grouping, ranking, top-N results, and comparisons
  - unique values, missing values, and duplicates
- Preserve conversational context for follow-up questions such as “Only HR”, “What about North?”, and “Compare both”.
- Provide trusted sales analytics for revenue, products, regions, trends, and month comparisons.
- Display grounded text answers followed by relevant tables and charts.
- Persist conversation history, rename conversations, delete conversations, and restore message order.
- Responsive React interface with CSV upload, active dataset details, retry, copy, loading states, and mobile layout.

## Technology stack

- **Frontend:** React, Vite, Recharts, Lucide React, CSS
- **Backend:** Python, FastAPI, Pydantic, Pandas
- **Database:** SQLite
- **Testing:** pytest, FastAPI `TestClient`
- **Deployment:** Render configuration in `render.yaml`

## Architecture

```text
React/Vite frontend
        |
        | HTTP JSON and multipart CSV upload
        v
FastAPI application
  - /api/upload
  - /api/chat
  - /api/conversations
  - /api/analytics/*
        |
        +--> Trusted sales analytics in app/analytics.py
        +--> Generic CSV profiling/query engine in app/generic.py
        +--> Conversation and dataset persistence in SQLite
```

Sales-shaped files are normalized by `backend/app/ingestion.py` and queried by `backend/app/analytics.py`. Other CSV files are profiled and stored in generated tables by `backend/app/generic.py`. Dynamic SQL identifiers are validated and quoted; all user values are passed as SQLite parameters.

Conversation records store `dataset_ref` and `context_json`, preventing a conversation from accidentally querying the most recently uploaded dataset.

## Installation

From the repository root on Windows:

```powershell
python -m pip install -r backend\requirements.txt
cd frontend
npm.cmd install
cd ..
```

Python 3.11+ and Node.js are recommended.

## Backend startup

```powershell
cd backend
python -m uvicorn app.main:app --reload
```

The backend listens on `http://localhost:8000`.

To load the bundled sales CSV:

```powershell
python scripts\import_data.py
```

To import another sales-compatible file:

```powershell
python scripts\import_data.py "C:\path\to\sales.csv"
```

The default SQLite database is `data\insightiq.sqlite3`.

## Frontend startup

In a second terminal:

```powershell
cd frontend
npm.cmd run dev
```

Open the Vite URL shown in the terminal, normally `http://localhost:5173`.

The frontend uses `http://localhost:8000` by default. Set `VITE_API_URL` before starting Vite when the backend is hosted elsewhere:

```powershell
$env:VITE_API_URL = "http://localhost:8000"
npm.cmd run dev
```

## Environment configuration

Copy the example configuration when environment-specific values are needed:

```powershell
Copy-Item backend\.env.example backend\.env
```

Important settings include:

- `DB_PATH`: SQLite database location
- `DATASET_PATH`: default sales CSV location
- `FRONTEND_ORIGINS`: allowed frontend origins
- `VITE_API_URL`: frontend API base URL

An external LLM key is optional. The verified default path is deterministic and database-grounded; no external model is required for the supported CSV operations.

## API

Health:

- `GET /health`
- `GET /api/health`

Data and analytics:

- `GET /api/metadata`
- `POST /api/upload`
- `GET /api/analytics/summary`
- `GET /api/analytics/monthly`
- `GET /api/analytics/products`
- `GET /api/analytics/regions`
- `GET /api/analytics/comparison`
- `GET /api/data-quality`

Chat and conversations:

- `POST /api/chat`
- `GET /api/conversations`
- `POST /api/conversations`
- `GET /api/conversations/{id}`
- `PATCH /api/conversations/{id}`
- `DELETE /api/conversations/{id}`
- `POST /api/conversations/{id}/messages`

## Testing and verification

Run the backend tests:

```powershell
$env:PYTHONPATH = "backend"
python -m pytest -q
```

Build the frontend:

```powershell
cd frontend
npm.cmd run build
```

The audit suite covers CSV ingestion, multiple schemas, profiling, calculations, filters, grouping, ranking, dates, missing values, dataset isolation, message ordering, and follow-up context. The production build is also verified with Vite.

## Screenshots

The current repository does not contain committed screenshot assets. The running application provides the approved InsightIQ workspace with:

- the collapsible InsightIQ sidebar
- right-aligned user messages and left-aligned assistant messages
- active CSV and dataset profile information
- grounded answer tables and charts
- mobile-responsive layout

To capture screenshots locally, start the backend and frontend using the commands above and save images under `docs/screenshots/`.

## Known limitations

- The default interpreter is deterministic and does not require an external LLM.
- The frontend build reports a non-blocking bundle-size warning from the current dependency bundle.
- Date filtering is supported by natural-language year/month queries; there is no separate date-picker workflow.

## Render deployment

`render.yaml` defines the deployable services. Configure the generated service URLs in `FRONTEND_ORIGINS` and `VITE_API_URL`, and use persistent storage for SQLite data and uploaded CSV files.
