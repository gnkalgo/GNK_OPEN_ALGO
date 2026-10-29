import { ledger } from "../api/ledger";
import { useState } from "react";
import {
  ArrowDownLeft,
  ArrowRight,
  ArrowUpRight,
  CalendarDays,
  CircleDollarSign,
  Layers,
  Plus,
  RefreshCw,
  Wallet,
  Zap,
} from "lucide-react";
import { Link } from "react-router-dom";
import { instruments, money } from "../api/paper";
import { LiveTradingPanel } from "../components/LiveTradingPanel";
import { usePaper } from "../hooks";
import {
  Badge,
  Change,
  Chart,
  Empty,
  PageHead,
  Panel,
  TextLink,
} from "../components/ui";
export default function Dashboard() {
  const {
    session,
    balance,
    orders,
    strategies,
    activity,
    watchlist,
    scenario,
  } = usePaper();
  const [period, setPeriod] = useState("1D"),
    [refresh, setRefresh] = useState(false);
  const positions = ledger(orders, instruments);
  const openPositions = positions.filter(position => position.quantity !== 0);
  const pnl = positions.reduce((total, position) => total + position.realized + position.pnl, 0);
  const active = strategies.filter((s) => s.status === "Active").length;
  const metrics = [
    {
      title: "Available balance",
      value: money(balance),
      sub: "Ready for your next opportunity",
      icon: Wallet,
      extra: "Paper funds",
    },
    {
      title: "Paper P&L",
      value: money(pnl),
      sub: "Realized and unrealized, before fees",
      icon: CircleDollarSign,
      extra: "Fictional marks",
      positive: pnl >= 0,
    },
    {
      title: "Open positions",
      value: String(openPositions.length).padStart(2, "0"),
      sub: "From your submitted paper orders",
      icon: Layers,
      extra: "Paper ledger",
    },
    {
      title: "Active strategies",
      value: String(active).padStart(2, "0"),
      sub: `${strategies.length} total strategies in workspace`,
      icon: Zap,
      extra: "Configuration only",
    },
  ];
  return (
    <>
      <PageHead
        eyebrow="YOUR WORKSPACE, AT A GLANCE"
        title={`Good morning, ${session?.name.split(" ")[0]}.`}
        subtitle="Here’s how your trading day is shaping up."
      >
        <span className="date-label">
          <CalendarDays size={14} /> {new Intl.DateTimeFormat("en-IN", {day:"numeric",month:"short",year:"numeric",timeZone:"Asia/Kolkata"}).format(new Date())}
        </span>
        <button
          className="button"
          disabled={refresh}
          onClick={() => {
            setRefresh(true);
            setTimeout(() => setRefresh(false), 450);
          }}
        >
          <RefreshCw size={14} className={refresh ? "spin" : ""} />
          {refresh ? "Refreshing…" : "Refresh"}
        </button>
        <Link className="button primary" to="/app/orders/new">
          <Plus size={16} /> New paper order
        </Link>
      </PageHead>
      <div className="demo-notice">
        <ShieldIcon />
        <span>
          <b>Your ideas. A safe space to test them.</b> You’re in paper trading
          mode. Balances, prices, and results are fictional.
        </span>
        <Badge tone="amber">Simulation</Badge>
      </div>
      <LiveTradingPanel />
      {scenario === "loading" && (
        <div className="loading-line" role="status">
          Loading simulated account snapshot…
        </div>
      )}
      {scenario === "timeout" && (
        <div className="banner warning" role="alert">
          Account snapshot timed out. Previously loaded fictional data is shown.
          Use Demo scenarios to restore normal service.
        </div>
      )}
      <div className="metric-grid">
        {metrics.map((m) => (
          <article className="metric-card" key={m.title}>
            <div>
              <span>{m.title}</span>
              <m.icon size={17} />
            </div>
            <strong className={m.positive ? "positive" : ""}>{m.value}</strong>
            <div>
              <small>{m.sub}</small>
              <span
                className={m.positive ? "metric-tag positive" : "metric-tag"}
              >
                {m.extra}
              </span>
            </div>
          </article>
        ))}
      </div>
      <div className="dashboard-primary">
        <Panel
          title="Example performance curve"
          extra={<Badge tone="green">Illustrative data</Badge>}
        >
          <div className="performance-top">
            <div>
              <span className="muted">Illustrative portfolio value</span>
              <div className="portfolio-value">
                ₹5,42,860<span className="decimal">.50</span>
                <span className="positive performance-gain">
                  <ArrowUpRight size={14} /> +₹12,450.80 (2.35%)
                </span>
              </div>
            </div>
            <div className="segmented" aria-label="Chart period">
              {["1D", "1W", "1M", "3M", "1Y", "ALL"].map((p) => (
                <button
                  key={p}
                  aria-pressed={p === period}
                  className={p === period ? "selected" : ""}
                  onClick={() => setPeriod(p)}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
          <div className="chart-with-axis">
            <Chart period={period} />
            <div className="chart-axis">
              <span>5,45,000</span>
              <span>5,40,000</span>
              <span>5,35,000</span>
              <span>5,30,000</span>
            </div>
          </div>
          <div className="chart-time">
            {(period === "1D"
              ? ["09:15", "10:00", "11:00", "12:00", "13:00", "14:00", "15:30"]
              : ["Mon", "Tue", "Wed", "Thu", "Fri"]
            ).map((t) => (
              <span key={t}>{t}</span>
            ))}
          </div>
          <div className="performance-footer">
            <span>
              <i /> Portfolio value{" "}
              <span className="muted">· fictional {period} snapshot</span>
            </span>
            <span className="muted">Example dataset</span>
          </div>
        </Panel>
        <Panel
          title="Your watchlist"
          extra={<TextLink to="/app/markets">View all</TextLink>}
        >
          <div className="watchlist-labels">
            <span>INSTRUMENT</span>
            <span>LAST PRICE / CHANGE</span>
          </div>
          {watchlist.slice(0, 4).map((symbol) => {
            const i = instruments.find((i) => i.symbol === symbol)!;
            return (
              <Link
                className="watchlist-row"
                key={symbol}
                to={`/app/markets?symbol=${symbol}`}
              >
                <span
                  className={`instrument-avatar ${i.symbol === "TCS" ? "purple" : ""}`}
                >
                  {symbol.slice(0, 2)}
                </span>
                <span className="symbol-name">
                  <b>{i.symbol}</b>
                  <small>
                    {i.exchange} · {i.sector}
                  </small>
                </span>
                <span className="quote">
                  <b>{money(i.price)}</b>
                  <Change value={i.change} />
                </span>
              </Link>
            );
          })}
          <Link className="add-watchlist" to="/app/markets">
            <Plus size={14} /> Add instrument
          </Link>
        </Panel>
      </div>
      <div className="dashboard-secondary">
        <Panel
          title="Open positions"
          extra={<TextLink to="/app/positions">View positions</TextLink>}
        >
          {scenario === "empty" || openPositions.length === 0 ? (
            <Empty />
          ) : (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>INSTRUMENT</th>
                    <th>QTY.</th>
                    <th>AVG. PRICE</th>
                    <th>LTP</th>
                    <th>P&L</th>
                    <th>MODE</th>
                  </tr>
                </thead>
                <tbody>
                  {openPositions.map((position) => (
                    <tr key={`${position.exchange}:${position.symbol}:${position.product}`}>
                      <td><Link to={`/app/markets?symbol=${position.symbol}`}><b>{position.symbol}</b></Link><small>{position.exchange} · {position.product}</small></td>
                      <td>{position.quantity}</td><td>{money(position.average)}</td><td>{money(position.price)}</td>
                      <td className={position.pnl >= 0 ? "positive" : "negative"}>{money(position.pnl)}</td>
                      <td><Badge tone="amber">Paper</Badge></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="table-total">
            <span>Paper positions / unrealized P&L</span>
            <b>{money(positions.reduce((total, position) => total + position.pnl, 0))}</b>
          </div>
        </Panel>
        <Panel
          title="Strategy overview"
          extra={<TextLink to="/app/strategies">Manage</TextLink>}
        >
          <div className="strategy-overview">
            <div className="strategy-stat">
              <strong>{active}</strong>
              <span>
                active configurations<small>No execution engine connected</small>
              </span>
              <Zap size={24} />
            </div>
            {strategies.slice(0, 3).map((s) => (
              <Link
                className="strategy-mini"
                to={`/app/strategies/${s.id}`}
                key={s.id}
              >
                <span className="strategy-mini-icon">
                  <Zap size={15} />
                </span>
                <span>
                  <b>{s.name}</b>
                  <small>
                    {s.signal} · {s.symbol}
                  </small>
                </span>
                <Badge
                  tone={
                    s.status === "Active"
                      ? "green"
                      : s.status === "Paused"
                        ? "amber"
                        : "neutral"
                  }
                >
                  {s.status}
                </Badge>
              </Link>
            ))}
          </div>
        </Panel>
      </div>
      <div className="dashboard-bottom">
        <Panel
          title="Recent activity"
          extra={<span className="muted text-xs">This session</span>}
        >
          <div className="activity-list">
            {activity.slice(0, 3).map((a, idx) => (
              <div className="activity-row" key={idx}>
                <span className="activity-icon">
                  {idx === 0 ? <ArrowDownLeft size={15} /> : <Zap size={15} />}
                </span>
                <span>
                  <b>{a}</b>
                  <small>Paper simulation · Workspace event</small>
                </span>
                <span className="muted text-xs">Just now</span>
              </div>
            ))}
          </div>
        </Panel>
        <div className="next-step">
          <span className="next-icon">
            <Zap size={22} />
          </span>
          <div className="eyebrow">PUT YOUR NEXT IDEA TO WORK</div>
          <h2>A strategy starts with a spark.</h2>
          <p>Build it. Validate it. Test it in paper mode.</p>
          <Link to="/app/strategies/new">
            Create a strategy <ArrowRight size={15} />
          </Link>
        </div>
      </div>
    </>
  );
}
function ShieldIcon() {
  return <span className="notice-icon">◇</span>;
}
