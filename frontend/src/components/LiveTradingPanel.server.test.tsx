import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { paper } from "../api/paper";
import { LiveTradingPanel } from "./LiveTradingPanel";

vi.mock("../api/paper", () => ({
  serverMode: true,
  money: (value: number) => String(value),
  paper: { liveTradingStatus: vi.fn() },
}));

test("paper-disabled deployment stays inactive while Dhan readiness is blocked", async () => {
  vi.mocked(paper.liveTradingStatus).mockResolvedValue({
    mode: "DISABLED", paper_trading_enabled: false,
    live_available: false, live_orders_enabled: false, execution: "paper-and-dhan",
    emergency_stop: false, session_status: "INACTIVE", last_connection_check: null,
    broker_auth_valid: false, risk_limits: null,
    blockers: ["DHAN_RECONNECT_REQUIRED"], brokers: [], session: null,
  });
  render(<MemoryRouter><LiveTradingPanel /></MemoryRouter>);
  await waitFor(() => expect(screen.getByText("Trading inactive")).toBeInTheDocument());
  expect(screen.getByRole("button", { name: "Paper trading disabled" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Live Trading unavailable" })).toBeDisabled();
  expect(screen.getByText(/Reconnect Dhan to refresh/)).toBeInTheDocument();
  expect(screen.queryByText("Dhan live session active")).not.toBeInTheDocument();
});
