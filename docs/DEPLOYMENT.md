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

The Compose stack exposes the web container only on `127.0.0.1:8080`; database, Redis and API ports are private. API runs as a non-root user. In production, the host's Nginx owns public ports 80/443 and proxies GNK requests to the Docker web container. This allows other host Nginx sites to keep running without a port conflict.

## Prepare production

1. Install Docker Engine/Desktop with its Linux engine running and Compose 2.24.4+ (`!override` is used by the production override).
2. Copy `.env.example` to `.env`. Choose a new random PostgreSQL password and set the matching URL-encoded password in `DATABASE_URL`. Keep `.env` private; it is ignored by Git.
3. Keep `FRONTEND_URL=https://gnkalgo.com`, `ENVIRONMENT=production`, and `COOKIE_SECURE=true`.
4. Supply SMTP host, port, username/password and sender. Production startup requires configured SMTP with STARTTLS; real email delivery needs a valid sender/provider. No SMTP credentials are supplied with this project.
5. Supply valid certificates covering `gnkalgo.com` and `www.gnkalgo.com` at `secrets/tls/fullchain.pem` and `secrets/tls/privkey.pem`. The host Nginx configuration reads these files directly. The directory is ignored; configure certificate renewal and reload host Nginx after renewal.
6. Point both domains to your host and allow 80/443. The host Nginx must be installed and running; do not bind Docker directly to those ports.

### Optional broker account linking

The authenticated Brokers page supports account identity linking for Dhan, FYERS and Zerodha. It does not submit live orders. Dhan access tokens are encrypted at rest; FYERS and Zerodha access tokens are discarded. Apply for the relevant broker developer/partner credentials and register these exact callback URLs in each provider application:

```text
https://gnkalgo.com/api/gnk/v1/brokers/dhan/callback
https://gnkalgo.com/api/gnk/v1/brokers/fyers/callback
https://gnkalgo.com/api/gnk/v1/brokers/zerodha/callback
```

The broker code in each callback path must match exactly: `dhan`, `fyers`, or `zerodha`. OpenAlgo's local `http://127.0.0.1:5000/<code>/callback` is not a GNK production callback URL. Configure the provider credentials only in the backend environment, never in Vite variables or frontend code:

```dotenv
DHAN_PARTNER_ID=
DHAN_PARTNER_SECRET=
DHAN_TOKEN_ENCRYPTION_KEY=
FYERS_CLIENT_ID=
FYERS_APP_SECRET=
ZERODHA_API_KEY=
ZERODHA_API_SECRET=
```

