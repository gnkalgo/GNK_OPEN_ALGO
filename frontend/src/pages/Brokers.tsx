import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Check, ExternalLink, Link2, ShieldCheck, Unplug } from "lucide-react";
import { paper, serverMode } from "../api/paper";
import { useAction, usePaper } from "../hooks";
import { Badge, Feedback, PageHead, Panel } from "../components/ui";
export default function Brokers({ callback = false }: { callback?: boolean }) {
  const { broker } = usePaper(),
    a = useAction(),
    [authorize, setAuthorize] = useState(false),
    [params] = useSearchParams();
  const navigate = useNavigate();
  useEffect(() => {
    if (callback && params.get("error"))
      a.setError(
        "Broker authorization denied. Return to connections and try again.",
      );
  }, [callback, params]);
  return (
    <>
      <PageHead
        eyebrow="YOUR EXECUTION CONNECTION"
        title={
          callback ? "Broker authentication callback" : "Broker connections"
        }
        subtitle="Connect the paper simulator to explore the complete trading workflow."
      />
      <div className="banner">
        <ShieldCheck size={18} /> Frontend demo only. No real broker
        credentials, redirects, or access tokens are used.
      </div>
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
                Use the simulated consent flow. Never enter broker secrets here.
              </p>
            </div>
            <div>
              <span>02</span>
              <h3>Confirm connection status</h3>
              <p>
                The status changes to Connected after a successful callback
                simulation.
              </p>
            </div>
            <div>
              <span>03</span>
              <h3>Start with a paper order</h3>
              <p>Review instrument, size, and direction before confirming.</p>
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
