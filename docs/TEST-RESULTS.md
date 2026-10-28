# Validation results

Date: 29 October 2026. Environment: Windows, Node.js 24.22.1, npm 11.19.1.

- Backend suite after live-session control-plane changes: 25 passed, 2 service-integration tests skipped locally (PostgreSQL row-lock concurrency and real Redis).
- Frontend unit/component suite: 23 passed, including live-mode locked-state rendering and same-origin GNK API transport.
- Responsive Chromium visual/route checks: 6 passed across desktop and mobile, including horizontal-overflow checks.
- Production TypeScript/Vite build passed.
- Ruff passed for all changed backend code and tests.
- Alembic upgrades through revision `0003` verified against a disposable SQLite database, including the live-session, event, and emergency-stop schema.
- The legacy broader desktop/mobile Chromium E2E regression remains 38 passed; this change ran the focused six-test visual suite rather than rerunning that full suite.
- Final desktop/mobile Chromium E2E regression after server adapter integration: 38 passed (1.3 minutes).
- Server-mode Chromium transport tests: 2 passed using isolated API fixtures (not a deployed PostgreSQL/SMTP stack).
- Both base and production Docker Compose configurations parse successfully.
- One backend test dependency emits a Starlette/httpx deprecation warning; no test failed from it.
- Logo integrity: original and copied artwork SHA-256 hashes match.
- No real broker APIs or trading endpoints were contacted.

The initial browser run identified stale auth-form state across routes and duplicate background/modal feedback announcements. Those were corrected before the final run. The suite uses isolated in-memory sessions, fictional credentials and paper orders.

Known limits: desktop/mobile Chromium emulation only, no Firefox/WebKit or physical-device claim. PostgreSQL/Redis container execution, SMTP provider delivery and deployment remain unverified because the Docker Linux engine is unavailable here. The live-session control plane is fail-closed; no OpenAlgo service, multi-user isolation, broker token validation, live feed, risk engine, or live order execution has been implemented or tested. No production rollout is claimed. GitHub workflows are prepared, not pushed or run. See [deployment details](DEPLOYMENT.md).
