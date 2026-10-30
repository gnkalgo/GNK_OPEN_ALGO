import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, LockKeyhole, ShieldCheck, SlidersHorizontal } from "lucide-react";
import { serverMode, money } from "../api/paper";
import { controls, type RiskPolicy, type PlatformStatus } from "../api/server";
import { Badge, PageHead, Panel } from "../components/ui";

export default function ControlCenter() {
  const [policy, setPolicy] = useState<RiskPolicy | null>(null);
  const [platform, setPlatform] = useState<PlatformStatus | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(serverMode);
  async function load() {
    setLoading(true);
    setError("");
    setMessage("");
    try {
      const [risk, status] = await Promise.all([controls.policy(), controls.platform()]);
      setPolicy(risk);
      setPlatform(status);
    } catch {
      setPolicy(null);
      setPlatform(null);
      setError("Account controls could not be loaded. Reconnect and retry.");
    } finally { setLoading(false); }
  }
  useEffect(() => { if (serverMode) void load(); }, []);
  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!policy || busy) return;
    const data = new FormData(event.currentTarget);
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await controls.save({
        max_order_value: String(data.get("order")),
        max_daily_value: String(data.get("daily")),
        max_quantity: Number(data.get("quantity")),
        halted: data.get("halted") === "on",
      });
      setPolicy(result);
      setMessage("Account limits saved. New paper orders will use these limits.");
    } catch {
      setPolicy(null);
      setError("Limits could not be saved. Reload account controls before trying again.");
    } finally { setBusy(false); }
  }
  return <>
    <PageHead eyebrow="ACCOUNT GOVERNANCE" title="Control center"
      subtitle="Set your boundaries. Know what is connected. Stay in control.">
      <Link className="button" to="/app/brokers">Broker connections <ArrowRight size={15}/></Link>
    </PageHead>
    <section className="control-hero" aria-label="Execution status">
      <div className="control-emblem"><ShieldCheck size={32}/></div>
      <div><div className="eyebrow">GNK ALGO / EXECUTION BOUNDARY</div>
        <h2>Your account. Your limits.</h2>
        <p>{platform?.live_orders_enabled ? "Your validated Dhan live session is active. Live orders use separate risk caps and a real broker ledger." : platform?.paper_trading_enabled === false ? "Paper trading is disabled. Review broker connections to resolve live blockers and confirm a Dhan live session." : "Dhan live trading requires a validated session and approved server configuration."}</p>
      </div><Badge tone={platform?.live_orders_enabled ? "red" : "amber"}>{platform?.live_orders_enabled ? "Dhan live session active" : "Live execution locked"}</Badge>
    </section>
    {!serverMode && <div className="banner warning" role="status">Demo preview. Persisted account controls require a GNK server session. No risk limits are changed here.</div>}
    {loading && <p role="status">Loading account controls…</p>}
    {error && <div className="banner warning" role="alert">{error} <button className="button" onClick={() => void load()} disabled={busy || loading}>Reload controls</button></div>}
    {message && <p className="banner" role="status">{message}</p>}
    <div className="control-grid">
      <Panel title="Paper account limits" extra={<SlidersHorizontal size={17}/>}>
        <form className="control-form" onSubmit={save} key={JSON.stringify(policy)}>
          <p>Limits apply to your account on the server. Buys and sells both count toward daily gross turnover.</p>
          <fieldset disabled={!policy || busy || loading}>
            <label>Maximum order value (INR)<input name="order" type="number" min="0.01" max="1000000" step="0.01" required defaultValue={policy?.max_order_value ?? "1000000.00"}/></label>
            <label>Daily gross turnover limit (INR)<input name="daily" type="number" min="0.01" max="5000000" step="0.01" required defaultValue={policy?.max_daily_value ?? "5000000.00"}/></label>
            <label>Maximum units per order<input name="quantity" type="number" min="1" max="1000" step="1" required defaultValue={policy?.max_quantity ?? 1000}/></label>
            <label className="control-check"><input name="halted" type="checkbox" defaultChecked={policy?.halted ?? false}/> Halt new paper orders</label>
            <button className="button primary" type="submit">{busy ? "Saving…" : "Save account limits"}</button>
          </fieldset>
          {policy && <p>Used today: <b>{money(Number(policy.daily_value_used))}</b> · Resets at midnight India time.</p>}
          {policy?.emergency_stop && <p role="alert">A live-trading emergency stop is active. Only an administrator can clear it. Paper limits are separate.</p>}
          <small>Halting blocks new orders. It does not cancel orders or close positions. Limits here apply to paper trading only.</small>
        </form>
      </Panel>
      <Panel title="Execution capabilities" extra={<LockKeyhole size={17}/>}>
        <div className="capability-list">
          {(platform?.capabilities ?? [
            {name: "Paper workspace", status: serverMode ? "unverified" : "demo"},
            {name: "Account risk limits", status: "server_required"},
            {name: "Live market data", status: "unavailable"},
            {name: "Live broker execution", status: "unavailable"},
          ]).map(item => <div className="capability-row" key={item.name}>
            <span>{item.name}</span><Badge tone={item.status === "available" ? "green" : "amber"}>{item.status.replaceAll("_", " ")}</Badge>
          </div>)}
        </div>
        <div className="control-note"><h3>Account linking is the first step</h3><p>Linking a broker identifies an account. It does not enable live orders, grant market data rights, or certify a strategy.</p><Link className="text-link" to="/app/brokers">Review your connections →</Link></div>
      </Panel>
    </div>
    <section className="control-next"><div><h2>Prepare. Review. Execute with evidence.</h2><p>Define a strategy, test the paper workflow, and review every order outcome before moving forward.</p></div><Link className="button" to="/app/strategies">Open strategies <ArrowRight size={15}/></Link></section>
  </>;
}
