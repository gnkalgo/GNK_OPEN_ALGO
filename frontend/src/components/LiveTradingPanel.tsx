import { useEffect, useState } from "react";
import { AlertTriangle, Clock3, RefreshCw, Shield } from "lucide-react";
import { Link } from "react-router-dom";
import { paper, serverMode } from "../api/paper";
import type {
  BrokerCode,
  LiveTradingStatus,
} from "../api/server";
import { Badge, Modal, Panel } from "./ui";

const confirmationWarning =
  "You are enabling LIVE TRADING. Orders submitted through this session may execute in your real broker account and result in financial losses. Confirm the broker account, trading mode, and risk limits before proceeding.";

function stateLabel(status: LiveTradingStatus["session_status"]) {
  return status === "PENDING_CONFIRMATION"
    ? "Pending confirmation"
    : status.charAt(0) + status.slice(1).toLowerCase().replaceAll("_", " ");
}

export function LiveTradingPanel() {
  const [status, setStatus] = useState<LiveTradingStatus | null>(null);
  const [brokerCode, setBrokerCode] = useState<BrokerCode | "">("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [confirming, setConfirming] = useState(false);

  async function refreshStatus(clearError = true) {
    try {
      const current = await paper.liveTradingStatus();
      setStatus(current);
      if (!current.brokers.some((broker) => broker.code === brokerCode)) {
        setBrokerCode(current.brokers[0]?.code ?? "");
      }
      if (clearError) setError("");
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Could not refresh trading mode.",
      );
    }
  }

  useEffect(() => {
    void refreshStatus();
  }, []);

  async function run(action: () => Promise<unknown>) {
    if (busy) return;
    setBusy(true);
    setError("");
    let actionError = "";
    try {
      await action();
    } catch (reason) {
      actionError =
        reason instanceof Error ? reason.message : "Trading control request failed.";
    } finally {
      setBusy(false);
      await refreshStatus(false);
      if (actionError) setError(actionError);
    }
  }

  const session = status?.session;
  const linkedBroker = status?.brokers.find(
    (broker) => broker.code === (session?.broker_code ?? brokerCode),
  );
  const terminal = session?.status === "EXPIRED" || session?.status === "REVOKED";

  return (
    <>
      <Panel
        title="Trading mode"
        className="live-trading-panel"
        extra={<Badge tone="amber">Paper trading</Badge>}
      >
        <div className="trading-mode-switch" aria-label="Trading mode">
          <button type="button" aria-pressed="true" disabled>
            Paper Trading
          </button>
          <button type="button" aria-pressed="false" disabled>
            Live Trading unavailable
          </button>
        </div>
        <p className="live-mode-explanation">
          Paper execution remains enabled. Live order submission is disabled
          until verified broker execution, instrument mapping, order risk
          controls and reconciliation are implemented.
        </p>

        <div className="live-safety-notice" role="note">
          <AlertTriangle size={18} />
          <span>
            <b>Account authentication is not trading authorization.</b> This
            deployment does not validate live trading permissions or expose
            broker order submission. A linked account is not proof that
            connectivity or trading permissions are valid.
          </span>
        </div>

        <div className="live-session-details">
          <div>
            <span>Live session</span>
            <b>{stateLabel(status?.session_status ?? "INACTIVE")}</b>
          </div>
          <div>
            <span>Broker account</span>
            <b>{session?.broker_account_mask ?? linkedBroker?.account_mask ?? "Not linked"}</b>
          </div>
          <div>
            <span>Broker authentication</span>
            <b>Not verified</b>
          </div>
          <div>
            <span>Risk limits</span>
            <b>Unavailable; live mode blocked</b>
          </div>
          <div>
            <span>Session condition</span>
            <b>{session?.suspension_reason ?? "No broker validation"}</b>
          </div>
          <div>
            <span>Session start</span>
            <b>{session ? new Date(session.created_at).toLocaleString() : "—"}</b>
          </div>
          <div>
            <span>Expiry / last validation</span>
            <b>
              {session ? new Date(session.expires_at).toLocaleString() : "—"}
              {" / "}
              {session?.last_validated_at
                ? new Date(session.last_validated_at).toLocaleString()
                : "Not checked"}
            </b>
          </div>
        </div>

        {error && (
          <div className="banner warning" role="alert">
            {error}
          </div>
        )}

        <div className="live-session-actions">
          <button
            className="button"
            type="button"
            onClick={() => void refreshStatus()}
            disabled={busy}
          >
            <RefreshCw size={14} /> Refresh status
          </button>
          {!session || terminal ? (
            <div className="live-start-actions">
              <label>
                Linked broker
                <select
                  aria-label="Linked broker"
                  value={brokerCode}
                  onChange={(event) =>
                    setBrokerCode(event.target.value as BrokerCode | "")
                  }
                  disabled={!status?.brokers.length || busy}
                >
                  {!status?.brokers.length && <option value="">No broker linked</option>}
                  {status?.brokers.map((broker) => (
                    <option key={broker.code} value={broker.code}>
                      {broker.name} · {broker.account_mask}
                    </option>
                  ))}
                </select>
              </label>
              {status?.brokers.length ? (
                <button
                  className="button primary"
                  type="button"
                  onClick={() =>
                    brokerCode &&
                    void run(() => paper.createLiveSession(brokerCode))
                  }
                  disabled={busy || !brokerCode}
                >
                  Enable Live Mode
                </button>
              ) : (
                <Link className="button" to="/app/brokers">
                  Link a broker account
                </Link>
              )}
            </div>
          ) : (
            <div className="live-start-actions">
              {session.status === "PENDING_CONFIRMATION" && (
                <button
                  className="button primary"
                  type="button"
                  onClick={() => setConfirming(true)}
                  disabled={busy}
                >
                  Confirm Live Trading
                </button>
              )}
              {session.status === "SUSPENDED" && (
                <button
                  className="button"
                  type="button"
                  onClick={() => void run(() => paper.resumeLiveSession(session.id))}
                  disabled={busy || status?.emergency_stop}
                >
                  Resume session
                </button>
              )}
              {(session.status === "PENDING_CONFIRMATION" ||
                session.status === "ACTIVE") && (
                <button
                  className="button"
                  type="button"
                  onClick={() => void run(() => paper.suspendLiveSession(session.id))}
                  disabled={busy}
                >
                  Suspend Live Trading
                </button>
              )}
              <button
                className="button danger"
                type="button"
                onClick={() => void run(() => paper.endLiveSession(session.id))}
                disabled={busy}
              >
                End Live Session
              </button>
            </div>
          )}
        </div>

        <div className="emergency-stop-row">
          <span>
            <Shield size={16} />
            Emergency Stop:{" "}
            <b>{status?.emergency_stop ? "ACTIVE" : "Not active"}</b>
          </span>
          <button
            className="button danger"
            type="button"
            onClick={() => void run(() => paper.activateEmergencyStop())}
            disabled={busy || !status || status.emergency_stop}
          >
            Activate Emergency Stop
          </button>
        </div>
        {status?.emergency_stop && (
          <p className="live-admin-note">
            An administrator must clear the emergency stop. Clearing it will
            not activate a live session.
          </p>
        )}

        <div className="live-execution-lock">
          <Clock3 size={15} />
          <span>
            Live-order controls are unavailable. All order requests remain
            paper-only{serverMode ? " and are validated server-side" : " in this demo"}.
          </span>
        </div>
      </Panel>

      {confirming && session && (
        <Modal
          title="Confirm live trading"
          close={() => {
            if (!busy) setConfirming(false);
          }}
        >
          <div className="live-confirmation">
            <p>{confirmationWarning}</p>
            <p>
              <b>Current deployment status:</b> the broker session cannot be
              used for trading because GNK ALGO's live execution service is
              not implemented. Confirming will not enable live orders.
            </p>
            <div className="live-session-actions">
              <button
                className="button"
                type="button"
                onClick={() => setConfirming(false)}
                disabled={busy}
              >
                Cancel
              </button>
              <button
                className="button danger"
                type="button"
                onClick={() => {
                  setConfirming(false);
                  void run(() => paper.confirmLiveSession(session.id));
                }}
                disabled={busy}
              >
                I understand — confirm
              </button>
            </div>
          </div>
        </Modal>
      )}
    </>
  );
}
