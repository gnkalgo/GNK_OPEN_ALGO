import { useEffect, useState } from "react";
import { server } from "../api/server";
import { useAction } from "../hooks";
import { Badge, Empty, Feedback, PageHead, Panel } from "../components/ui";
export default function AdminServer() {
  const [tab, setTab] = useState("Users"),
    [users, setUsers] = useState<Awaited<ReturnType<typeof server.adminUsers>>>(
      [],
    ),
    [status, setStatus] = useState<Record<string, string | number>>({}),
    [events, setEvents] = useState<
      Awaited<ReturnType<typeof server.adminAudit>>
    >([]);
  const a = useAction();
  useEffect(() => {
    void a.run(async () => {
      if (tab === "Users") setUsers(await server.adminUsers());
      if (tab === "System status") setStatus(await server.adminStatus());
      if (tab === "Audit events") setEvents(await server.adminAudit());
    });
  }, [tab]);
  return (
    <>
      <PageHead
        title="Workspace administration"
        subtitle="Server-authorized account management and paper system status."
      />
      <div className="tabs settings-tabs">
        {["Users", "System status", "Audit events", "Configuration"].map(
          (t) => (
            <button
              key={t}
              className={tab === t ? "active" : ""}
              onClick={() => setTab(t)}
            >
              {t}
            </button>
          ),
        )}
      </div>
      <Feedback {...a} />
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
                {users.map((u) => (
                  <tr key={u.id}>
                    <td>
                      {u.name}
                      <small>{u.email}</small>
                    </td>
                    <td>{u.role}</td>
                    <td>
                      <Badge tone={u.enabled ? "green" : "amber"}>
                        {u.enabled ? "Enabled" : "Suspended"}
                      </Badge>
                    </td>
                    <td>
                      <button
                        className="button"
                        disabled={a.busy}
                        onClick={() =>
                          void a.run(async () => {
                            await server.adminToggle(u.id, !u.enabled);
                            setUsers(await server.adminUsers());
                          }, "Account status updated; existing sessions revoked.")
                        }
                      >
                        {u.enabled ? "Suspend account" : "Restore account"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {tab === "System status" && (
          <div className="settings-content">
            {Object.entries(status).map(([k, v]) => (
              <p key={k}>
                {k}: <b>{v}</b>
              </p>
            ))}
          </div>
        )}
        {tab === "Audit events" &&
          (events.length ? (
            <div className="settings-content">
              {events.map((e) => (
                <p key={e.id}>
                  <Badge>{e.time}</Badge> {e.action}
                </p>
              ))}
            </div>
          ) : (
            <Empty title="No audit events loaded" />
          ))}
        {tab === "Configuration" && (
          <div className="settings-content">
            <Badge tone="amber">Paper execution only</Badge>
            <p>
              Deployment configuration is managed through server environment
              variables. Secrets and trading mode cannot be changed in the
              browser.
            </p>
          </div>
        )}
      </Panel>
    </>
  );
}
