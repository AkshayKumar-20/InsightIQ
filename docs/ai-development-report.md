# AI development report

The current product uses deterministic intent classification for total revenue, top product, monthly trend, top region, and month comparison. Each response includes the calculation explanation and the interpreter mode so users can distinguish grounded fallback behavior from a future provider adapter.

Security boundaries are explicit: Pydantic validates questions, the interpreter rejects unsupported or SQL-shaped prompts, analytics uses fixed SQL templates, and all values are bound parameters. An external LLM adapter is not enabled by default and is not required for local operation.
