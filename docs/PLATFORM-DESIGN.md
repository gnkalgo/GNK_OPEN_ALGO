# GNK ALGO independent platform design

Decision date: 29 October 2026. Product direction: multi-user commercial platform with direct broker execution as the target. Current delivery stage: authenticated paper trading development platform. This document distinguishes implemented controls from commercial launch requirements; it does not grant regulatory approval.

## Product requirements and acceptance

| Requirement | Current evidence | Acceptance before commercial live release |
| --- | --- | --- |
| Independent GNK identity, contracts and workflows | GNK brand assets, `/app` workspace and `/api/v1/gnkalgo` API; new account control center | Verify provenance of retained source and artwork; owner selects distribution license |
| Isolated trader accounts | Server sessions, server role checks, user-scoped database queries and risk policy | PostgreSQL concurrent isolation tests, full cross-account route audit, independent security review |
| Explicit trading authority | Broker linking and live-session requests are distinct; execution remains disabled | Revalidate broker identity and trading rights, expiry, scope and account on every execution boundary |
| Pre-trade controls | Paper quantity, per-order value, daily gross turnover and halt checked on server | Live margin, available holdings, exposure, loss, exchange bands, tick/lot and order-type controls |
| Reliable order handling | UUID idempotency, durable paper result and same-key lookup | Broker client references, partial fills, unknown submissions, cancellation races and broker reconciliation |
| Honest user experience | Fictional market labels, paper badges and capability status | Licensed data timestamps, stale-feed blocks, realistic executions; no fabricated performance |
| Operations and oversight | Audit events, admin disable/emergency stop, health checks, migration and deployment scripts | MFA/step-up, reviewed support access, append-only external audit archive, alerting and tested disaster recovery |
| Commercial management | Not implemented | Organization membership/roles, entitlements, billing, privacy/retention and customer terms |
| Strategy automation | Configuration lifecycle only | Versioned engine, isolated runners, deterministic event replay and resource quotas |

## Architecture decisions

Use a modular monolith initially: React/TypeScript SPA, FastAPI domain services, PostgreSQL as system of record, Redis for revocable sessions and short-lived authorization state, separate mail worker and Nginx ingress. This fits the existing repository and permits transactions spanning account risk and the paper ledger. Redis is not the durable source of orders. Splitting into microservices now would add distributed failure modes without an implemented broker execution engine.

The current `main.py` still contains legacy application routes. New account governance lives in `app/risk.py`; incremental extraction must preserve existing route contracts and tests. Do not rewrite working authentication simply to change its appearance. The legacy GNK callback aliases are retained for existing broker applications; they are not OpenAlgo compatibility routes.

Domain boundaries and target ownership:

| Boundary | Implementation now | Next responsibility |
| --- | --- | --- |
| Identity | `security.py`, authentication routes, Redis sessions | MFA, access review, scoped support sessions |
| Accounts and governance | `models.py`, `risk.py`, control center | Organizations, memberships, policy approval history |
| Broker authorization | `broker_auth.py`, token vault and connection routes | Provider-specific credential rotation and trading permission validation |
| Instrument and market data | Fictional quotes only | Licensed feed adapter, canonical instrument identifiers and freshness policy |
| Execution | Paper submission in `main.py` | Durable order intents, dispatcher, provider adapters and execution events |
| Risk | Per-user persisted paper policy | Distinct live policy/margin service; no reuse of fixture prices |
| Reconciliation | Paper result lookup | Broker order/trade polling and stream reconciliation, break resolution |
| Strategies | Saved configurations and lifecycle | Isolated runner with no direct broker credentials |
| Operations | Admin routes, health, worker and deployment scripts | Outbox dispatcher, metrics, incident tooling and restore verification |

## Account and trust model

The authenticated server session determines `user_id`; mutations never accept an owner identifier from the browser. A user owns a paper account, broker connections, strategies, risk policy and order ledger. The current administrator is a global operator; this is not yet an organization-admin role. Commercial organizations will require separate membership and scoped permissions before introducing teams or billing.

Browser navigation guards are presentation only. Session revocation, enabled/verified account checks, role checks, same-origin validation and CSRF remain server responsibilities. Broker secrets remain server-side; callback states and confirmation tokens are short-lived and single-use. Current encrypted credential retention covers Dhan; do not claim an execution-ready token vault for every provider.

