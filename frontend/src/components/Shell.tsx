import { useEffect, useState } from "react";
import {
  Activity,
  ArrowLeftRight,
  Bell,
  BookOpen,
  ChartNoAxesCombined,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  Command,
  FlaskConical,
  LayoutDashboard,
  LogOut,
  Menu,
  Search,
  Settings2,
  ShieldCheck,
  Unplug,
  Wallet,
  X,
  Zap,
} from "lucide-react";
import {
  Link,
  NavLink,
  Navigate,
  Outlet,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { paper, serverMode, type Scenario } from "../api/paper";
import { usePaper, useTradingStatus } from "../hooks";
import { Badge, Brand, Modal } from "./ui";
const navigation = [
  {
    title: "WORKSPACE",
    items: [
      ["Dashboard", "/app/dashboard", LayoutDashboard],
      ["Markets", "/app/markets", ChartNoAxesCombined],
      ["Orders", "/app/orders", ArrowLeftRight],
      ["Positions", "/app/positions", BookOpen],
      ["Portfolio", "/app/portfolio", Wallet],
    ],
  },
  {
    title: "AUTOMATION",
    items: [
      ["Strategies", "/app/strategies", Zap],
      ["Trade book", "/app/trades", Activity],
    ],
  },
  {
    title: "MANAGE",
    items: [
      ["Broker connections", "/app/brokers", Unplug],
      ["Dhan live desk", "/app/live", ShieldCheck],
      ["Control center", "/app/controls", ShieldCheck],
      ["Settings", "/app/profile", Settings2],
    ],
  },
] as const;
export const scenarios: Scenario[] = [
  "normal",
  "timeout",
  "login-failed",
  "expired-link",
  "broker-denied",
  "broker-expired",
  "feed-offline",
  "order-rejected",
  "order-unknown",
  "session-expired",
  "loading",
  "empty",
];
export function DemoLab() {
  const { scenario, session } = usePaper();
  if (serverMode) return null;
  return (
    <details className="demo-lab">
      <summary>
        <FlaskConical size={13} /> Demo scenarios
      </summary>
      <div className="demo-lab-body">
        <label>
          Simulate a state
          <select
            aria-label="Demo scenario"
            value={scenario}
            onChange={(e) => paper.scenario(e.target.value as Scenario)}
          >
            {scenarios.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </label>
        {session && (
          <label>
            Preview role (demo only)
            <select
              value={session.role}
              onChange={(e) =>
                paper.previewRole(e.target.value as "trader" | "admin")
              }
            >
              <option value="trader">Trader</option>
              <option value="admin">Admin</option>
            </select>
          </label>
        )}
        <p>In-memory fixtures only. No real identity, feed or broker.</p>
      </div>
    </details>
  );
}
export function Shell() {
  const { session, broker, scenario, strategies } = usePaper();
  const [collapsed, setCollapsed] = useState(false),
    [mobile, setMobile] = useState(false),
    [notifications, setNotifications] = useState(false);
  const [online, setOnline] = useState(navigator.onLine);
  const [logoutError, setLogoutError] = useState("");
  useEffect(() => {
    const update = () => setOnline(navigator.onLine);
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);
  const location = useLocation(),
    navigate = useNavigate();
  const trading = useTradingStatus(location.pathname);
  const tradingLabel = !serverMode ? "Paper trading" : !trading ? "Trading status unavailable" : trading.live_orders_enabled ? "Dhan live session active" : trading.paper_trading_enabled === false ? "Trading inactive" : "Paper trading";
  useEffect(() => {
    setMobile(false);
    document.querySelector("main")?.focus();
  }, [location.pathname]);
  useEffect(() => {
    const listener = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMobile(false);
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        navigate("/app/markets");
      }
    };
    window.addEventListener("keydown", listener);
    return () => window.removeEventListener("keydown", listener);
  }, [navigate]);
  if (!session)
    return (
      <Navigate
        to="/login"
        replace
        state={{ expired: scenario === "session-expired" }}
      />
    );
  return (
    <div className={`app-shell ${collapsed ? "collapsed" : ""}`}>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      {mobile && (
        <button
          className="sidebar-backdrop"
          aria-label="Close navigation"
          onClick={() => setMobile(false)}
        />
      )}
      <aside className={`sidebar ${mobile ? "mobile-open" : ""}`}>
        <div className="sidebar-brand">
          <Brand compact={collapsed} />
          <button
            className="icon-btn mobile-only"
            aria-label="Close menu"
            onClick={() => setMobile(false)}
          >
            <X size={18} />
          </button>
        </div>
        <div className="workspace-label">
          <span className="workspace-avatar">G</span>
          <span>
            Personal workspace<small>{tradingLabel}</small>
          </span>
          <ChevronRight size={14} />
        </div>
        <nav aria-label="Main navigation">
          {navigation.map((group) => (
            <div className="nav-group" key={group.title}>
              <span className="nav-group-title">{group.title}</span>
              {group.items.map(([label, to, Icon]) => (
                <NavLink to={to} key={to} title={label}>
                  <Icon size={18} />
                  <span>{label}</span>
                  {label === "Strategies" && <small>{strategies.length}</small>}
                </NavLink>
              ))}
            </div>
          ))}
          {session.role === "admin" && (
            <NavLink to="/app/admin">
              <ShieldCheck size={18} />
              <span>Administration</span>
            </NavLink>
          )}
        </nav>
        <div className="sidebar-bottom">
          <div className="upgrade-box">
            <div className="flex items-center gap-2">
              <ShieldCheck size={17} />
              <b>A safer space to trade</b>
            </div>
            <p>Test your edge. Trade with confidence.</p>
            <Link to="/app/strategies">
              Explore paper strategies <ChevronRight size={14} />
            </Link>
          </div>
          <Link className="help-link" to="/app/help">
            <CircleHelp size={17} />
            <span>Help & documentation</span>
            <span>↗</span>
          </Link>
          <button
            className="collapse-button"
            onClick={() => setCollapsed(!collapsed)}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? <ChevronRight size={17} /> : <ChevronLeft size={17} />}
            <span>Collapse sidebar</span>
          </button>
          <div className="sidebar-user">
            <span className="avatar">
              {session.name
                .split(" ")
                .map((x) => x[0])
                .slice(0, 2)
                .join("")}
            </span>
            <Link to="/app/profile">
              <b>{session.name}</b>
              <small>Personal account</small>
            </Link>
            <button
              className="icon-btn"
              aria-label="Logout"
              onClick={async () => {
                try {
                  await paper.logout();
                  navigate("/login", { replace: true });
                } catch {
                  setLogoutError(
                    "Sign out could not be confirmed. Reconnect and try again.",
                  );
                }
              }}
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>
      <div className="workspace">
        {logoutError && (
          <div className="banner warning" role="alert">
            {logoutError}
          </div>
        )}
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="icon-btn mobile-only"
              aria-label="Open menu"
              aria-expanded={mobile}
              onClick={() => setMobile(!mobile)}
            >
              <Menu size={19} />
            </button>
            <span>Workspace</span>
            <ChevronRight size={13} />
            <b>{location.pathname.split("/").pop()?.replace(/-/g, " ")}</b>
          </div>
          <div className="topbar-right">
            <Link className="global-search" to="/app/markets">
              <Search size={15} />
              <span>Search instruments…</span>
              <kbd>
                <Command size={10} /> K
              </kbd>
            </Link>
            <Badge tone={trading?.live_orders_enabled ? "red" : "amber"}>{tradingLabel}</Badge>
            <button
              className="icon-btn notification-button"
              aria-label="Notifications"
              onClick={() => setNotifications(true)}
            >
              <Bell size={18} />
              <i />
            </button>
            <Link
              className="avatar small-avatar"
              to="/app/profile"
              aria-label="Open profile"
            >
              {session.name[0]}
            </Link>
          </div>
        </header>
        {location.pathname !== "/app/live" && <div className="ticker-strip">
          {[
            ["NIFTY 50", "24,825.10", "+0.67%"],
            ["SENSEX", "81,467.10", "+0.54%"],
            ["BANK NIFTY", "51,295.80", "+0.82%"],
            ["INDIA VIX", "13.24", "−2.14%"],
          ].map(([name, value, change]) => (
            <div key={name}>
              <span>{name}</span>
              <b>{value}</b>
              <span className={name === "INDIA VIX" ? "negative" : "positive"}>
                {change}
              </span>
            </div>
          ))}
          <span className="ticker-note">FICTIONAL MARKET SNAPSHOT</span>
        </div>}
        <main id="main" tabIndex={-1}>
          {!online && (
            <div className="banner warning" role="alert">
              You are offline. Check your network connection before retrying.
              Mutations are blocked.
            </div>
          )}
          {location.pathname !== "/app/live" && broker === "Expired" && (
            <div className="banner warning" role="alert">
              Paper broker token expired.{" "}
              <Link to="/app/brokers">Reconnect broker →</Link>
            </div>
          )}
          {location.pathname !== "/app/live" && scenario === "feed-offline" && (
            <div className="banner warning" role="alert">
              Market feed disconnected. Prices are stale; new orders are
              blocked.{" "}
              <button onClick={() => paper.scenario("normal")}>
                Reconnect feed
              </button>
            </div>
          )}
          <Outlet />
        </main>
        <footer className="app-footer">
          <span>
            <span className="status-dot" />{" "}
            {location.pathname === "/app/live"
              ? "Dhan live order desk" : scenario === "feed-offline"
              ? "Feed offline"
              : "Paper simulator ready"}
            <i /> {location.pathname === "/app/live" ? "Confirmed live orders use real broker funds" : "All figures are fictional"}
          </span>
          <DemoLab />
          <span>
            GNK ALGO <span className="muted">v1.0</span>
          </span>
        </footer>
      </div>
      {notifications && (
        <Modal title="Notifications" close={() => setNotifications(false)}>
          <div className="modal-content">
            <Badge tone="green">Workspace ready</Badge>
            <p>
              Your paper trading environment is ready. All prices and activity
              are fictional.
            </p>
            <Link
              className="button"
              to="/app/brokers"
              onClick={() => setNotifications(false)}
            >
              Manage broker connection
            </Link>
          </div>
        </Modal>
      )}
    </div>
  );
}
