import React, { Component, type ErrorInfo, type ReactNode } from "react";
import ReactDOM from "react-dom/client";
import {
  BrowserRouter,
  Link,
  Navigate,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import { Shell } from "./components/Shell";
import Landing from "./pages/Landing";
import Auth from "./pages/Auth";
import ControlCenter from "./pages/ControlCenter";
import Dashboard from "./pages/Dashboard";
import Markets from "./pages/Markets";
import Brokers from "./pages/Brokers";
import { Books, OrderEntry } from "./pages/Orders";
import { StrategyEditor, StrategyList } from "./pages/Strategies";
import Settings, { Admin, Help } from "./pages/Settings";
import "./styles.css";
import { paper } from "./api/paper";
class ErrorBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch(_error: Error, _info: ErrorInfo) {
    /* Do not log account or form data. */
  }
  render() {
    return this.state.failed ? (
      <div className="fatal-error">
        <h1>Something interrupted your workspace.</h1>
        <p>
          Reload to start a new paper session. No real orders were submitted.
        </p>
        <button className="button primary" onClick={() => location.reload()}>
          Reload workspace
        </button>
      </div>
    ) : (
      this.props.children
    );
  }
}
function App() {
  const [ready, setReady] = React.useState(false);
  React.useEffect(() => {
    void paper.initialize().finally(() => setReady(true));
  }, []);
  const loc = useLocation();
  React.useEffect(() => {
    document.title = `GNK ALGO | ${loc.pathname === "/" ? "Intelligence Behind Every Trade" : loc.pathname.split("/").pop()?.replace(/-/g, " ")}`;
    window.scrollTo(0, 0);
  }, [loc.pathname]);
  if (!ready)
    return (
      <div className="fatal-error" role="status">
        Loading GNK ALGO workspace…
      </div>
    );
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Auth key="login" kind="login" />} />
      <Route
        path="/register"
        element={<Auth key="register" kind="register" />}
      />
      <Route
        path="/verify-email"
        element={<Auth key="verify" kind="verify" />}
      />
      <Route
        path="/forgot-password"
        element={<Auth key="forgot" kind="forgot" />}
      />
      <Route
        path="/reset-password"
        element={<Auth key="reset" kind="reset" />}
      />
      <Route path="/app" element={<Shell />}>
        <Route index element={<Navigate to="dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="controls" element={<ControlCenter />} />
        <Route path="markets" element={<Markets />} />
        <Route path="brokers" element={<Brokers />} />
        <Route path="brokers/callback" element={<Brokers callback />} />
        <Route path="orders/new" element={<OrderEntry />} />
        <Route path="orders" element={<Books view="orders" />} />
        <Route path="trades" element={<Books view="trades" />} />
        <Route path="positions" element={<Books view="positions" />} />
        <Route path="portfolio" element={<Books view="portfolio" />} />
        <Route path="strategies" element={<StrategyList />} />
        <Route
          path="strategies/new"
          element={<StrategyEditor key="new" create />}
        />
        <Route path="strategies/:id" element={<StrategyEditor />} />
        <Route path="profile" element={<Settings />} />
        <Route path="admin" element={<Admin />} />
        <Route path="help" element={<Help />} />
      </Route>
      <Route
        path="*"
        element={
          <div className="fatal-error">
            <h1>Page not found</h1>
            <p>This route isn’t part of the GNK ALGO workspace.</p>
            <Link className="button primary" to="/">
              Back to home
            </Link>
          </div>
        }
      />
    </Routes>
  );
}
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </ErrorBoundary>
  </React.StrictMode>,
);
