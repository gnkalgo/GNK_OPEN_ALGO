import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  LockKeyhole,
  MailCheck,
  ShieldCheck,
} from "lucide-react";
import { Brand, Feedback } from "../components/ui";
import { DemoLab } from "../components/Shell";
import { paper, serverMode } from "../api/paper";
import { useAction } from "../hooks";
export default function Auth({
  kind,
}: {
  kind: "login" | "register" | "verify" | "forgot" | "reset";
}) {
  const [email, setEmail] = useState(""),
    [name, setName] = useState(""),
    [password, setPassword] = useState(""),
    [sent, setSent] = useState(false);
  const a = useAction(),
    navigate = useNavigate(),
    location = useLocation();
  const [linkToken] = useState(() => {
    const value =
      new URLSearchParams(window.location.hash.slice(1)).get("token") ?? "";
    return value;
  });
  useEffect(() => {
    if (linkToken) history.replaceState(null, "", window.location.pathname);
  }, [linkToken]);
  const titles = {
    login: "Welcome back.",
    register: "Create your workspace.",
    verify: "Check your inbox.",
    forgot: "Forgot your password?",
    reset: "A fresh start.",
  };
  async function submit() {
    await a.run(async () => {
      if (kind === "register") {
        if (!serverMode && password !== "PaperDemo!2026")
          throw new Error(
            "For this demo, use the sample password PaperDemo!2026. Do not use a real password.",
          );
        await paper.register(name, email, password);
        setPassword("");
        navigate("/verify-email");
      }
      if (kind === "login") {
        await paper.login(email, password);
        setPassword("");
        navigate("/app/brokers");
      }
      if (kind === "verify") {
        if (serverMode && !linkToken) {
          await paper.resend(email);
          setSent(true);
          return;
        }
        await paper.verify(linkToken);
        navigate("/login");
      }
      if (kind === "forgot") {
        await paper.forgot(email);
        setSent(true);
      }
      if (kind === "reset") {
        if (
          !serverMode &&
          (new URLSearchParams(location.search).get("demo") !== "valid" ||
            paper.snapshot().scenario === "expired-link")
        )
          throw new Error(
            "Reset link is invalid or expired. Request a new link.",
          );
        if (!serverMode && password !== "PaperDemo!2026")
          throw new Error("Use the sample password PaperDemo!2026.");
        await paper.reset(linkToken, password);
        setPassword("");
        setSent(true);
      }
    });
  }
  return (
    <div className="auth-page">
      <div className="auth-story">
        <Brand />
        <div>
          <div className="eyebrow">YOUR NEXT CHAPTER STARTS HERE</div>
          <h1>
            Built for focus.
            <br />
            <em>Ready for your edge.</em>
          </h1>
          <p>
            A clearer view of your markets. A smarter way to test your ideas.
          </p>
          <img src="/gnk-logo.png" alt="GNK ALGO bull and bear brand artwork" />
        </div>
        <small>Intelligence Behind Every Trade.</small>
      </div>
      <div className="auth-side">
        <Link to="/" className="back-link">
          <ArrowLeft size={15} /> Back to home
        </Link>
        <div className="auth-form">
          <div className="auth-icon">
            {kind === "verify" ? <MailCheck /> : <LockKeyhole />}
          </div>
          <h1>{titles[kind]}</h1>
          <p>
            {kind === "login"
              ? "Sign in to your GNK ALGO paper workspace."
              : kind === "register"
                ? "A focused trading experience, from day one."
                : kind === "verify"
                  ? serverMode
                    ? linkToken
                      ? "Confirm the single-use email verification link."
                      : "Check your inbox, or request a fresh verification email below."
                    : "Simulate the email link below to verify your demo account."
                  : "Try the password recovery flow with a demo link."}
          </p>
          {serverMode ? (
            <div className="banner">
              Secure account mode · Server-authenticated paper trading.
              Verification and recovery links arrive by email.
            </div>
          ) : (
            <div className="banner">
              Demo only. Use fictional details and sample password{" "}
              <code>PaperDemo!2026</code>. Email is never sent.
            </div>
          )}
          {location.state?.expired && (
            <p role="alert" className="feedback error">
              Session expired. Sign in again.
            </p>
          )}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void submit();
            }}
          >
            {kind === "register" && (
              <label>
                Full name
                <input
                  autoComplete="off"
                  required
                  minLength={2}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Alex Morgan"
                />
              </label>
            )}
            {(["login", "register", "forgot"].includes(kind) ||
              (serverMode && kind === "verify" && !linkToken)) && (
              <label>
                Email address
                <input
                  type="email"
                  autoComplete="off"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="trader@gnk.demo"
                />
              </label>
            )}
            {["login", "register", "reset"].includes(kind) && (
              <label>
                {serverMode ? "Password" : "Demo password"}
                <input
                  type="password"
                  autoComplete={
                    serverMode
                      ? kind === "login"
                        ? "current-password"
                        : "new-password"
                      : "off"
                  }
                  required
                  minLength={12}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={
                    serverMode
                      ? "At least 12 characters"
                      : "Sample password only"
                  }
                />
              </label>
            )}
            {kind === "login" && (
              <Link className="forgot-link" to="/forgot-password">
                Forgot password?
              </Link>
            )}
            {kind === "register" && (
              <label className="checkbox-label">
                <input type="checkbox" required />I understand this is a
                fictional paper-trading demo.
              </label>
            )}
            <Feedback {...a} />
            {sent ? (
              <div className="feedback success" role="status">
                {kind === "forgot"
                  ? serverMode
                    ? "If an account exists, a reset email will be sent."
                    : "If an account exists, a reset link would be sent."
                  : kind === "verify"
                    ? "If eligible, a verification email will be sent."
                    : serverMode
                      ? "Password reset complete."
                      : "Demo password reset complete."}
              </div>
            ) : (
              <button className="button primary full" disabled={a.busy}>
                {
                  {
                    login: "Sign in",
                    register: "Create account",
                    verify: serverMode
                      ? linkToken
                        ? "Verify email link"
                        : "Request verification email"
                      : "Simulate verification link",
                    forgot: "Request reset link",
                    reset: serverMode
                      ? "Reset password"
                      : "Reset demo password",
                  }[kind]
                }
                <ArrowRight size={16} />
              </button>
            )}
          </form>
          {!serverMode && kind === "forgot" && sent && (
            <Link className="button full" to="/reset-password?demo=valid">
              Open simulated reset link
            </Link>
          )}
          {!serverMode && kind === "verify" && (
            <button
              className="button full"
              onClick={() => {
                paper.scenario("normal");
                a.setError("");
              }}
            >
              Request a new demo link
            </button>
          )}
          {kind === "login" && (
            <p className="auth-switch">
              New to GNK ALGO? <Link to="/register">Create an account</Link>
            </p>
          )}
          {kind !== "login" && (
            <p className="auth-switch">
              Already have an account? <Link to="/login">Sign in</Link>
            </p>
          )}
          <div className="auth-security">
            <ShieldCheck size={14} />{" "}
            {serverMode
              ? "Server sessions · HttpOnly cookies · Paper execution only"
              : "In-memory demo. No credentials retained."}
          </div>
        </div>
        <DemoLab />
      </div>
    </div>
  );
}
