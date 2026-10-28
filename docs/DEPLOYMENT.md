# FastAPI / PostgreSQL 17 / Redis 8 deployment

Production frontend origin: **`https://gnkalgo.com`** (the `www` hostname is also accepted for browser mutations). Put the canonical plain URL in `FRONTEND_URL`; do not include Markdown brackets. This setting controls email-link destinations and the allowed browser mutation origins. Same-origin Nginx proxies `/api/` to FastAPI; wildcard CORS is not enabled.

## Services

| Service | Implementation |
| --- | --- |
| web | React/Vite server-mode build served by Docker Nginx |
| api | FastAPI, SQLAlchemy 2.0, Psycopg 3, Argon2id, server-side authorization |
| postgres | PostgreSQL 17 with persistent named volume |
| redis | Redis 8; expiring session cache, rate limits and email queue hints; persistent AOF |
| migrate | One-shot Alembic upgrade before API startup |
| worker | Durable PostgreSQL email outbox and bounded SMTP delivery attempts via Redis queue |

The base Compose configuration exposes only Nginx on `127.0.0.1:8080`; database, Redis and API ports are private. API runs as a non-root user. `compose.production.yaml` changes web exposure to 80/443 and mounts TLS configuration/certificates into the same Docker Nginx service. Do not start another Nginx listener on those ports.

## Prepare production

1. Install Docker Engine/Desktop with its Linux engine running and Compose 2.24.4+ (`!override` is used by the TLS override).
2. Copy `.env.example` to `.env`. Choose a new random PostgreSQL password and set the matching URL-encoded password in `DATABASE_URL`. Keep `.env` private; it is ignored by Git.
3. Keep `FRONTEND_URL=https://gnkalgo.com`, `ENVIRONMENT=production`, and `COOKIE_SECURE=true`.
4. Supply SMTP host, port, username/password and sender. Production startup requires configured SMTP with STARTTLS; real email delivery needs a valid sender/provider. No SMTP credentials are supplied with this project.
5. Supply valid certificates for `www.gnkalgo.com` at `secrets/tls/fullchain.pem` and `secrets/tls/privkey.pem`. This directory is ignored. Configure certificate renewal outside the application and reload Nginx after renewal.
6. Point the domain to your host and allow 80/443. Inspect existing services before binding those ports.

```powershell
Copy-Item .env.example .env
# Edit .env privately before continuing.
docker compose -f compose.yaml -f compose.production.yaml config --quiet
docker compose -f compose.yaml -f compose.production.yaml up -d --build
docker compose ps
```

Check `https://www.gnkalgo.com/api/health/ready` for readiness. `/api/health/live` reports process health only. This project has not been deployed or tested against that domain.

For local HTTP development, explicitly use `ENVIRONMENT=development`, `COOKIE_SECURE=false`, and `FRONTEND_URL=http://127.0.0.1:8080` in a **local** `.env`. Use the base Compose file without the TLS override. For Vite server development on 5173, use that exact origin instead. The Vite proxy forwards `/api` to local port 8000.

## Run Python directly

```powershell
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.lock
# Set DATABASE_URL, REDIS_URL, FRONTEND_URL and COOKIE_SECURE for local services.
.venv/Scripts/python -m alembic upgrade head
.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
# Separate terminal, same environment:
.venv/Scripts/python -m app.worker
```

From `frontend`, set `VITE_API_MODE=server` for `npm run dev`. Without this variable, the standalone in-memory demo remains available. Docker builds select server mode by default. Build-time Vite variables are public and must contain no secrets.

## Administrator bootstrap

There is no public role assignment endpoint and no default administrator/password. Create an account using the local CLI with its hidden password prompt:

```powershell
docker compose exec api python -m app.cli create-admin --email YOUR_ADMIN_EMAIL
```

The command creates a verified administrator only if the email is new. It never promotes or overwrites an existing user. Admin endpoints check the database role on every request; suspending a user or resetting a password revokes their existing sessions through a session-version change.

## Checks and delivery

```powershell
cd backend
.venv/Scripts/python -m ruff check app tests migrations
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m alembic check
```

The local default tests use SQLite and FakeRedis. To run real service tests, provide a **dedicated disposable** `gnk_test` PostgreSQL database via `TEST_DATABASE_URL`, and `TEST_REDIS_URL` pointing to an isolated Redis test database. Apply Alembic to that database before pytest. The PostgreSQL test fixture removes rows from application tables between tests; never point it at a development or production database.

`.github/workflows/ci.yml` runs frontend builds/unit/E2E, server-mode transport tests, PostgreSQL 17/Alembic/Redis 8 service tests and Docker image builds. `.github/workflows/publish.yml` provides manually triggered container delivery to GHCR, gated by the GitHub `production` environment. Configure required reviewers there if desired. These workflow files have not been pushed or run on GitHub; this directory has no Git remote.

## Operations and limits

- Back up PostgreSQL and test restoration before upgrades. Named volumes retain data on restart. Do not delete production volumes as a recovery step.
- Migrations are explicit and run before the API. No application startup `create_all` or automatic production downgrade is used.
- Email links contain 256-bit random tokens in URL fragments, stored only as SHA-256 digests. The browser removes the fragment after reading it. API validation responses omit submitted values. Neither Nginx nor Uvicorn access logging captures links/passwords.
- Mail delivery is at least once with five bounded attempts. SMTP outages can leave unsent outbox rows; inspect `mail_outbox` metadata or request a fresh link after fixing SMTP. Do not log message bodies. There is no exactly-once external email guarantee.
- Session IDs are opaque HttpOnly, SameSite=Strict cookies, stored as digests in Redis keys. CSRF tokens are held in browser memory and validated on authenticated mutations. Origin validation protects public auth mutations. Production HTTPS is required.
- Only paper brokerage, fictional quotes and lifecycle simulation are implemented. No live broker integration, market-data entitlement, MFA, exchange risk controls, full trading engine or financial settlement is provided. The backend does not make the illustrative dashboard performance into real account data.
- Docker Engine was unavailable during local verification. Compose configuration parsing, Python tests and SQLite migrations passed; actual image builds, PostgreSQL row-lock integration, Redis 8 integration, SMTP provider delivery, certificates, DNS and production rollout remain unverified until executed in their target environments.

Technology references used: [FastAPI](https://fastapi.tiangolo.com/) and [SQLAlchemy 2.0 PostgreSQL/Psycopg documentation](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html).
