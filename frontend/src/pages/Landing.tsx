import {
  ArrowRight,
  ArrowUpRight,
  ChartNoAxesCombined,
  Check,
  Code2,
  Layers,
  ShieldCheck,
  Zap,
} from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { paper, serverMode } from "../api/paper";
import { Badge, Brand, Chart } from "../components/ui";
export default function Landing() {
  const navigate = useNavigate();
  return (
    <div className="landing">
      <header className="public-nav">
        <Brand />
        <nav aria-label="Public navigation">
          <a href="#platform">Platform</a>
          <a href="#workflow">How it works</a>
          <a href="#safety">Built for confidence</a>
        </nav>
        <div>
          <Link to="/login" className="quiet-link">
            Sign in
          </Link>
          <Link to="/register" className="button primary">
            Get started <ArrowUpRight size={15} />
          </Link>
        </div>
      </header>
      <main>
        <section className="hero">
          <div className="hero-copy">
            <Badge tone="green">Your edge starts here</Badge>
            <h1>
              Intelligence behind
              <br />
              <em>every trade.</em>
            </h1>
            <p>
              A focused workspace for your markets, strategies, and execution.
              Bring your ideas to life with clarity and control.
            </p>
            <div className="hero-buttons">
              <Link to="/register" className="button primary large">
                Build your trading edge <ArrowRight size={17} />
              </Link>
              <button
                className="button large"
                onClick={() => {
                  if (serverMode) navigate("/login");
                  else {
                    paper.explore();
                    navigate("/app/dashboard");
                  }
                }}
              >
                Explore paper workspace <ArrowUpRight size={17} />
              </button>
            </div>
            <div className="hero-proof">
              <span>
                <Check size={14} /> No broker credentials needed
              </span>
              <span>
                <Check size={14} /> Paper trading first
              </span>
            </div>
            <p className="disclaimer">
              Frontend demonstration · Fictional data · No live order execution
            </p>
          </div>
          <div className="hero-art">
            <img
              src="/gnk-logo.png"
              alt="GNK ALGO — Intelligence Behind Every Trade, with bull and bear artwork"
            />
            <div className="art-caption">
              <span className="status-dot" /> PREDICT. ANALYZE. EXECUTE.
            </div>
          </div>
        </section>
        <div className="landing-market">
          <span>
            ONE WORKSPACE.
            <br />
            <b>EVERY OPPORTUNITY.</b>
          </span>
          {[
            ["NIFTY 50", "24,825.10", "+0.67%"],
            ["SENSEX", "81,467.10", "+0.54%"],
            ["BANK NIFTY", "51,295.80", "+0.82%"],
          ].map(([n, v, c]) => (
            <div key={n}>
              <small>{n} · MOCK</small>
              <b>
                {v} <span className="positive">{c}</span>
              </b>
            </div>
          ))}
          <Chart compact />
        </div>
        <section id="platform" className="landing-section">
          <div className="eyebrow">PURPOSE-BUILT FOR YOUR PROCESS</div>
          <h2>Less friction. More focus.</h2>
          <p>
            From your first watchlist to your next strategy, everything
            connects.
          </p>
          <div className="feature-grid">
            {[
              [
                ChartNoAxesCombined,
                "See the bigger picture",
                "Track instruments, build watchlists, and explore market context in one clear view.",
              ],
              [
                Zap,
                "Turn ideas into a process",
                "Configure, validate, and paper test strategies before activating them.",
              ],
              [
                ShieldCheck,
                "Stay in control",
                "Review every order, monitor status, and recover safely from uncertain outcomes.",
              ],
            ].map(([Icon, title, copy]) => {
              const I = Icon as typeof Zap;
              return (
                <article key={String(title)}>
                  <I size={24} />
                  <h3>{String(title)}</h3>
                  <p>{String(copy)}</p>
                  <Link to="/register">
                    Explore the platform <ArrowUpRight size={15} />
                  </Link>
                </article>
              );
            })}
          </div>
        </section>
        <section id="workflow" className="workflow-section">
          <div>
            <div className="eyebrow">A CLEAR PATH FROM IDEA TO ACTION</div>
            <h2>
              Your workflow.
              <br />
              Working together.
            </h2>
            <p>Keep research, execution, and review in the same workspace.</p>
            <Link to="/register" className="button primary">
              Start your paper journey <ArrowRight size={16} />
            </Link>
          </div>
          <ol>
            {[
              [
                "01",
                "Connect your workspace",
                "Create a demo account and connect the paper broker.",
              ],
              [
                "02",
                "Find your opportunity",
                "Explore fictional markets and review your order.",
              ],
              [
                "03",
                "Execute. Learn. Refine.",
                "Submit a paper order, review positions, and test your next idea.",
              ],
            ].map(([n, t, d]) => (
              <li key={n}>
                <span>{n}</span>
                <div>
                  <h3>{t}</h3>
                  <p>{d}</p>
                </div>
              </li>
            ))}
          </ol>
        </section>
        <section id="safety" className="safety-section">
          <Layers size={24} />
          <h2>
            Built with intention.
            <br />
            Designed for confidence.
          </h2>
          <p>
            Clear status indicators. Explicit order reviews. Independent GNK
            ALGO contracts.
          </p>
          <div>
            <span>
              <ShieldCheck size={16} /> Paper-only execution
            </span>
            <span>
              <Code2 size={16} /> Documented API boundary
            </span>
            <span>
              <Check size={16} /> Accessible by design
            </span>
          </div>
        </section>
      </main>
      <footer className="public-footer">
        <Brand />
        <span>© 2026 GNK ALGO. Intelligence Behind Every Trade.</span>
        <Link to="/login">
          Enter workspace <ArrowUpRight size={14} />
        </Link>
      </footer>
    </div>
  );
}
