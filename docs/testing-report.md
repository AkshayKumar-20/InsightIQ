# Testing report

Backend verification: `14 passed` with `python -m pytest -q`. Coverage includes revenue calculations, product and regional rankings, monthly aggregation, comparisons, returned and invalid record handling, missing values, zero quantities, unsupported questions, and SQL-injection-shaped input.

Frontend verification: `npm.cmd run build` succeeds with Vite. The build emits a non-blocking bundle-size warning because Recharts and Lucide are currently shipped in the main bundle.
