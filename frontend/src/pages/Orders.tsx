import { ledger } from "../api/ledger";
import { useRef, useState } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Plus,
  ShieldCheck,
} from "lucide-react";
import {
  instruments,
  money,
  paper,
  serverMode,
  validateTicket,
  type Ticket,
} from "../api/paper";
import { useAction, usePaper, useTradingStatus } from "../hooks";
import {
  Badge,
  Empty,
  Feedback,
  Modal,
  PageHead,
  Panel,
} from "../components/ui";
export function OrderEntry() {
  const trading = useTradingStatus();
  const [params] = useSearchParams(),
    navigate = useNavigate(),
    a = useAction(),
    { broker, scenario } = usePaper();
  const first =
    instruments.find((i) => i.symbol === params.get("symbol")) ??
    instruments[0];
  const [ticket, setTicket] = useState<Ticket>({
    symbol: first.symbol,
    exchange: first.exchange,
    product: "Delivery",
    side: "BUY",
    quantity: 1,
    type: "MARKET",
    price: first.price,
  });
  const [review, setReview] = useState(false),
    key = useRef(crypto.randomUUID()),
    submitting = useRef(false);
  const set = <K extends keyof Ticket>(k: K, v: Ticket[K]) => {
    setTicket((t) => ({ ...t, [k]: v }));
    a.setError("");
  };
  const price =
    ticket.type === "MARKET"
      ? instruments.find((i) => i.symbol === ticket.symbol)!.price
      : ticket.price;
  async function submit() {
    if (submitting.current) return;
    submitting.current = true;
    await a.run(async () => {
      await paper.submit(ticket, key.current);
      navigate("/app/orders");
    });
    submitting.current = false;
  }
  if (serverMode && !trading) return <p role="status">Checking trading availability…</p>;
  if (serverMode && trading?.paper_trading_enabled === false) return <Navigate to="/app/live" replace />;
  return (
    <>
      <PageHead
        eyebrow="PLAN YOUR EXECUTION"
        title="New paper order"
        subtitle="Define your trade. Review the details. Stay in control."
      >
        <Link className="button" to="/app/markets">
          <ArrowLeft size={15} /> Back to markets
        </Link>
      </PageHead>
      <div className="two-column">
        <Panel
          title="Order ticket"
          extra={<Badge tone="amber">Paper only</Badge>}
        >
          <form
            className="form-grid"
            onSubmit={(e) => {
              e.preventDefault();
              const error = validateTicket(ticket);
              if (error) a.setError(error);
              else setReview(true);
            }}
          >
            <div className="side-toggle">
              <button
                type="button"
                className={ticket.side === "BUY" ? "buy selected" : ""}
                onClick={() => set("side", "BUY")}
              >
                Buy
              </button>
              <button
                type="button"
                className={ticket.side === "SELL" ? "sell selected" : ""}
                onClick={() => set("side", "SELL")}
              >
                Sell
              </button>
            </div>
            <label className="span-2">
              Instrument
              <select
                value={ticket.symbol}
                onChange={(e) => {
                  const i = instruments.find(
                    (i) => i.symbol === e.target.value,
                  )!;
                  setTicket({
                    ...ticket,
                    symbol: i.symbol,
                    exchange: i.exchange,
                    price: i.price,
                  });
                }}
              >
                {instruments.map((i) => (
                  <option key={i.symbol} value={i.symbol}>
                    {i.symbol} — {i.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Exchange
              <select
                value={ticket.exchange}
                onChange={(e) => set("exchange", e.target.value)}
              >
                <option>NSE</option>
                <option>BSE</option>
              </select>
            </label>
            <label>
              Product
              <select
                value={ticket.product}
                onChange={(e) => set("product", e.target.value)}
              >
                <option>Delivery</option>
                <option>Intraday</option>
              </select>
            </label>
            <label>
              Quantity
              <input
                type="number"
                required
                min={1}
                max={1000}
                step={1}
                value={ticket.quantity || ""}
                onChange={(e) => set("quantity", Number(e.target.value))}
              />
            </label>
            <label>
              Order type
              <select
                value={ticket.type}
                onChange={(e) => set("type", e.target.value as Ticket["type"])}
              >
                <option value="MARKET">Market</option>
                <option value="LIMIT">Limit</option>
              </select>
            </label>
            <label className="span-2">
              Price (INR)
              <input
                type="number"
                required
                min={0.05}
                step="0.05"
                disabled={ticket.type === "MARKET"}
                value={ticket.type === "MARKET" ? price : ticket.price || ""}
                onChange={(e) => set("price", Number(e.target.value))}
              />
              <small>
                Market: simulated quote. Limit: immediate fictional fill at your
                price.
              </small>
            </label>
            <div className="span-2">
              {!review && <Feedback {...a} />}
              {broker !== "Connected" && (
                <div className="banner warning">
                  A paper broker connection is required.{" "}
                  <Link to="/app/brokers">Connect broker →</Link>
                </div>
              )}
              <button
                className="button primary full"
                disabled={broker !== "Connected" || scenario === "feed-offline"}
              >
                Review paper order <ArrowRight size={16} />
              </button>
            </div>
          </form>
        </Panel>
        <Panel title="Estimated order value">
          <div className="order-summary">
            <span className="muted">
              {ticket.side} · {ticket.symbol}
            </span>
            <strong>{money((price || 0) * ticket.quantity)}</strong>
            <dl>
              <div>
                <dt>Order mode</dt>
                <dd>Paper simulation</dd>
              </div>
              <div>
                <dt>Execution</dt>
                <dd>{ticket.type}</dd>
              </div>
              <div>
                <dt>Quantity</dt>
                <dd>{ticket.quantity} shares</dd>
              </div>
              <div>
                <dt>Product</dt>
                <dd>{ticket.product}</dd>
              </div>
            </dl>
            <div className="banner">
              <ShieldCheck size={20} /> No real orders will be placed. Fees,
              slippage, partial fills, exchange rules and settlement are not
              modeled.
            </div>
          </div>
        </Panel>
      </div>
      {review && (
        <Modal
          title="Review paper order"
          close={() => {
            if (!a.busy) setReview(false);
          }}
        >
          <div className="modal-content">
            <Badge tone="amber">Paper trading confirmation</Badge>
            <h3>
              {ticket.side} {ticket.quantity} × {ticket.symbol}
            </h3>
            <p>
              {ticket.exchange} · {ticket.product} · {ticket.type} ·{" "}
              {money(price)} per share
            </p>
            <div className="review-total">
              <span>Estimated value</span>
              <b>{money(price * ticket.quantity)}</b>
            </div>
            <p className="muted">
              This submits one simulated order. Unknown outcomes must be
              reconciled in the order book before placing another order.
            </p>
            <Feedback {...a} />
            <button
              className="button primary full"
              disabled={a.busy}
              onClick={() => void submit()}
            >
              {a.busy ? "Submitting…" : "Confirm paper order"}
              <CheckCircle2 size={16} />
            </button>
            <button
              className="button full"
              disabled={a.busy}
              onClick={() => setReview(false)}
            >
              Edit order
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
export function Books({
  view,
}: {
  view: "orders" | "trades" | "positions" | "portfolio";
}) {
  const { orders, scenario } = usePaper(),
    a = useAction(),
    [filter, setFilter] = useState("All");
  const titles = {
    orders: "Order book",
    trades: "Trade book",
    positions: "Positions",
    portfolio: "Portfolio",
  };
  const filled = orders.filter((o) => o.status === "Filled");
  const list =
    scenario === "empty"
      ? []
      : view === "orders"
        ? orders.filter((o) => filter === "All" || o.status === filter)
        : filled;
  const grouped = ledger(orders, instruments).filter(item => item.quantity !== 0);
  const isPositions = view === "positions" || view === "portfolio";
  return (
    <>
      <PageHead
        eyebrow="A CLEAR RECORD OF YOUR ACTIVITY"
        title={titles[view]}
        subtitle={
          isPositions
            ? "Positions generated by your submitted paper orders."
            : "Review execution and status across your paper trading session."
        }
      >
        <Link className="button primary" to="/app/orders/new">
          <Plus size={16} /> New paper order
        </Link>
      </PageHead>
      <div className="mini-stats">
        <div>
          <span>Paper orders</span>
          <b>{orders.length}</b>
        </div>
        <div>
          <span>Filled</span>
          <b className="positive">{filled.length}</b>
        </div>
        <div>
          <span>Rejected</span>
          <b className="negative">
            {orders.filter((o) => o.status === "Rejected").length}
          </b>
        </div>
        <div>
          <span>Unresolved</span>
          <b>{orders.filter((o) => o.status === "Unknown").length}</b>
        </div>
      </div>
      <Feedback {...a} />
      <Panel
        title={isPositions ? "Your paper holdings" : "Session activity"}
        extra={<Badge>Fictional ledger</Badge>}
      >
        {view === "orders" && (
          <div className="tabs padded">
            {["All", "Filled", "Rejected", "Unknown"].map((f) => (
              <button
                className={f === filter ? "active" : ""}
                key={f}
                onClick={() => setFilter(f)}
              >
                {f}
              </button>
            ))}
          </div>
        )}
        {(
          isPositions
            ? grouped.length === 0 || scenario === "empty"
            : list.length === 0
        ) ? (
          <Empty
            title={
              isPositions ? "No open paper positions" : "No paper activity yet"
            }
            detail="Start with an instrument, review your order, and submit it in paper mode."
          >
            <Link className="button" to="/app/markets">
              Explore markets →
            </Link>
          </Empty>
        ) : (
          <div className="table-scroll">
            <table>
              {isPositions ? (
                <>
                  <thead>
                    <tr>
                      <th>INSTRUMENT</th>
                      <th>NET QTY.</th>
                      <th>NET COST</th>
                      <th>MARK VALUE</th>
                      <th>MARK-TO-MARKET</th>
                    </tr>
                  </thead>
                  <tbody>
                    {grouped.map((p) => (
                      <tr key={`${p.exchange}:${p.symbol}:${p.product}`}>
                        <td>
                          <b>{p.symbol}</b>
                          <small>{p.exchange} · Paper</small>
                        </td>
                        <td>{p.quantity}</td>
                        <td>{money(p.netValue)}</td>
                        <td>{money(p.quantity * p.price)}</td>
                        <td className={p.pnl >= 0 ? "positive" : "negative"}>
                          {p.pnl >= 0 ? "+" : ""}
                          {money(p.pnl)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </>
              ) : (
                <>
                  <thead>
                    <tr>
                      <th>INSTRUMENT / ORDER ID</th>
                      <th>SIDE</th>
                      <th>QTY.</th>
                      <th>PRICE</th>
                      <th>STATUS</th>
                      <th>TIME</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {list.map((o) => (
                      <tr key={o.id}>
                        <td>
                          <b>{o.symbol}</b>
                          <small className="order-id">{o.id}</small>
                        </td>
                        <td>
                          <Badge tone={o.side === "BUY" ? "green" : "red"}>
                            {o.side}
                          </Badge>
                        </td>
                        <td>{o.quantity}</td>
                        <td>{money(o.price)}</td>
                        <td>
                          <Badge
                            tone={
                              o.status === "Filled"
                                ? "green"
                                : o.status === "Rejected"
                                  ? "red"
                                  : "amber"
                            }
                          >
                            {o.status}
                          </Badge>
                          {o.reason && (
                            <small className="negative">{o.reason}</small>
                          )}
                        </td>
                        <td>{o.time}</td>
                        <td>
                          {o.status === "Unknown" && (
                            <button
                              className="button"
                              disabled={a.busy}
                              onClick={() =>
                                void a.run(async () => {
                                  await paper.reconcile(o.id);
                                }, "Order reconciled. No duplicate was submitted.")
                              }
                            >
                              Reconcile status
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </>
              )}
            </table>
          </div>
        )}
      </Panel>
      <div className="banner">
        Paper ledger only. Position cost uses weighted average entry prices.
        Fees, settlement and margin are not modeled.{" "}
        {view === "orders" && <Link to="/app/trades">Review trade book →</Link>}
        {view === "trades" && (
          <Link to="/app/positions">Review positions →</Link>
        )}
      </div>
    </>
  );
}
