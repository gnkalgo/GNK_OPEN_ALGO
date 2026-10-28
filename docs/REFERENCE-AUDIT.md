# Frontend audit and mapping

Audit performed 28 October 2026. The supplied workspace `D:\GNK_OPEN_ALGO` was empty, with no frontend, package manifest, router, components, test setup, Git repository or AGENTS.md. There was no local functionality to migrate or preserve. Other GNK checkouts were not modified.

## Reference evidence

Inspected the public OpenAlgo frontend through the connected GitHub tools:

- [frontend directory](https://github.com/marketcalls/openalgo/tree/main/frontend): source, public assets, e2e, Vite, TypeScript, Vitest and Playwright configuration.
- [package.json](https://github.com/marketcalls/openalgo/blob/main/frontend/package.json): React, TypeScript, Vite, Tailwind, React Router, Lucide, shared Radix primitives, React Query, Zustand, Vitest, testing-library and Playwright.
- [App.tsx](https://github.com/marketcalls/openalgo/blob/main/frontend/src/App.tsx): public routes, broker authentication routes, nested application layouts, strategy pages and admin/settings routes. Observed App.tsx blob SHA: `6ced0517270a85f7d3276d0276c5f8d1b1f9c2fc`. The reference is a moving branch; these observations describe the audit snapshot.
- [layout directory](https://github.com/marketcalls/openalgo/tree/main/frontend/src/components/layout): Layout, FullWidthLayout, Navbar, AccountControls, Footer, MobileBottomNav and component tests.
- [Dashboard.tsx](https://github.com/marketcalls/openalgo/blob/main/frontend/src/pages/Dashboard.tsx): cards, margin data, loading/error handling, distinct broker expiration vs app expiration.
- [OrderBook.tsx](https://github.com/marketcalls/openalgo/blob/main/frontend/src/pages/OrderBook.tsx): shared table, badges, empty state, review/action dialogs, filter controls and order-event refresh.
- [strategy/Wizard.tsx](https://github.com/marketcalls/openalgo/blob/main/frontend/src/pages/strategy/Wizard.tsx): configuration sections, inputs/selects, validation and dialogs.
- [playwright.config.ts](https://github.com/marketcalls/openalgo/blob/main/frontend/playwright.config.ts): desktop and mobile browser projects and local Vite web-server setup.

No OpenAlgo endpoint, auth store, secret management, backend, business logic or branding was copied. This is an independently written frontend informed by its screen organization and reusable UI patterns. This was not an audit of OpenAlgo's complete feature set or backend behavior.

## Mapping presented before implementation

| Reference pattern | GNK ALGO surface | Decision |
| --- | --- | --- |
| Layout / Navbar / MobileBottomNav | Shell / sidebar / topbar / mobile drawer | Independently implement consistent protected workspace navigation |
| Shared Card / Badge / Input / EmptyState | Panel / Badge / labeled fields / Empty | Reuse concepts; create compact accessible components |
| Dashboard margin cards and status handling | Fictional balances, sample P&L, performance and watchlist | Distinguish app expiration, broker expiration and feed state |
| OrderBook tables and dialogs | Orders, trades, positions, portfolio, paper review | Independent typed ledger; safe unknown outcome recovery |
| Strategy Wizard / Detail route organization | Strategy editor and lifecycle monitor | Independent lifecycle state machine and paper fixture checks |
| Profile / admin page families | Profile, security, appearance, user management, status and audit | Demo role gate; explicitly document server authority |
| Vitest / testing-library / Playwright | Component and state tests; desktop/mobile journeys | New tests against GNK route and simulator contracts |

The GNK route map intentionally uses `/app/...`; OpenAlgo route paths and endpoints are not treated as GNK contracts. The supplied brand artwork is used unchanged on the landing and identity screens, with GNK wordmark styling for compact terminal navigation.
