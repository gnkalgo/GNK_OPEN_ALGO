# Validation results

Date: 28 October 2026. Environment: Windows, Node.js 24.22.1, npm 11.19.1.

- Initial production TypeScript/Vite build passed.
- Unit/component suite: 21 passed, including server transport, CSRF and unknown-response handling.
- Final desktop/mobile Chromium E2E regression after server adapter integration: 38 passed (1.3 minutes).
- Server-mode Chromium transport tests: 2 passed using isolated API fixtures (not a deployed PostgreSQL/SMTP stack).
- Backend: 13 passed, 2 service-integration tests skipped locally; these target PostgreSQL 17 row-lock concurrency and real Redis cache/queues.
- Alembic: initial migration applied to disposable SQLite file; `alembic check` reports no model drift.
- Both base and production Docker Compose configurations parse successfully.
- Backend Ruff checks and Python compilation pass. Demo-mode and server-mode frontend builds pass.
- One backend test dependency emits a Starlette/httpx deprecation warning; no test failed from it.
- Logo integrity: original and copied artwork SHA-256 hashes match.
- No real broker APIs or trading endpoints were contacted.

The initial browser run identified stale auth-form state across routes and duplicate background/modal feedback announcements. Those were corrected before the final run. The suite uses isolated in-memory sessions, fictional credentials and paper orders.

Known limits: desktop/mobile Chromium emulation only, no Firefox/WebKit or physical-device claim. An independent server authentication and persisted paper backend is now implemented, but PostgreSQL/Redis container execution, SMTP provider delivery and deployment remain unverified because the Docker Linux engine is unavailable here. No broker OAuth, live feed, live trading, real strategy engine or production rollout is claimed. GitHub workflows are prepared, not pushed or run. See [deployment details](DEPLOYMENT.md).
