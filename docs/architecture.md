# InsightIQ architecture

InsightIQ is a Vite React client over a FastAPI service backed by SQLite. The backend imports CSV data into validated `transactions`, records rejected rows and ingestion runs, and exposes read-only analytics operations. The frontend renders those API results conversationally with Recharts and keeps conversation messages in SQLite.

The interpretation path is intentionally allowlisted: natural language is mapped to one of five approved intents, then trusted parameterized analytics functions execute. No model-generated SQL is executed. When no provider key is configured, deterministic fallback interpretation remains the active mode.
