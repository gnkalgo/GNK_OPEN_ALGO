# Dhan live pilot setup

The pilot supports NSE EQ delivery BUY LIMIT orders with a separate order ledger,
explicit preview and confirmation, account checks, margin checks and reconciliation.
It does not run strategies, supply live market quotes, or implement sells, order
modifications or cancellations. Manage these actions in Dhan's terminal.

## Choose the correct login credentials

For an API Key and Secret created in Dhan Web, use individual authentication:

```dotenv
DHAN_AUTH_MODE=individual
DHAN_CLIENT_ID=YOUR_DHAN_CLIENT_ID
DHAN_API_KEY=YOUR_REPLACEMENT_API_KEY
DHAN_API_SECRET=YOUR_REPLACEMENT_API_SECRET
DHAN_TOKEN_ENCRYPTION_KEY=YOUR_FERNET_KEY
FRONTEND_URL=https://gnkalgo.com
PAPER_TRADING_ENABLED=false
DHAN_LIVE_ENABLED=true
DHAN_LIVE_APPROVED=true
DHAN_EXECUTION_IP=YOUR_REGISTERED_SERVER_EGRESS_IP
DHAN_LIVE_ACCOUNT_IDS=YOUR_APPROVED_DHAN_CLIENT_ID
DHAN_LIVE_SECURITY_IDS=YOUR_APPROVED_NUMERIC_NSE_EQ_IDS
DHAN_LIVE_MAX_ORDER_VALUE=50000
DHAN_LIVE_MAX_DAILY_VALUE=50000
DHAN_LIVE_MAX_QUANTITY=10
```

Set `DHAN_LIVE_APPROVED=true` only when actual deployment acceptance and broker
approval are complete. This flag does not obtain broker permissions.
Keep the remaining database, Redis, HTTPS and SMTP settings from `.env.example`.
Use a private server `.env`; never put broker secrets in `VITE_` settings.

Register this redirect URL in the Dhan Web application:

```text
https://gnkalgo.com/api/gnk/v1/brokers/dhan/callback
```

For credentials issued through Dhan's partner onboarding, use
`DHAN_AUTH_MODE=partner`, `DHAN_PARTNER_ID` and `DHAN_PARTNER_SECRET` instead.
Do not put an individual API key in `DHAN_PARTNER_ID`.

Official authentication contracts:
https://dhanhq.co/docs/v2/authentication/

## Install the complete implementation

Updating only the Brokers page does not install the execution service. Deploy the
backend, frontend, migration `0006`, and related pilot modules together. Back up
the production database using the established deployment procedure first.

From the deployed project directory:

```sh
docker compose build api worker web
docker compose run --rm migrate
docker compose up -d --force-recreate api worker web
```

Refresh the approved instrument catalog each trading day, using the same numeric
IDs as `DHAN_LIVE_SECURITY_IDS` (replace the placeholder before running):

```sh
docker compose exec api python -m app.dhan_instruments --security-ids YOUR_COMMA_SEPARATED_NUMERIC_IDS
```

The importer validates Dhan's official instrument master and fails without
changing the catalog when selected IDs or required risk metadata are invalid.
Catalog entries expire after 18 hours and must be from the current India date.

## Connect and activate

1. Sign in to GNK and connect Dhan under Brokers; complete Dhan's browser login.
2. Confirm the account link. Reconnect old links to retain encrypted identity.
3. Review Trading mode and resolve every reported blocker.
4. Request a Dhan session and explicitly confirm activation.
5. Open the Dhan live desk, review a BUY LIMIT preview and confirm each order.
6. Reconcile any pending or unknown broker outcome before another submission.

With paper disabled, new simulator orders and paper connections are rejected by
the server. Existing paper history and idempotent result retrieval remain
available. The old paper order entry redirects to the separate Dhan live desk.
No order is submitted by applying environment settings or activating a session.
The backend accepts new live orders on weekdays 09:15-15:20 India time, subject
to broker trading availability. A session expires according to
`LIVE_SESSION_TTL_SECONDS` and cannot outlive its broker token.

Paper execution defaults to disabled when `PAPER_TRADING_ENABLED` is absent.
The production Compose override forces it off even if `.env` enables it.
For an isolated development paper server only, explicitly set
`PAPER_TRADING_ENABLED=true` and omit the production override.
