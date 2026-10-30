# InsightIQ Testing

## Backend tests

Backend tests use pytest and FastAPI's `TestClient`. No additional test framework is required.

From the repository root on Windows:

```powershell
$env:PYTHONPATH = "backend"
python -m pytest -q
```

The suite covers:

- Health endpoints.
- Sales ingestion and revenue policy.
- Generic CSV parsing and schema profiling.
- Numeric, categorical, text, and date detection.
- Missing-value and duplicate-row detection.
- Counts, sums, averages, minimums, maximums, filters, grouping, ranking, samples, and comparisons.
- Invalid CSV handling and unsupported questions.
- Dataset isolation.
- Conversation ordering and follow-up context.
- Region label regression coverage.

Run a focused file when debugging:

```powershell
$env:PYTHONPATH = "backend"
python -m pytest backend\tests\test_generic_datasets.py -q
```

## Frontend verification

The repository does not currently include a frontend component-test runner. The supported automated frontend check is the production build:

```powershell
cd frontend
npm.cmd run build
```

This verifies Vite compilation, React imports, CSS processing, and production bundle generation. Manual browser checks should cover login, CSV upload, question submission, conversation selection, settings, and responsive layout.

## End-to-end smoke check

Start the backend:

```powershell
cd backend
python -m uvicorn app.main:app --reload
```

Start the frontend in another terminal:

```powershell
cd frontend
npm.cmd run dev
```

Then upload a CSV in the browser and verify:

1. The filename and profile appear.
2. `How many records?` returns a count.
3. A numeric question returns a calculated value.
4. A sample question returns table rows.
5. The answer appears after the user question.

## Current verified status

Run the commands above against the current checkout rather than relying on this document for a stale count. Test output and build warnings should be recorded in the assessment submission or CI logs.
