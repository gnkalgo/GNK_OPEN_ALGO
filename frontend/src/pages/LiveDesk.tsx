import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { serverMode, money, paper } from "../api/paper";
import { ApiError, dhan, type DhanInstrument, type DhanOrder, type DhanPreview, type LiveTradingStatus } from "../api/server";
import { Badge, Modal, PageHead, Panel } from "../components/ui";

export default function LiveDesk() {
  const [status,setStatus] = useState<LiveTradingStatus|null>(null);
  const [instruments,setInstruments] = useState<DhanInstrument[]>([]);
  const [orders,setOrders] = useState<DhanOrder[]>([]);
  const [security,setSecurity] = useState("");
  const [quantity,setQuantity] = useState(1);
  const [price,setPrice] = useState("");
  const [preview,setPreview] = useState<DhanPreview|null>(null);
  const [acknowledged,setAcknowledged] = useState(false);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState("");
  const [uncertain,setUncertain] = useState(false);
  const submitting = useRef(false);
  const key = useRef(crypto.randomUUID());
  async function refresh() {
    try {
      const [mode,catalog,ledger] = await Promise.all([paper.liveTradingStatus(),dhan.instruments(),dhan.orders()]);
      setStatus(mode);setInstruments(catalog.instruments);setOrders(ledger.orders);
    } catch (reason) {
      setStatus(null);
      setError(reason instanceof Error ? reason.message : "Could not load the Dhan live desk.");
    }
  }
  useEffect(() => { if (serverMode) void refresh(); }, []);
  const item = instruments.find(value => value.security_id === security);
  const blocked = orders.some(order => !["TRADED","CANCELLED","REJECTED","EXPIRED","BLOCKED"].includes(order.status));
  const ready = serverMode && !!status?.live_orders_enabled && !blocked && !uncertain;
  async function review(event:React.FormEvent) {
    event.preventDefault();
    if (!status?.session || !ready || busy) return;
    if (!navigator.onLine) {setError("You are offline. No request was sent.");return;}
    setBusy(true);setError("");
    try {
      const result = await dhan.preview({session_id:status.session.id,security_id:security,quantity,price});
      key.current = crypto.randomUUID();setAcknowledged(false);setPreview(result);
    } catch (reason) {setError(reason instanceof Error ? reason.message : "Live preview failed.");}
    finally {setBusy(false);}
  }
  async function confirm() {
    if (!preview || !acknowledged || submitting.current) return;
    if (!navigator.onLine) {setError("You are offline. No request was sent.");return;}
    submitting.current = true;setBusy(true);setError("");
    try {
      const result = await dhan.submit(preview.preview_token,key.current);
      setOrders(current => [result,...current.filter(order => order.id !== result.id)]);
      setUncertain(false);setPreview(null);
      await refresh();
    } catch (reason) {
      const definitive = reason instanceof ApiError && [400,401,403,404,409,422].includes(reason.status);
      setUncertain(!definitive);
      if (definitive) setPreview(null);
      setError(definitive ? reason.message : "Submission could not be confirmed. Retry the same request below or review the live ledger. Do not create another order.");
    } finally {submitting.current=false;setBusy(false);}
  }
  async function reconcile(id:string) {
    if (busy) return;
    setBusy(true);setError("");
    try { const result=await dhan.reconcile(id);setOrders(current => current.map(order => order.id === id ? result : order));await refresh(); }
    catch(reason) {setError(reason instanceof Error ? reason.message : "Reconciliation could not be completed.");}
    finally {setBusy(false);}
  }
  return <>
    <PageHead eyebrow="REAL BROKER EXECUTION" title="Dhan live order desk" subtitle="A separate ledger for real NSE equity delivery limit buys.">
      <Link className="button" to="/app/dashboard">Manage live session</Link>
      <button className="button" disabled={!serverMode || busy} onClick={() => void refresh()}>Refresh live ledger</button>
    </PageHead>
    <div className="banner warning" role="note">Confirmed orders use real Dhan funds. This pilot supports BUY / CNC / LIMIT / DAY only. Sell, modify and cancel through Dhan's own terminal. Session stop does not cancel orders or close positions.</div>
    {!serverMode && <p role="status">Live execution requires an authenticated GNK server session. The browser demo cannot activate or submit live trades.</p>}
    {error && <div className="banner warning" role="alert">{error}</div>}
    <div className="control-grid">
      <Panel title="Dhan delivery buy" extra={<Badge tone={ready ? "red" : "amber"}>{ready ? "Live session active" : "Live submission locked"}</Badge>}>
        <form className="control-form" onSubmit={review}>
          <fieldset disabled={!ready || busy}>
            <label>Approved Dhan equity<select aria-label="Approved Dhan equity" required value={security} onChange={event => {setSecurity(event.target.value);setPrice("");}}>
              <option value="">Select an approved equity</option>{instruments.map(value => <option key={value.security_id} value={value.security_id}>{value.name} / NSE / {value.security_id}</option>)}
            </select></label>
            <label>Live quantity<input type="number" required min="1" max={status?.risk_limits?.max_quantity ?? 1} step="1" value={quantity} onChange={event => setQuantity(Number(event.target.value))}/></label>
            <label>Live limit price (INR)<input type="number" required min={item?.lower_limit ?? "0.01"} max={item?.upper_limit} step={item?.tick_size ?? "0.01"} value={price} onChange={event => setPrice(event.target.value)}/></label>
            <p>Price is entered by you. No paper quote or fixture price is used. {item && <>Instrument price band: {money(Number(item.lower_limit))} to {money(Number(item.upper_limit))}; tick {money(Number(item.tick_size))}.</>}</p>
            <button className="button danger" type="submit">Review live BUY LIMIT order</button>
          </fieldset>
          {!ready && <p>Activate a validated Dhan session on the dashboard and reconcile any outstanding order before creating another.</p>}
        </form>
      </Panel>
      <Panel title="Execution boundaries"><div className="control-note">
        <h3>Review every real order</h3><p>Both preview and submission recheck account identity, static IP registration, session authority, instrument metadata, margin and available funds.</p>
        <p>Only one unresolved or pending GNK live order is allowed for a Dhan account. Broker acknowledgement is not a fill. Use reconciliation to read cumulative fills.</p>
        <p>Configured order cap: {status?.risk_limits ? money(Number(status.risk_limits.max_order_value)) : "Not available"}. Daily gross cap: {status?.risk_limits ? money(Number(status.risk_limits.max_daily_value)) : "Not available"}.</p>
        <p>GNK accepts orders on weekdays 09:15-15:20 India time. Dhan remains authoritative for holidays and exchange restrictions.</p>
      </div></Panel>
    </div>
    <Panel title="Your Dhan live orders" extra={<Badge tone="red">Real account ledger</Badge>}>
      {!orders.length ? <div className="control-note">No GNK Dhan live orders recorded for this user.</div> : <div className="table-scroll"><table><thead><tr><th>INSTRUMENT</th><th>ORDER</th><th>STATUS</th><th>FILLED</th><th>AVG. FILL</th><th>ACTION</th></tr></thead><tbody>{orders.map(order => <tr key={order.id}>
        <td><b>{order.name}</b><small>NSE / {order.security_id}</small></td><td>BUY {order.quantity} at {money(Number(order.price))}<small>{order.broker_order_id ?? "Broker ID not confirmed"}</small></td>
        <td><Badge tone={order.status === "UNKNOWN" ? "red" : "amber"}>{order.status}</Badge>{order.reason && <small>{order.reason}</small>}</td><td>{order.filled_quantity} / {order.quantity}</td><td>{money(Number(order.average_price))}</td>
        <td><button className="button" disabled={busy || order.status === "BLOCKED"} onClick={() => void reconcile(order.id)}>Reconcile broker status</button></td>
      </tr>)}</tbody></table></div>}
    </Panel>
    {preview && <Modal title="Confirm real Dhan order" close={() => {if (!busy && !uncertain) setPreview(null);}}><div className="live-confirmation">
      <Badge tone="red">REAL MONEY / BUY LIMIT</Badge><h3>{preview.ticket.name}</h3>
      <p>Dhan account ending {preview.account_mask}: BUY {preview.ticket.quantity} units at {money(Number(preview.ticket.price))}, delivery CNC, NSE, DAY.</p>
      <p>Order notional: <b>{money(preview.ticket.quantity * Number(preview.ticket.price))}</b>. Margin estimate: {money(Number(preview.margin.required_margin))}. Brokerage estimate: {money(Number(preview.margin.brokerage_estimate))}. Other taxes and charges may apply.</p>
      <label className="control-check"><input type="checkbox" checked={acknowledged} onChange={event => setAcknowledged(event.target.checked)}/> I confirm this real Dhan BUY LIMIT order and understand that it can cause financial losses.</label>
      <p>Preview expires in 90 seconds. The server checks again before dispatch.</p>
      {uncertain && <p role="alert">A response was lost. Retry uses the original request key; it cannot create a duplicate GNK intent.</p>}
      <div className="live-session-actions"><button className="button" disabled={busy || uncertain} onClick={() => setPreview(null)}>Cancel review</button><button className="button danger" disabled={busy || !acknowledged} onClick={() => void confirm()}>{busy ? "Checking broker..." : uncertain ? "Retry the same live request" : "Confirm real BUY LIMIT order"}</button></div>
    </div></Modal>}
  </>;
}
