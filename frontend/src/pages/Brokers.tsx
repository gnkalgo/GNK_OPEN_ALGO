import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Check, ExternalLink, Link2, ShieldCheck, Unplug } from "lucide-react";
import { paper, serverMode } from "../api/paper";
import { server, type BrokerCode, type BrokerProvider } from "../api/server";
import { useAction, usePaper } from "../hooks";
import { Badge, Feedback, PageHead, Panel } from "../components/ui";
import { LiveTradingPanel } from "../components/LiveTradingPanel";
export default function Brokers({ callback = false }: { callback?: boolean }) {
  const { broker } = usePaper(),
    a = useAction(),
    [authorize, setAuthorize] = useState(false),
    [params] = useSearchParams();
  const navigate = useNavigate();
  const [providers, setProviders] = useState<BrokerProvider[]>([]);
  const [pendingToken, setPendingToken] = useState("");
  const [pendingAccount, setPendingAccount] = useState<{
    code: BrokerCode;
    name: string;
    account_name: string;
    account_mask: string;
  } | null>(null);
  useEffect(() => {
    if (callback && params.get("error"))
      a.setError(
        "Broker authorization denied. Return to connections and try again.",
      );
  }, [callback, params]);
  useEffect(() => {
    if (!serverMode) return;
    void server
      .brokers()
      .then(({ providers: current }) => setProviders(current))
      .catch((error: unknown) =>
        a.setError(
          error instanceof Error
            ? error.message
            : "Could not load broker connections.",
        ),
      );
  }, []);
  useEffect(() => {
    if (!callback || !serverMode) return;
    const fragment = new URLSearchParams(window.location.hash.slice(1));
    const token = fragment.get("pending") ?? "";
    if (token) {
      window.history.replaceState(
        null,
        "",
        window.location.pathname + window.location.search,
      );
      setPendingToken(token);
      void server
        .brokerPending(token)
        .then(setPendingAccount)
        .catch((error: unknown) =>
          a.setError(
            error instanceof Error
              ? error.message
              : "Broker account confirmation expired. Reconnect and retry.",
          ),
        );
    }
  }, [callback]);

  async function reloadProviders() {
    const result = await server.brokers();
    setProviders(result.providers);
  }

  async function startBrokerLink(code: BrokerCode) {
    await a.run(async () => {
      const { authorization_url } = await server.authorizeBroker(code);
      window.location.assign(authorization_url);
    });
  }

  async function confirmBrokerLink() {
    if (!pendingAccount || !pendingToken) return;
    await a.run(async () => {
      await server.confirmBroker(pendingAccount.code, pendingToken);
      setPendingToken("");
      setPendingAccount(null);
      await reloadProviders();
      navigate("/app/brokers", { replace: true });
    }, "Broker account linked. Review trading mode to activate an eligible Dhan live session.");
  }

  async function disconnectBroker(code: BrokerCode) {
    await a.run(async () => {
      await server.disconnectBroker(code);
      await reloadProviders();
    }, "Broker account unlinked.");
  }

  return (
    <>
      <PageHead
        eyebrow="YOUR EXECUTION CONNECTION"
        title={
          callback ? "Broker authentication callback" : "Broker connections"
        }
        subtitle={
          serverMode
            ? "Link your broker account securely, then review and confirm an eligible Dhan live session."
            : "Connect the paper simulator to explore the complete trading workflow."
        }
      />
      <div className="banner">
        <ShieldCheck size={18} />
        {serverMode
          ? "Broker sign-in is handled by each broker. Dhan account identity and access tokens are encrypted on the server; only a masked ID is displayed. FYERS and Zerodha tokens are discarded after account linking. Dhan live trading requires server readiness checks and your explicit session confirmation."
          : "Frontend demo only. No real broker credentials, redirects, or access tokens are used."}
      </div>
      {serverMode && callback && pendingAccount && (
        <Panel title="Confirm broker account">
          <div className="broker-card">
            <Badge tone="amber">Confirmation required</Badge>
            <h2>{pendingAccount.name}</h2>
            <p>
              Authorize linking <strong>{pendingAccount.account_name}</strong>{" "}
              ({pendingAccount.account_mask}) to your GNK profile.
            </p>
            <p>
              {pendingAccount.code === "dhan"
                ? "GNK retains your Dhan account identity and access token encrypted on the server for the live pilot. Linking does not place orders; review and confirm a live session separately."
                : "This records the account link only. The broker access token is discarded and live execution is unavailable for this broker."}
            </p>
            <Feedback {...a} />
            <button
              className="button primary"
              disabled={a.busy}
              onClick={() => void confirmBrokerLink()}
            >
              <Check size={16} /> Confirm account link
            </button>{" "}
            <Link to="/app/brokers" className="button">
              Cancel
            </Link>
          </div>
        </Panel>
      )}
      {serverMode && (
        <Panel title="Broker accounts" extra={<Badge>Dhan live pilot</Badge>}>
          <div className="broker-provider-grid">
            {providers.map((provider) => (
              <article className="broker-provider" key={provider.code}>
                <div className="broker-provider-heading">
                  <h3>{provider.name}</h3>
                  <Badge
                    tone={
                      provider.connection
                        ? "green"
                        : provider.configured
                          ? "amber"
                          : "neutral"
                    }
                  >
                    {provider.connection
                      ? "Linked"
                      : provider.configured
                        ? "Ready"
                        : "Not configured"}
                  </Badge>
                </div>
                {provider.connection ? (
                  <>
                    <p>{provider.connection.account_name}</p>
                    <p className="muted">{provider.connection.account_mask}</p>
                    <button
                      className="button"
                      disabled={a.busy}
                      onClick={() => void disconnectBroker(provider.code)}
                    >
                      Unlink account
                    </button>
                  </>
                ) : (
                  <>
                    <p>
                      Continue to {provider.name} to authorize account linking.
                    </p>
                    <button
                      className="button primary"
                      disabled={!provider.configured || a.busy}
                      onClick={() => void startBrokerLink(provider.code)}
                    >
                      <ExternalLink size={15} /> Connect {provider.name}
                    </button>
                    {!provider.configured && (
                      <p className="muted">
                        Broker app credentials have not been configured by the
                        administrator.
                      </p>
                    )}
                  </>
                )}
              </article>
            ))}
            {providers.length === 0 && (
              <p role="status">Loading broker availability…</p>
            )}
          </div>
          <Feedback {...a} />
          <p className="muted">
            Callback codes: <code>dhan</code>, <code>fyers</code>,{" "}
            <code>zerodha</code>. Configure each broker app with its exact GNK
            callback URL in the deployment guide.
          </p>
        </Panel>
      )}
      {serverMode && !callback && <LiveTradingPanel />}
      <div className="two-column">
        <Panel
          title="GNK Paper Broker"
          extra={
            <Badge tone={broker === "Connected" ? "green" : "amber"}>
              {broker}
            </Badge>
          }
        >
          <div className="broker-card">
            <div className="broker-mark">
              <Link2 size={30} />
            </div>
            <h2>Your safe execution sandbox</h2>
            <p>
              Practice order entry and strategy lifecycles with fictional
              instruments and an in-memory paper ledger.
            </p>
            <ul className="check-list">
              <li>
                <Check size={15} /> Simulated funds and order fills
              </li>
              <li>
                <Check size={15} /> No real money or broker access
              </li>
              <li>
                <Check size={15} /> Reconnect and recovery scenarios
              </li>
            </ul>
            <Feedback {...a} />
            {broker === "Connected" ? (
              <Link to="/app/dashboard" className="button primary">
                Go to dashboard →
              </Link>
            ) : (
              <button
                className="button primary"
                disabled={a.busy}
                onClick={() => setAuthorize(true)}
              >
                <Unplug size={16} />
                {broker === "Expired"
                  ? "Reconnect paper broker"
                  : "Connect paper broker"}
              </button>
            )}
            {authorize && (
              <div className="authorization-box">
                <h3>Authorize paper connection</h3>
                <p>
                  This simulates broker consent. No external account is
                  accessed.
                </p>
                <button
                  className="button primary"
                  disabled={a.busy}
                  onClick={() =>
                    void a.run(async () => {
                      await paper.connect();
                      setAuthorize(false);
                      navigate("/app/brokers/callback?result=approved");
                    }, "Paper broker connected successfully.")
                  }
                >
                  <ExternalLink size={15} /> Approve simulated authorization
                </button>
                <Link
                  to="/app/brokers/callback?error=access_denied"
                  className="button"
                >
                  Deny authorization
                </Link>
              </div>
            )}
          </div>
        </Panel>
        <Panel title="Connection checklist">
          <div className="steps-list">
            <div>
              <span>01</span>
              <h3>Authorize your connection</h3>
              <p>
                {serverMode
                  ? "Connect Dhan above and sign in on the broker's authorization page."
                  : "Use the simulated consent flow. Never enter broker secrets here."}
              </p>
            </div>
            <div>
              <span>02</span>
              <h3>Confirm connection status</h3>
              <p>
                {serverMode
                  ? "Confirm the returned account identity to complete linking."
                  : "The status changes to Connected after a successful callback simulation."}
              </p>
            </div>
            <div>
              <span>03</span>
              <h3>{serverMode ? "Review trading mode" : "Start with a paper order"}</h3>
              <p>{serverMode
                ? "Resolve the listed live blockers, request a Dhan session and explicitly confirm activation. The live desk supports NSE equity delivery BUY LIMIT orders."
                : "Review instrument, size, and direction before confirming."}</p>
            </div>
          </div>
          {callback && (
            <Link className="button" to="/app/brokers">
              Return to connections
            </Link>
          )}
        </Panel>
      </div>
    </>
  );
}
