import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  Pause,
  Play,
  Plus,
  Square,
  Zap,
} from "lucide-react";
import { instruments, money, paper, type Strategy } from "../api/paper";
import { useAction, usePaper } from "../hooks";
import {
  Badge,
  Chart,
  Empty,
  Feedback,
  Modal,
  PageHead,
  Panel,
} from "../components/ui";
export function StrategyList() {
  const { strategies, scenario } = usePaper();
  return (
    <>
      <PageHead
        eyebrow="BUILD. TEST. REFINE."
        title="Strategies"
        subtitle="Bring discipline to your ideas, one paper test at a time."
      >
        <Link className="button primary" to="/app/strategies/new">
          <Plus size={16} /> Create strategy
        </Link>
      </PageHead>
      <div className="banner">
        <Zap size={17} /> Every strategy runs in paper mode. Activation never
        starts real trading.
      </div>
      <div className="strategy-grid">
        {scenario === "empty" ? (
          <Empty title="Create your first strategy" />
        ) : (
          strategies.map((s, idx) => (
            <Link
              className="strategy-card"
              key={s.id}
              to={`/app/strategies/${s.id}`}
            >
              <div>
                <span className="strategy-card-icon">
                  <Zap size={22} />
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
              </div>
              <h2>{s.name}</h2>
              <p>
                {s.signal} · {s.symbol}
              </p>
              <Chart compact period={idx === 1 ? "1W" : "1D"} />
              <dl>
                <div>
                  <dt>Risk limit</dt>
                  <dd>{money(s.loss)}</dd>
                </div>
                <div>
                  <dt>Quantity</dt>
                  <dd>{s.quantity}</dd>
                </div>
                <div>
                  <dt>Mode</dt>
                  <dd>Paper</dd>
                </div>
              </dl>
              <span className="strategy-link">
                Configure & monitor <ArrowRight size={15} />
              </span>
            </Link>
          ))
        )}
      </div>
    </>
  );
}
export function StrategyEditor({ create = false }: { create?: boolean }) {
  const { id } = useParams(),
    { strategies } = usePaper(),
    navigate = useNavigate(),
    a = useAction();
  const s = strategies.find((x) => x.id === id);
  const [form, setForm] = useState({
    name: s?.name ?? "",
    symbol: s?.symbol ?? "RELIANCE",
    quantity: s?.quantity ?? 5,
    loss: s?.loss ?? 1000,
    signal: s?.signal ?? "EMA crossover",
  });
  const [confirm, setConfirm] = useState<Strategy["status"] | null>(null);
  if (!create && !s)
    return (
      <Empty title="Strategy not found">
        <Link to="/app/strategies">Return to strategies</Link>
      </Empty>
    );
  const status = s?.status ?? "Draft";
  const dirty =
    !!s &&
    (form.name !== s.name ||
      form.symbol !== s.symbol ||
      form.quantity !== s.quantity ||
      form.loss !== s.loss ||
      form.signal !== s.signal);
  const next =
    status === "Draft" || status === "Stopped"
      ? "Validated"
      : status === "Validated"
        ? "Tested"
        : status === "Tested" || status === "Paused"
          ? "Active"
          : null;
  const labels: Partial<Record<Strategy["status"], string>> = {
    Validated: "Validate configuration",
    Tested: "Run paper test",
    Active:
      status === "Paused" ? "Resume paper strategy" : "Activate paper strategy",
  };
  const transition = async (next: Strategy["status"]) => {
    await a.run(
      async () => {
        if (dirty && next !== "Paused" && next !== "Stopped")
          throw new Error("Save the modified configuration before continuing.");
        await paper.transition(id!, next);
        setConfirm(null);
      },
      next === "Tested"
        ? "Paper test passed. Fixture rules and risk settings accepted; no orders executed."
        : `Strategy ${next.toLowerCase()} successfully.`,
    );
  };
  return (
    <>
      <PageHead
        eyebrow="YOUR STRATEGY WORKSPACE"
        title={create ? "Create strategy" : s!.name}
        subtitle="Configure the rules. Validate the setup. Test before activation."
      >
        <Link className="button" to="/app/strategies">
          <ArrowLeft size={15} /> All strategies
        </Link>
        <Badge tone={status === "Active" ? "green" : "amber"}>{status}</Badge>
      </PageHead>
      <div className="lifecycle">
        {["Draft", "Validated", "Tested", "Active"].map((step, i) => (
          <span className={step === status ? "current" : ""} key={step}>
            <b>{i + 1}</b>
            {step}
            {i < 3 && <ArrowRight size={14} />}
          </span>
        ))}
      </div>
      {!confirm && <Feedback {...a} />}
      <div className="two-column">
        <Panel title="Configuration">
          <form
            className="form-grid"
            onSubmit={(e) => {
              e.preventDefault();
              void a.run(async () => {
                const newId = await paper.saveStrategy(
                  form,
                  create ? undefined : id,
                );
                if (create) navigate(`/app/strategies/${newId}`);
              }, "Configuration saved. Validate again before activation.");
            }}
          >
            <label className="span-2">
              Strategy name
              <input
                required
                maxLength={80}
                value={form.name}
                disabled={status === "Active"}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="e.g. Morning momentum"
              />
            </label>
            <label>
              Instrument
              <select
                value={form.symbol}
                disabled={status === "Active"}
                onChange={(e) => setForm({ ...form, symbol: e.target.value })}
              >
                {instruments.map((i) => (
                  <option key={i.symbol}>{i.symbol}</option>
                ))}
              </select>
            </label>
            <label>
              Signal template
              <select
                value={form.signal}
                disabled={status === "Active"}
                onChange={(e) => setForm({ ...form, signal: e.target.value })}
              >
                <option>EMA crossover</option>
                <option>Opening range</option>
                <option>RSI reversal</option>
              </select>
            </label>
            <label>
              Quantity
              <input
                type="number"
                min={1}
                max={1000}
                step={1}
                required
                value={form.quantity || ""}
                disabled={status === "Active"}
                onChange={(e) =>
                  setForm({ ...form, quantity: Number(e.target.value) })
                }
              />
            </label>
            <label>
              Maximum paper loss (INR)
              <input
                type="number"
                min={1}
                step={1}
                required
                value={form.loss || ""}
                disabled={status === "Active"}
                onChange={(e) =>
                  setForm({ ...form, loss: Number(e.target.value) })
                }
              />
            </label>
            <div className="span-2">
              <button
                className="button primary full"
                disabled={status === "Active" || a.busy}
              >
                Save configuration
              </button>
              <small className="muted">
                Saving resets validation and paper test results. Pause an active
                strategy before editing.
              </small>
            </div>
          </form>
        </Panel>
        <Panel title="Lifecycle & monitoring" extra={<Badge>Paper mode</Badge>}>
          <div className="strategy-monitor">
            <h3>
              {status === "Active"
                ? "Your paper strategy is active."
                : "A deliberate path to activation."}
            </h3>
            <p>
              No strategy engine is running. This frontend simulates lifecycle
              transitions and fixture-based validation.
            </p>
            {status === "Tested" ||
            status === "Active" ||
            status === "Paused" ||
            status === "Stopped" ? (
              <div className="test-result">
                <Badge tone="green">Fixture test passed</Badge>
                <p>
                  Signal: configured · Risk limit: positive · Execution: paper
                </p>
                <small>
                  This is not a backtest or a profitability forecast.
                </small>
              </div>
            ) : (
              <p className="muted">
                Save configuration, validate, and run the fixture paper test.
              </p>
            )}
            <div className="lifecycle-actions">
              {!create && next && (
                <button
                  className="button primary"
                  disabled={a.busy}
                  onClick={() => {
                    if (next === "Active") setConfirm(next);
                    else void transition(next);
                  }}
                >
                  <Play size={15} />
                  {labels[next]}
                </button>
              )}
              {status === "Active" && (
                <button
                  className="button"
                  disabled={a.busy}
                  onClick={() => void transition("Paused")}
                >
                  <Pause size={15} /> Pause strategy
                </button>
              )}
              {["Active", "Paused"].includes(status) && (
                <button
                  className="button danger"
                  disabled={a.busy}
                  onClick={() => setConfirm("Stopped")}
                >
                  <Square size={14} /> Stop strategy
                </button>
              )}
            </div>
          </div>
        </Panel>
      </div>
      {confirm && (
        <Modal
          title={
            confirm === "Active"
              ? "Activate paper strategy?"
              : "Stop paper strategy?"
          }
          close={() => setConfirm(null)}
        >
          <div className="modal-content">
            <p>
              {confirm === "Active"
                ? "Confirm activation in the simulator. No real trades or automated orders will be placed."
                : "Stop this paper strategy. Existing positions stay open. Revalidation is required before restarting."}
            </p>
            <Feedback {...a} />
            <button
              className="button primary full"
              disabled={a.busy}
              onClick={() => void transition(confirm)}
            >
              Confirm {confirm === "Active" ? "activation" : "stop"}
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
