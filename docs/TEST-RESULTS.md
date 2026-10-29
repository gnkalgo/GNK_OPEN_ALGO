# Validation results

## Independent redesign verification - 29 October 2026

This section supersedes historical results below for the current changes.

- Backend: **38 passed, 3 skipped**. Skips require disposable PostgreSQL/Redis services: concurrent idempotency, concurrent daily-risk budget enforcement and real Redis. Local tests use SQLite/fake Redis; no production concurrency claim.
- Frontend: **28 unit/component tests passed**, including weighted-average ledger, policy persistence, failed load and uncertain-save recovery.
- Desktop/mobile Chromium: **40 passed**, including the new control center, existing user journeys, offline/recovery and responsive overflow checks. A discovered desktop sidebar overflow was fixed and the complete browser suite rerun successfully.
- Alembic: upgrade to `0005`, metadata comparison, downgrade to `0004` and re-upgrade passed on a disposable SQLite database. No target-environment migration was performed.
- Frontend production builds passed in demo and server modes; backend Ruff checks passed.
- Server-mode Chromium transport: **3 passed** with isolated API fixtures, including CSRF-protected risk updates. This does not exercise a deployed PostgreSQL/SMTP/broker stack.
- Dependency inventory: **308 locked components**, no missing license declarations in the installed environment. `--check` passed. `--release` intentionally failed on six pending review areas; license declarations are not compatibility approval. Lock hashes normalize CRLF/LF for cross-platform CI.
- Logo SHA-256 remains `808A77EE26E367A7A41251F010FE987E82D7467EDF7519CC0B51238E2D86BC6C`.
- No OpenAlgo implementation was imported by this change, no live broker orders were sent, and no deployment or push was performed.

Current limitations: commercial tenancy/entitlements/billing, running strategies, live instruments/feed, broker execution/margin/reconciliation, full provenance and legal release approvals remain incomplete. Health checks, local tests and account linking do not establish live readiness.

## Historical validation records

Date: 29 October 2026. Environment: Windows, Node.js 24.22.1, npm 11.19.1.

- Backend suite after live-session control-plane changes: 25 passed, 2 service-integration tests skipped locally (PostgreSQL row-lock concurrency and real Redis).
- Frontend unit/component suite: 23 passed, including live-mode locked-state rendering and same-origin GNK API transport.
- Responsive Chromium visual/route checks: 6 passed across desktop and mobile, including horizontal-overflow checks.
- Production TypeScript/Vite build passed.
- Ruff passed for all changed backend code and tests.
- Alembic upgrades through revision `0004` verified against a disposable SQLite database, including encrypted Dhan access-token columns.
- The legacy broader desktop/mobile Chromium E2E regression remains 38 passed; this change ran the focused six-test visual suite rather than rerunning that full suite.
- Final desktop/mobile Chromium E2E regression after server adapter integration: 38 passed (1.3 minutes).
- Server-mode Chromium transport tests: 2 passed using isolated API fixtures (not a deployed PostgreSQL/SMTP stack).
- Both base and production Docker Compose configurations parse successfully.
- One backend test dependency emits a Starlette/httpx deprecation warning; no test failed from it.
- Logo integrity: original and copied artwork SHA-256 hashes match.
- No real broker APIs or trading endpoints were contacted.

The initial browser run identified stale auth-form state across routes and duplicate background/modal feedback announcements. Those were corrected before the final run. The suite uses isolated in-memory sessions, fictional credentials and paper orders.

Known limits: desktop/mobile Chromium emulation only, no Firefox/WebKit or physical-device claim. PostgreSQL/Redis container execution, SMTP provider delivery and deployment remain unverified because the Docker Linux engine is unavailable here. The live-session control plane is fail-closed; no broker execution service, live feed, risk engine, or live order execution has been implemented or tested. No production rollout is claimed. GitHub workflows are prepared, not pushed or run. See [deployment details](DEPLOYMENT.md).
