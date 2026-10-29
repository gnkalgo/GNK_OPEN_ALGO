# Route map and UI specification

The routes work in both isolated demo mode and `VITE_API_MODE=server`. In server mode, FastAPI owns authentication/authorization, sessions persist through refresh using an HttpOnly cookie, registration/verification/reset use SMTP delivery, account data is stored in PostgreSQL, and admin screens call server-enforced endpoints. Demo fixture/role controls are hidden. Quotes, performance samples, order execution and strategy tests remain paper simulations. See [the implemented API](API-BOUNDARY.md).

## Routes and page behavior

| Route | Access | Page specification |
| --- | --- | --- |
| `/` | Public | GNK artwork, tagline, platform benefits, workflow, paper safety, registration/login and immediate demo exploration |
| `/register` | Public | Fictional name/email, sample password, demo acknowledgement, native validation; registers in memory |
| `/verify-email` | Public | Explicit simulated verification action, expired-link error and renewal |
| `/login` | Public | Email/sample password, generic failed-login response, recovery link and session-expired feedback |
| `/forgot-password` | Public | Email field, generic response, simulated reset-link entry |
| `/reset-password` | Public | Sample password input, invalid/expired link feedback; valid demo query enables recovery simulation |
| `/app` | Demo session | Redirects to dashboard |
| `/app/brokers` | Demo session | Paper connection consent preview; no real broker secret fields |
| `/app/brokers` in server mode | Authenticated account | Dhan, FYERS and Zerodha account-link cards, configuration status, masked account identity, unlink and explicit confirmation; live orders remain disabled |
| `/app/brokers/callback` | Broker callback | Handles opaque, short-lived confirmation result; never displays or stores provider tokens |
| `/app/dashboard` | Demo session | Balance, sample P&L, open-position count, active strategies, period chart, watchlist, illustrative positions and recent session activity |
| `/app/markets` | Demo session | Symbol/company search, watchlist membership toggle, instrument selection, fictional chart and quote, order-entry link; `?symbol=` preserves selection |
| `/app/orders/new` | Demo session | Buy/sell, instrument, exchange, delivery/intraday, whole quantity, market/limit and price; explicit review and paper submission; blocks expired broker/feed |
| `/app/orders` | Demo session | Session orders, status filters, full request identifier, side, size, price, time, rejection reason and unknown status reconciliation |
| `/app/trades` | Demo session | Filled session orders only; link to positions |
| `/app/positions` | Demo session | Signed net position and net cost aggregated from filled orders; mark value and mark-to-market |
| `/app/portfolio` | Demo session | Current simulated net holdings using the same signed ledger; empty state before first fill |
| `/app/strategies` | Demo session | Strategy cards with signal, instrument, risk limit, quantity, mode and lifecycle badge; create entry |
| `/app/strategies/new` | Demo session | Name, instrument, signal template, whole quantity and maximum paper loss; save creates Draft |
| `/app/strategies/:id` | Demo session | Configure/save, validate, fixture test, confirm activate/resume, monitor, pause, confirm stop; edit invalidates validation; active configuration locked |
| `/app/profile` | Demo session | Tabs for editable name, immutable demo email, security/recovery, carbon/daylight/system theme and notification preview |
| `/app/admin` | Demo admin | Trader denied state; demo user suspend/restore, simulator system status, audit events, maintenance-preview setting |
| `/app/help` | Demo session | First-order steps and safe recovery guidance |
| unmatched | Public | Not-found explanation and home link |

## Component plan

`Shell` owns sidebar expansion, mobile dismissal, breadcrumb/topbar, notification dialog, mock index strip, connectivity banners, footer and scenario controls. Session guards and demo role guards are presentation only.

`PageHead`, `Panel`, `Badge`, `Change`, `Feedback`, `Empty`, `TextLink`, `Brand` and `Chart` are shared display primitives. `Modal` uses the native top-layer dialog for focus containment, Escape and backdrop dismissal. It restores focus on unmount. Forms use semantic labels, native required/number/email constraints and API-boundary error messages. Loading and success use status regions; errors use alerts. Status always includes a word or signed value as well as color.

`usePaper` subscribes to immutable snapshots using `useSyncExternalStore`. `useAction` centralizes request status, error and success feedback. `paper.ts` defines typed inputs, independent fixtures, request deduplication, broker/feed gates, net balance effects and strategy transitions. Books aggregate one shared ledger rather than maintaining separate copies.

## Design tokens

| Token | Carbon value | Purpose |
| --- | --- | --- |
| Background | `#0b0d10` | Main terminal canvas |
| Surface | `#121519` | Cards and panels |
| Raised surface | `#171b20` | Controls and secondary sections |
| Border | `#262b31` | Subtle dividers |
| Text | `#e8eaed` | Primary content |
| Muted | `#8d959f` | Labels and descriptions |
| Accent | `#b4f17d` | GNK actions and current navigation |
| Positive | `#87d5a0` | Signed gains and confirmed success |
| Negative | `#f18b8b` | Signed losses, rejection and critical errors |
| Pending | `#e3bd7e` | Paper mode, unknown, paused and recovery states |
| Font | Inter if installed, Segoe UI, Arial, sans-serif | Local-first typography, no third-party font request |
| Radius | 5–7px controls/panels; 10px dialog | Compact, restrained terminal geometry |
| Spacing | 4, 8, 12, 16, 20, 24, 32px | Consistent rhythm; dense data with readable forms |

Tables use tabular numerals, compact rows, persistent headers within each table and horizontal overflow. Desktop uses a 218px collapsible sidebar and multi-column panels. At 980px the content progressively stacks; at 700px the sidebar becomes a dismissible drawer and cards use two columns. Charts include text labels and accessible names. Reduced-motion preferences disable animations. Theme choices affect the current session only; system mode samples the current OS preference on selection.

## Shared states

| State | UI and recovery |
| --- | --- |
| Loading | Processing status, disabled submit controls; slow fixture scenario and dashboard loading message |
| Empty | Clear explanation and action link; no stale fabricated order records |
| Success | Labeled success feedback and state badges |
| Error / timeout | Actionable alert; no hidden mutation on simulated timeout; allow retry |
| Offline | Browser connectivity alert; mutation guard; fixture feed offline banner blocks orders and activation |
| Session expired | Clears demo identity; redirect to login with explanation |
| Broker expired | Preserves app identity; reconnect broker independently |
| Unknown order | Amber labeled status, request identifier, explicit reconcile; blocks new orders |
| Unauthorized | Protected-route redirect or admin access-denied screen |

Real broker app credentials stay in backend environment configuration. Provider login secrets are never collected by GNK, access tokens are exchanged server-side and discarded after account identity verification, only a broker display name and masked account identifier are persisted, and no live trading control exists. No client-only route or role preview can substitute for server access checks.

## GNK governance redesign (29 October 2026)

`/app/controls` adds a responsive control center with execution status, per-user persisted paper limits, gross turnover, account halt and capability list. Mutations require a server session; demo controls remain disabled and explicitly labeled. Loading/error states with reload, server acknowledgement and administrator-stop explanation are exposed accessibly.

The dashboard now derives account P&L and open-position count from submitted fills, labels the performance chart as an example, displays the India-calendar date and distinguishes active strategy configurations from a running engine. Position books use weighted average cost with realized P&L separated from remaining open cost. Supplied GNK artwork is preserved.
