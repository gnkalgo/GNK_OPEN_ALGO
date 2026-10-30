import { useEffect, useState } from "react";
import { AlertTriangle, RefreshCw, Shield } from "lucide-react";
import { Link } from "react-router-dom";
import { paper, serverMode, money } from "../api/paper";
import type { LiveTradingStatus } from "../api/server";
import { Badge, Modal, Panel } from "./ui";

function stateLabel(status: LiveTradingStatus["session_status"]) {
  return status === "PENDING_CONFIRMATION" ? "Pending confirmation" : status.charAt(0) + status.slice(1).toLowerCase();
}
const blockerLabels: Record<string,string> = {
  DHAN_LIVE_DISABLED: "The server operator has not enabled Dhan live execution.",
  DHAN_DEPLOYMENT_APPROVAL_REQUIRED: "The deployment approval is outstanding.",
  DHAN_INSTRUMENT_REFRESH_REQUIRED: "Today's approved Dhan instruments must be refreshed.",
  DHAN_EXECUTION_IP_REQUIRED: "The server execution IP must be configured.",
  DHAN_ACCOUNT_NOT_APPROVED: "This Dhan account is not on the approved pilot list.",
  DHAN_RECONNECT_REQUIRED: "Reconnect Dhan to refresh the account identity and token.",
  EMERGENCY_STOP_ACTIVE: "The account emergency stop is active.",
  DHAN_REVALIDATION_REQUIRED: "Dhan account validation failed; check connectivity and reconnect if needed.",
};
export function LiveTradingPanel() {
  const [status, setStatus] = useState<LiveTradingStatus|null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [confirming, setConfirming] = useState(false);
  async function refreshStatus(clearError=true) {
    try {
      setStatus(await paper.liveTradingStatus());
      if (clearError) setError("");
    } catch (reason) {
      setStatus(null);
      setError(reason instanceof Error ? reason.message : "Could not refresh trading status.");
    }
  }
  useEffect(() => { void refreshStatus(); }, []);
  async function run(action:()=>Promise<unknown>) {
    if (busy) return;
    setBusy(true);setError("");
    let failure="";
    try { await action(); }
    catch (reason) { failure=reason instanceof Error ? reason.message : "Trading request failed."; }
    finally { await refreshStatus(false);window.dispatchEvent(new Event("gnk-trading-status-changed"));setBusy(false);if (failure) setError(failure); }
  }
  const session = status?.session;
  const active = serverMode && !!status?.live_orders_enabled;
  const paperEnabled = !serverMode || status?.paper_trading_enabled !== false;
  const ready = serverMode && !!status?.live_available;
  const linked = status?.brokers.some(item => item.code === "dhan");
  const terminal = !session || session.status === "EXPIRED" || session.status === "REVOKED";
  return <>
    <Panel title="Trading mode" className="live-trading-panel" extra={<Badge tone={active ? "red" : "amber"}>{active ? "Dhan live session active" : !status ? "Checking trading status" : paperEnabled ? "Paper trading" : "Trading inactive"}</Badge>}>
      <div className="trading-mode-switch" aria-label="Trading mode">
        <button type="button" aria-pressed={!active && paperEnabled} disabled={!paperEnabled || !active || busy} onClick={() => void run(() => paper.setTradingMode("PAPER"))}>{paperEnabled ? "Paper Trading" : "Paper trading disabled"}</button>
        <button type="button" aria-pressed={active} disabled={!ready || active || busy}
          onClick={() => { if (terminal) void run(() => paper.createLiveSession("dhan")); else setConfirming(true); }}>
          {ready ? "Dhan Live Trading" : "Live Trading unavailable"}
        </button>
      </div>
      <p className="live-mode-explanation">Dhan live trading supports reviewed NSE equity delivery BUY LIMIT orders. {paperEnabled ? "Paper orders stay in their separate simulator." : "Paper order submission is disabled on this server."}</p>
      <div className="live-safety-notice" role="note"><AlertTriangle size={18}/><span><b>Account authentication is not trading authorization.</b> {active ? "Dhan identity and registered execution IP passed the last validation. Every order is checked again before dispatch." : "This session does not validate live trading permissions until the server activation checks pass."}</span></div>
      <div className="live-session-details">
        <div><span>Live session</span><b>{stateLabel(status?.session_status ?? "INACTIVE")}</b></div>
        <div><span>Broker account</span><b>{session?.broker_account_mask ?? status?.brokers.find(item => item.code === "dhan")?.account_mask ?? "Not linked"}</b></div>
        <div><span>Broker authentication</span><b>{status?.broker_auth_valid ? "Verified at last check" : "Not verified"}</b></div>
        <div><span>Live order / daily cap</span><b>{status?.risk_limits ? `${money(Number(status.risk_limits.max_order_value))} / ${money(Number(status.risk_limits.max_daily_value))}` : "Unavailable; live mode blocked"}</b></div>
        <div><span>Session condition</span><b>{session?.suspension_reason ?? (active ? "Validated" : "Awaiting validation")}</b></div>
        <div><span>Session start</span><b>{session ? new Date(session.created_at).toLocaleString() : "-"}</b></div>
        <div><span>Expiry / last validation</span><b>{session ? new Date(session.expires_at).toLocaleString() : "-"} / {session?.last_validated_at ? new Date(session.last_validated_at).toLocaleString() : "Not checked"}</b></div>
      </div>
      {!!status?.blockers.length && <ul className="live-blockers">{status.blockers.map(code => <li key={code}>{blockerLabels[code] ?? code.replaceAll("_", " ")}</li>)}</ul>}
      {error && <div className="banner warning" role="alert">{error}</div>}
      <div className="live-session-actions">
        <button className="button" disabled={busy} onClick={() => void refreshStatus()}><RefreshCw size={14}/> Refresh status</button>
        {!linked && <Link className="button" to="/app/brokers">Link a Dhan account</Link>}
        {terminal && linked && <button className="button primary" disabled={busy || !ready} onClick={() => void run(() => paper.createLiveSession("dhan"))}>Request Dhan live session</button>}
        {session?.status === "PENDING_CONFIRMATION" && <button className="button primary" disabled={busy || !ready} onClick={() => setConfirming(true)}>Confirm Live Trading</button>}
        {session?.status === "SUSPENDED" && <button className="button" disabled={busy || !ready} onClick={() => setConfirming(true)}>Review and resume session</button>}
        {active && <><Link className="button danger" to="/app/live">Open Dhan live order desk</Link><button className="button" disabled={busy} onClick={() => void run(() => paper.suspendLiveSession(session!.id))}>Suspend Live Trading</button></>}
        {!terminal && session && <button className="button danger" disabled={busy} onClick={() => void run(() => paper.endLiveSession(session.id))}>End Live Session</button>}
      </div>
      <div className="emergency-stop-row"><span><Shield size={16}/> Emergency Stop: <b>{status?.emergency_stop ? "ACTIVE" : "Not active"}</b></span><button className="button danger" disabled={busy || !status || status.emergency_stop} onClick={() => void run(() => paper.activateEmergencyStop())}>Activate Emergency Stop</button></div>
      <p className="live-admin-note">Stopping or ending a session blocks new GNK live submissions. It does not cancel broker orders or close positions. Clear a live emergency stop through an administrator, then explicitly resume.</p>
      <div className="live-execution-lock"><Link to="/app/live">Review the separate Dhan order ledger</Link>. Use Dhan's own terminal to sell, modify or cancel orders during this limited pilot.</div>
    </Panel>
    {confirming && session && <Modal title="Confirm live trading" close={() => {if (!busy) setConfirming(false);}}><div className="live-confirmation">
      <p>You are enabling LIVE TRADING for {session.broker_account_mask}. Confirmed orders can execute in your real Dhan account and cause financial losses.</p>
      <p>Scope: NSE equity delivery BUY LIMIT orders only. Review the live risk caps above. Session activation does not place an order.</p>
      <div className="live-session-actions"><button className="button" disabled={busy} onClick={() => setConfirming(false)}>Cancel</button><button className="button danger" disabled={busy} onClick={() => {setConfirming(false);void run(() => session.status === "SUSPENDED" ? paper.resumeLiveSession(session.id) : paper.confirmLiveSession(session.id));}}>I understand - activate Dhan session</button></div>
    </div></Modal>}
  </>;
}