## Implemented paper risk contract

`GET /api/v1/gnkalgo/risk-policy` returns the caller's effective policy, used turnover, administrator stop and `live_orders_enabled: false`. `PUT` accepts only `max_order_value`, `max_daily_value`, `max_quantity`, `halted`. Monetary values are decimal strings in INR. Limits cannot exceed service ceilings: INR 1,000,000 per order, INR 5,000,000 gross daily turnover, 1,000 units. These are simulator ceilings, not broker margin or regulatory limits.

Missing policy rows use explicit service defaults. Updates and new order booking serialize on the user's PostgreSQL row. Both buys and sells consume daily gross turnover, using filled paper orders from midnight Asia/Kolkata. Rejections consume no turnover or balance. Rejected results are durable: replaying the same UUID returns the same outcome after a policy change. A changed ticket with the same UUID remains a conflict. A paper policy halt rejects new paper orders. The existing live emergency stop is separate; paper simulation remains available during a live stop. Returning an existing result is allowed during a halt because it does not execute again. A halt does not cancel or flatten anything.

Policy updates create audit events. The live emergency stop cannot be cleared by the user's policy update. Browser demo mode cannot persist or enforce these server controls; its control center explicitly requires a server session.

`GET /api/v1/gnkalgo/platform` returns implemented capability states and unresolved release blockers. It is an authenticated development capability manifest, not a legal or infrastructure health attestation.

## Target live order workflow (not implemented)

1. Authenticate and authorize an account-scoped command; require recent step-up for activation and sensitive changes.
2. Resolve canonical instrument, exchange segment, tick/lot, valid session and permitted order type from approved broker/exchange sources.
3. Lock account policy/reservations, reject stale data and unresolved outcomes, validate live funds/margin/holdings and applicable risk limits.
4. Commit the immutable intent, payload hash, idempotency key, policy version, reservation and transactional dispatch outbox together.
5. A dispatcher calls an independently implemented provider adapter using an account-scoped credential handle. Neither strategy code nor the browser receives credentials.
6. Record acknowledgement or unknown outcome. Never infer rejection from a network timeout; never blindly resubmit a non-idempotent broker order.
7. Reconcile using broker references and trades. Apply monotonic cumulative fills; settle/release reservations only from authoritative evidence. Keep cancellation requested separate from cancellation confirmed.
8. Present orders, fills, positions and incidents from the reconciled ledger. Emergency actions separately halt new entries, cancel pending orders, and request flattening; each needs its own status.

Suggested internal adapter operations are authorization validation, instrument resolution, order submission, order lookup, cancellation, trade lookup and account snapshot. These are GNK concepts, not a copied external API. Implement against each broker's official contract only after reviewing commercial terms. No generic adapter may claim unsupported order types, atomic baskets, idempotency or execution certainty.

## Delivery roadmap and release evidence

| Stage | Deliverables | Exit evidence |
| --- | --- | --- |
| Foundation (this checkout) | Account isolation, original GNK UI, paper order ledger, persisted paper risk, dependency declarations, provenance policy | Local checks documented; no commercial production readiness claim |
| Commercial identity | Organizations/memberships, scoped RBAC, MFA, entitlements, subscription boundaries, consent/retention | Tenant escape tests, access review, privacy and billing acceptance |
| First live provider | Choose provider through a documented business/terms review; instruments, licensed data, margin, durable dispatcher and reconciliation | Broker sandbox/contract tests including timeout/partial-fill/restart and paper/live separation |
| Controlled pilot | Approved account/strategy cohort, static egress where required, monitoring, reconciliation operations, backup/restore | Broker/exchange applicability sign-off, security review, incident/restore drill and staged risk caps |
| Commercial launch | Customer terms, operational support, licensing notices and required registrations | Completed signed release record, approved deployment change, observed production acceptance |
| Expansion | Additional independently implemented brokers, strategy engine, research/backtesting | Per-provider conformance and strategy/data licensing review; no extrapolated certification |

Each stage remains incomplete until its evidence exists. Current broker account linking does not satisfy the live provider stage. Deployment and paid customer onboarding are not part of this local implementation.
