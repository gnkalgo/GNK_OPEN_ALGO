# GNK ALGO frontend API boundary

**Backend addition:** the independent FastAPI implementation now exists in `backend/app/main.py`, and `frontend/src/api/server.ts` connects the existing UI to it when `VITE_API_MODE=server`. The sections below originally documented the frontend-only simulator and proposals. The implemented contract is the following table; it supersedes proposed paths where they differ. See [deployment instructions](DEPLOYMENT.md).

| Implemented route under `/api/gnk/v1` | Contract |
| --- | --- |
| `POST /auth/register` | Name/email/password; generic 202, Argon2id password hash, durable verification outbox |
| `POST /auth/verify` | Single-use email token; expired/replayed links rejected |
| `POST /auth/resend` | Generic 202, rate-limited verification resend |
| `POST /auth/login` | Email/password; sets opaque HttpOnly cookie and returns CSRF token plus public user |
| `GET /session` | Public user and CSRF token for authenticated session bootstrap |
| `POST /auth/logout` | CSRF-protected session revocation |
| `POST /auth/forgot`, `/auth/reset` | Generic email response; single-use reset, password hash replacement, session revocation |
| `GET /workspace` | Current user's paper balance, orders, strategies, watchlist and audit activity |
| `POST /brokers/paper/connect` | Connect the server's paper simulator only |
| `POST /paper/orders` | Ticket plus UUID `Idempotency-Key`; locked PostgreSQL balance update and durable deduplication |
| `GET /paper/orders/:key` | Read committed result for that user's original request; 404 leaves unknown client outcomes unresolved |
| `PUT /profile` | Update validated name |
| `PUT /watchlist/:symbol` | Toggle listed fictional symbol |
| `POST /strategies`, `PUT /strategies/:id` | Validate/save current user's configuration as Draft |
| `POST /strategies/:id/transition` | Validate lifecycle transition and paper-connection prerequisite |
| `GET /admin/users`, `PATCH /admin/users/:id` | Server admin permission; view users or suspend/restore and revoke sessions |
| `GET /admin/audit`, `/admin/status` | Server admin permission; redacted events and service readiness |

All public auth POSTs require the configured `Origin`; authenticated mutations also require `X-CSRF-Token`. The client sends cookies with `credentials: same-origin`. No session or broker token enters browser storage. Server errors return `detail: {code, message}` and validation errors omit submitted values. Server-mode demo-role/scenario controls are absent and cannot assign authority. Session and role checks are enforced in `backend/app/security.py` on every request.

The server adapter preserves an uncertain order response as Unknown with the original idempotency key and blocks a new request until reconciliation. The backend's paper fills are transactional and immediate; no real exchange outcome is modeled. Strategies are configuration/lifecycle records, not running trading algorithms. Market quotes remain explicitly fictional frontend/server fixtures. No production market feed, broker OAuth, account deletion, MFA or live execution API exists.

The remaining sections describe the retained isolated demo and historical proposal, not additional implemented endpoints.

## Executable boundary in this delivery

The application imports `paper` from `frontend/src/api/paper.ts`. It is an in-memory simulation, not an HTTP API and not a backend. React components consume typed `Session`, `Snapshot`, `Instrument`, `Ticket`, `Order` and `Strategy` values. No fetch, WebSocket, broker SDK or network execution endpoint exists in the application source. Dependencies and development tools may use network access during installation.

| Method | Input | Result / effect |
| --- | --- | --- |
| `register` | Fictional name/email | Pending demo verification; no password retained |
| `verify` | None | Verify pending fixture account or return expired/no-registration error |
| `login` | Demo email/sample password | In-memory trader session or generic error |
| `explore` | None | Public demo session with connected paper broker |
| `logout` | None | Clear identity, registration, request cache and ledger |
| `connect` | None | Paper connection or denied/timeout error |
| `submit` | Ticket, stable request identifier | Exactly one paper Order for that identifier; balance changes only on Filled |
| `reconcile` | Existing order identifier | Resolve Unknown to Filled once; do not submit a new order |
| `saveStrategy` | Configuration, optional strategy id | Draft; resets validation; active edits rejected |
| `transition` | Strategy id, next lifecycle status | Validate allowed state transition; activation requires connection/feed |
| `profile` | Name | Update current demo identity name |
| `toggleWatch` | Symbol | Toggle in-memory watchlist membership |
| `scenario` / `previewRole` | Demo fixture selector | Presentation testing only; no authority over any server |

Ticket: `{symbol, exchange, product, side, quantity, type, price}`. Quantity is a safe integer 1–1000. Symbols must be listed and match the exchange. Limit price must be finite and positive. Order: ticket plus stable `id`, `status`, `time`, and optional rejection `reason`. Unknown and rejected orders never create positions; reconciled or immediate fills do.

The request key is generated before review and reused after an error. The adapter checks its request cache both before and after the asynchronous delay, preventing concurrent duplicates. A real service must implement idempotency durably and atomically; this process-local Map is only a simulation.

## Proposed future integration contract — not implemented

These are independent GNK contract proposals requiring backend agreement. They are **not existing endpoints** and are not derived from OpenAlgo paths.

| Proposed resource | Responsibility |
| --- | --- |
| `GET /api/gnk/v1/session` | Resolve HttpOnly-cookie session and server-issued permissions |
| `POST /api/gnk/v1/auth/register`, `/verify`, `/login`, `/forgot`, `/reset`, `/logout` | Server-owned identity, rate limits, one-time expiring links and session revocation |
| `GET /api/gnk/v1/brokers`; `POST .../:id/authorization` | Server-generated authorization URL/state, approved redirect allowlist |
| Server callback `/api/gnk/v1/brokers/:id/callback` | Validate one-time state, exchange code server-side, retain broker tokens on server, redirect UI with opaque result |
| `GET /api/gnk/v1/account/summary` | Authorized balances and source timestamps |
| `GET /api/gnk/v1/instruments?q=...`; `/quotes`; `/watchlists` | Entitlements, symbol metadata, freshness and feed status |
| `POST /api/gnk/v1/paper/orders` | Validate and submit paper order with stable idempotency key |
| `GET /api/gnk/v1/paper/orders/:id` | Reconcile same request after uncertain network outcome |
| `/api/gnk/v1/paper/trades`, `/positions`, `/portfolio` | Authorized, consistent ledger reads |
| `/api/gnk/v1/strategies` and explicit lifecycle actions | Server validation, configuration version, testing evidence and transition enforcement |
| `/api/gnk/v1/profile`, `/security`, `/admin/*` | Server permissions and audit trail |

Production transport should use same-origin `credentials: include`, HttpOnly/Secure/SameSite cookies, CSRF protection for mutation and bounded request cancellation. Keep broker secrets and tokens entirely on the server. Do not store session or broker tokens in JavaScript storage or log request bodies. Validate runtime response schemas before trusting data. Server returns stable machine codes (e.g. `SESSION_EXPIRED`, `BROKER_EXPIRED`, `FORBIDDEN`, `FEED_STALE`, `ORDER_REJECTED`, `OUTCOME_UNKNOWN`) and redacted request identifiers for recovery.

An order submission timeout in a real service **does not prove no action occurred**. Mark it Unknown and query the original request's status. The simulator's `timeout` fixture explicitly fails before mutation; its `order-unknown` fixture models the uncertain-outcome branch separately. Preserve this distinction in a real adapter.

This frontend has no production adapter switch. Integrating any real service requires replacing the boundary deliberately, implementing and testing the server contracts, and removing public demo-role/scenario controls from the production surface. Do not deploy this demo as a secure trading product.
