# AI Usage and Development Reflection

## AI tools used

This project was developed with GitHub Copilot CLI assistance in the coding workflow. The assistant was used to inspect files, trace failures, propose focused changes, edit source files, and run tests and builds.

The application itself does not depend on ChatGPT or an external LLM at runtime. “ChatGPT-style” describes the conversational interface. `OPENAI_API_KEY` and `OPENAI_MODEL` exist in the environment examples, but the implemented query path uses deterministic local logic and SQLite.

## How AI was used

- **Planning and architecture:** inspected the existing React, FastAPI, SQLite, Pandas, and Recharts structure before making changes.
- **Frontend development:** traced the existing message, upload, conversation, settings, and authentication flows and made surgical React/CSS updates.
- **Backend development:** extended and verified CSV profiling, dataset selection, conversation context, and deterministic query execution.
- **CSV processing:** examined actual schemas and implemented validation, type inference, missing-value reporting, duplicate detection, and generated dataset tables.
- **Natural-language queries:** added schema-aware matching for counts, aggregates, filters, grouping, ranking, dates, samples, and follow-ups without executing arbitrary generated SQL.
- **Debugging:** reproduced API and browser failures, inspected console/runtime errors, checked process ports, and verified request/response behavior with live HTTP calls.
- **Documentation and testing:** reviewed existing tests, added regression cases, ran pytest, built the frontend, and documented the actual architecture and commands.

## Problems encountered

The development history included several verified issues:

- A region label was converted with `Number(...)` in the frontend and displayed as `NaN`.
- New assistant messages were initially inserted or displayed in the wrong order.
- A newly uploaded CSV could be ignored when a conversation still referenced another dataset.
- Generic follow-up filters such as `Only HR.` failed because punctuation remained attached to the token.
- Explicit questions about departments could match an `Employee` column first because of substring matching.
- “How many records?” was initially routed to the sample-row branch instead of the count branch.
- The frontend could stop before calling `/api/chat` if conversation-message persistence failed.
- A runtime error occurred because `setFailedQuestion` was referenced in `App` without declaring the corresponding state there.
- Generic charts were initially labeled as INR/net revenue even for non-revenue numeric columns.

## Debugging approach

I used browser console errors to identify frontend runtime failures, backend terminal output and HTTP responses to identify API behavior, and direct code inspection to trace the full request path. I reproduced upload and chat calls using FastAPI's test client and live HTTP requests, checking status codes and returned JSON.

Regression tests were added or updated around each important failure. The backend suite was run after fixes, and the Vite production build was run after frontend changes. This combination distinguished source-code defects from stale processes, incorrect ports, and runtime configuration problems.

## What I would improve with one additional day

- Improve ambiguous column resolution with stronger schema semantics and user clarification.
- Expand CSV compatibility testing for encodings, delimiters, very wide files, and large datasets.
- Add more API-level conversation-context sequences and frontend component tests.
- Improve follow-up context expiry so unrelated new questions do not inherit an old filter.
- Add pagination and query limits for larger datasets while preserving safe parameterization.
- Replace password hashing with a modern password-hashing library and add stronger authentication controls.
- Add structured logging, health/readiness checks, and deployment monitoring.
- Add persistent production storage and backup procedures for SQLite and uploaded files.
