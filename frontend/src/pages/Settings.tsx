import { useState } from "react";
import { Link } from "react-router-dom";
import {
  Bell,
  Check,
  LockKeyhole,
  Monitor,
  Moon,
  ShieldCheck,
  Sun,
  User,
} from "lucide-react";
import { paper, serverMode } from "../api/paper";
import AdminServer from "./AdminServer";
import { useAction, usePaper } from "../hooks";
import { Badge, Feedback, PageHead, Panel } from "../components/ui";
export default function Settings() {
  const { session } = usePaper(),
    [name, setName] = useState(session?.name ?? ""),
    [tab, setTab] = useState("Profile"),
    [theme, setTheme] = useState(
      document.documentElement.dataset.theme ?? "dark",
    ),
    [emailNotifications, setEmailNotifications] = useState(true),
    a = useAction();
  return (
    <>
      <PageHead
        eyebrow="MAKE IT YOUR WORKSPACE"
        title="Account settings"
        subtitle="Manage your profile, security, and preferences."
      />
      <div className="tabs settings-tabs">
        {[
          ["Profile", User],
          ["Security", ShieldCheck],
          ["Appearance", Monitor],
          ["Preferences", Bell],
        ].map(([t, I]) => {
          const Icon = I as typeof User;
          return (
            <button
              className={t === tab ? "active" : ""}
              onClick={() => setTab(String(t))}
              key={String(t)}
            >
              <Icon size={16} />
              {String(t)}
            </button>
          );
        })}
      </div>
      <div className="settings-panel">
        <Panel title={tab} extra={<Badge>Demo account</Badge>}>
          {tab === "Profile" && (
            <form
              className="form-grid"
              onSubmit={(e) => {
                e.preventDefault();
                void a.run(async () => {
                  await paper.profile(name);
                }, "Profile saved for this session.");
              }}
            >
              <div className="profile-intro span-2">
                <span className="avatar large-avatar">{session?.name[0]}</span>
                <div>
                  <h3>{session?.name}</h3>
                  <p>Personal paper trading account</p>
                </div>
              </div>
              <label className="span-2">
                Full name
                <input
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </label>
              <label className="span-2">
                Email address
                <input type="email" value={session?.email} disabled />
                <small>
                  Email changes require server-side verification in production.
                </small>
              </label>
              <div className="span-2">
                <Feedback {...a} />
                <button className="button primary" disabled={a.busy}>
                  Save profile
                </button>
              </div>
            </form>
          )}
          {tab === "Security" && (
            <div className="settings-content">
              <div className="security-row">
                <LockKeyhole size={22} />
                <div>
                  <h3>Password & recovery</h3>
                  <p>Explore the simulated password recovery flow.</p>
                </div>
                <Link className="button" to="/forgot-password">
                  Reset password
                </Link>
              </div>
              <div className="security-row">
                <ShieldCheck size={22} />
                <div>
                  <h3>Session security</h3>
                  <p>
                    Demo identity exists only in memory and clears on refresh or
                    logout.
                  </p>
                </div>
                <Badge tone="green">No tokens stored</Badge>
              </div>
              <div className="banner">
                Production authentication, role checks, MFA, and session
                revocation must be enforced by GNK ALGO’s server.
              </div>
            </div>
          )}
          {tab === "Appearance" && (
            <div className="settings-content">
              <h3>Choose your theme</h3>
              <p>A workspace that works with you.</p>
              <div className="theme-options">
                {[
                  ["dark", "Carbon", Moon],
                  ["light", "Daylight", Sun],
                  ["system", "System", Monitor],
                ].map(([value, label, I]) => {
                  const Icon = I as typeof Sun;
                  return (
                    <button
                      key={String(value)}
                      className={theme === value ? "chosen" : ""}
                      onClick={() => {
                        const t = String(value);
                        setTheme(t);
                        document.documentElement.dataset.theme =
                          t === "system"
                            ? window.matchMedia("(prefers-color-scheme: light)")
                                .matches
                              ? "light"
                              : "dark"
                            : t;
                      }}
                    >
                      <Icon size={23} />
                      <span>{String(label)}</span>
                      {theme === value && <Check size={15} />}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
          {tab === "Preferences" && (
            <div className="settings-content">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={emailNotifications}
                  onChange={(e) => setEmailNotifications(e.target.checked)}
                />{" "}
                Paper activity notifications
              </label>
              <p>
                Preference preview for this session only. No emails or external
                notifications are sent.
              </p>
              <Badge tone="amber">Live trading unavailable</Badge>
              <p>
                Real order submission is intentionally absent from this
                frontend.
              </p>
            </div>
          )}
        </Panel>
      </div>
    </>
  );
}
export function Admin() {
  const { session, activity } = usePaper(),
    [tab, setTab] = useState("Users"),
    [suspended, setSuspended] = useState(false),
    [maintenance, setMaintenance] = useState(false);
  if (serverMode) return <AdminServer />;
  if (session?.role !== "admin")
    return (
      <>
        <PageHead
          title="Access denied"
          subtitle="This screen requires the administrator role."
        />
        <div className="banner warning" role="alert">
          Your current demo role is trader. Server-side authorization is
          required in production.
        </div>
        <Link className="button" to="/app/dashboard">
          Return to dashboard
        </Link>
      </>
    );
  return (
    <>
      <PageHead
        eyebrow="ADMINISTRATION"
        title="Workspace administration"
        subtitle="Role-restricted interface preview. No production users or systems are connected."
      />
      <div className="banner">
        Demo role switching previews this screen only. It provides no server
        authority.
      </div>
      <div className="tabs settings-tabs">
        {["Users", "System status", "Audit events", "Configuration"].map(
          (t) => (
            <button
              className={tab === t ? "active" : ""}
              key={t}
              onClick={() => setTab(t)}
            >
              {t}
            </button>
          ),
        )}
      </div>
      <Panel title={tab}>
        {tab === "Users" && (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>USER</th>
                  <th>ROLE</th>
                  <th>STATUS</th>
                  <th>ACTION</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>
                    Sample paper trader<small>sample@gnk.demo</small>
                  </td>
                  <td>Trader</td>
                  <td>
                    <Badge tone={suspended ? "amber" : "green"}>
                      {suspended ? "Suspended" : "Enabled"}
                    </Badge>
                  </td>
                  <td>
                    <button
                      className="button"
                      onClick={() => setSuspended(!suspended)}
                    >
                      {suspended ? "Restore demo user" : "Suspend demo user"}
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        )}
        {tab === "System status" && (
          <div className="settings-content">
            <Badge tone="green">Simulator operational</Badge>
            <p>API: not connected · Feed: fixture · Execution: paper only</p>
          </div>
        )}
        {tab === "Audit events" && (
          <div className="settings-content">
            {activity.map((x, i) => (
              <p key={i}>
                <Badge>Demo event</Badge> {x}
              </p>
            ))}
          </div>
        )}
        {tab === "Configuration" && (
          <div className="settings-content">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={maintenance}
                onChange={(e) => setMaintenance(e.target.checked)}
              />{" "}
              Preview maintenance banner
            </label>
            {maintenance && (
              <div className="banner warning" role="status">
                Maintenance preview enabled for this admin screen.
              </div>
            )}
            <p>
              Execution mode: paper (locked). Configuration changes are local
              previews.
            </p>
          </div>
        )}
      </Panel>
    </>
  );
}
export function Help() {
  return (
    <>
      <PageHead
        title="Help & documentation"
        subtitle="A clear path through your paper trading workspace."
      />
      <div className="two-column">
        <Panel title="Start your journey">
          <div className="settings-content">
            <ol className="help-steps">
              <li>Connect the GNK Paper Broker.</li>
              <li>Search for an instrument in Markets.</li>
              <li>Review and confirm a paper order.</li>
              <li>Follow status in Order book and review Positions.</li>
              <li>Create a strategy, validate, and run the paper test.</li>
            </ol>
            <Link className="button primary" to="/app/brokers">
              Connect paper broker →
            </Link>
          </div>
        </Panel>
        <Panel title="Safe recovery">
          <div className="settings-content">
            <h3>Unknown order outcome?</h3>
            <p>
              Open the order book and use Reconcile status. Never resubmit
              blindly.
            </p>
            <h3>Feed or broker disconnected?</h3>
            <p>
              Reconnect before creating another paper order. Use Demo scenarios
              to explore failures.
            </p>
            <h3>Need to sign in again?</h3>
            <p>
              Reloading clears the demo session. Sign in with trader@gnk.demo
              and PaperDemo!2026.
            </p>
          </div>
        </Panel>
      </div>
    </>
  );
}
