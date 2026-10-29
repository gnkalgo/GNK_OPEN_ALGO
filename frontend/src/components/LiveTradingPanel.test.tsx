import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { LiveTradingPanel } from "./LiveTradingPanel";

test("live trading stays unavailable and the paper mode is explicit", async () => {
  render(
    <MemoryRouter>
      <LiveTradingPanel />
    </MemoryRouter>,
  );
  expect(screen.getByRole("button", { name: "Paper Trading" })).toBeDisabled();
  expect(
    screen.getByRole("button", { name: "Live Trading unavailable" }),
  ).toBeDisabled();
  expect(
    screen.getByText(/does not validate live trading permissions/),
  ).toBeInTheDocument();
  await waitFor(() => {
    expect(screen.getByText("Inactive")).toBeInTheDocument();
  });
  expect(screen.queryByRole("button", { name: "Enable Live Mode" })).toBeNull();
});