Keep the production environment file private and restrict its filesystem permissions (for example, `chmod 600 .env`). Generate `DHAN_TOKEN_ENCRYPTION_KEY` with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`, keep it private, and back it up securely; losing it makes stored Dhan sessions unreadable. Dhan account linking requires Dhan's approved partner consent flow; ordinary individual Dhan access tokens are not accepted. The OAuth callback exchanges credentials server-side, displays the broker account name and masked final four characters for explicit confirmation, and stores the access token encrypted with its provider expiry. The token is not refreshed and does not provide trading access. Dhan linking is unavailable unless the encryption key and partner credentials are configured. Follow each broker's current developer terms and seek qualified advice about applicable SEBI/exchange obligations before offering any trading service.

Broker callback paths have host-Nginx access logging disabled because providers return one-time authorization values in callback URLs. Keep that logging exception if changing the host Nginx configuration.

Provider references: [OpenAlgo Dhan plugin](https://github.com/marketcalls/openalgo/tree/main/broker/dhan), [OpenAlgo FYERS plugin](https://github.com/marketcalls/openalgo/tree/main/broker/fyers), [OpenAlgo Zerodha plugin](https://github.com/marketcalls/openalgo/tree/main/broker/zerodha), [Dhan partner authentication](https://dhanhq.co/docs/v2/authentication/), [FYERS API v3](https://myapi.fyers.in/docsv3), and [Kite Connect login](https://kite.trade/docs/connect/v3/user/).

### Live-trading control plane status

The dashboard includes a fail-closed live-session control panel. Dhan authorization tokens are now encrypted at rest, but the live Dhan order path is not implemented: symbols are fixtures rather than verified Dhan instruments, and server-enforced risk limits and order reconciliation are missing. Live mode requests are persisted for audit, but confirmation suspends rather than activates the session; the GNK order endpoint remains paper-only. The Emergency Stop can be activated by its user and cleared only by an administrator. Clearing it does not resume a session.

Do not enable live order routes in this release. Production live trading requires verified Dhan instrument mapping, explicit server-side order and loss caps, per-user account validation, reliable idempotency and reconciliation for ambiguous broker responses, and an independent review of operational and regulatory requirements. No production live order can be placed by this release.

The control-session expiry defaults to 900 seconds and can be set with `LIVE_SESSION_TTL_SECONDS` (60–86400). Alembic migration `0003` adds the session/event tables and user emergency-stop flag; Compose applies it before the API starts.

```bash
# On the Ubuntu server, from the repository root:
docker compose -f compose.yaml -f compose.production.yaml config --quiet
docker compose -f compose.yaml -f compose.production.yaml up -d --build
```

Configure the GNK virtual host in the host's Nginx using [`nginx.host.conf`](../deploy/nginx.host.conf). Review existing files under `/etc/nginx/sites-enabled` first; replace or update only the GNK virtual host, and preserve other sites. Ensure the certificate paths in that file match the actual certificate location. Then validate and reload the host Nginx:

```bash
sudo nginx -t
sudo systemctl reload nginx
curl -fsS http://127.0.0.1:8080/api/health/live
curl -fsS https://gnkalgo.com/api/health/ready
```

For initial setup only, the GNK virtual host can be installed with:

```bash
sudo cp deploy/nginx.host.conf /etc/nginx/sites-available/gnkalgo
sudo ln -sfn /etc/nginx/sites-available/gnkalgo /etc/nginx/sites-enabled/gnkalgo
sudo nginx -t && sudo systemctl reload nginx
```

Do not install a duplicate GNK server block if an existing GNK site is enabled; update that file instead. Confirm the Docker web mapping is `127.0.0.1:8080->80` and the API is healthy:

```bash
docker compose -f compose.yaml -f compose.production.yaml ps
```

For a local, non-production Docker run, the base Compose configuration still binds only to localhost:

```powershell
Copy-Item .env.example .env
# Edit .env privately before continuing.
docker compose -f compose.yaml config --quiet
docker compose -f compose.yaml up -d --build
docker compose ps
```

Check `https://www.gnkalgo.com/api/health/ready` for readiness. `/api/health/live` reports process health only. This project has not been deployed or tested against that domain.

## Manage the production stack

From the repository root on the Ubuntu server, make the helper executable once:

```bash
chmod +x deploy/gnk-service.sh
```

Then use it to manage the stack:

```bash
./deploy/gnk-service.sh start
./deploy/gnk-service.sh stop
./deploy/gnk-service.sh restart api
./deploy/gnk-service.sh build
./deploy/gnk-service.sh deploy
./deploy/gnk-service.sh status
./deploy/gnk-service.sh logs api
./deploy/gnk-service.sh docker-status
./deploy/gnk-service.sh docker-stop-all
./deploy/gnk-service.sh health
```

`deploy` fast-forward pulls `origin/main`, then builds and starts the complete production stack; it runs database migrations through Compose before the API starts. Use `update` instead to build and start from the current local source without pulling. `start` does not rebuild, and `restart` only restarts existing containers. `stop` preserves containers and volumes.

`docker-status` lists all containers on the Docker host and displays each running container's processes. `docker-stop-all` stops all running Docker containers—including unrelated applications—after requiring the exact confirmation `STOP ALL DOCKER CONTAINERS`. It sends a graceful stop signal and preserves containers, images, and volumes; it does not stop host services or kill arbitrary host processes. Use this host-wide command only when you intend to stop every Docker workload.

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
