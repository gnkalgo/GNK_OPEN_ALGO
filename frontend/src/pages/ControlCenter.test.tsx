import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

vi.mock("../api/paper", () => ({serverMode: true, money: (value: number) => `INR ${value}`}));
vi.mock("../api/server", () => ({controls: {policy: vi.fn(), platform: vi.fn(), save: vi.fn()}}));
import { controls } from "../api/server";
import ControlCenter from "./ControlCenter";
const policy = {max_order_value:"1000",max_daily_value:"5000",max_quantity:5,halted:false,
  currency:"INR" as const,scope:"paper" as const,day_timezone:"Asia/Kolkata",daily_value_used:"200",emergency_stop:false,live_orders_enabled:false as const};
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(controls.policy).mockResolvedValue(policy);
  vi.mocked(controls.platform).mockResolvedValue({execution:"paper-only",live_orders_enabled:false,capabilities:[{name:"Live broker execution",status:"unavailable"}],release_blockers:[]});
});
test("saves only policy inputs and shows server acknowledgement", async () => {
  vi.mocked(controls.save).mockResolvedValue({...policy,halted:true});
  render(<MemoryRouter><ControlCenter/></MemoryRouter>);
  await screen.findByText(/Used today/);
  fireEvent.click(screen.getByLabelText("Halt new paper orders"));
  fireEvent.click(screen.getByRole("button",{name:"Save account limits"}));
  await waitFor(() => expect(controls.save).toHaveBeenCalledWith({max_order_value:"1000",max_daily_value:"5000",max_quantity:5,halted:true}));
  expect(await screen.findByText(/Account limits saved/)).toBeInTheDocument();
  expect(screen.getByText("Live execution locked")).toBeInTheDocument();
});
test("failure leaves controls disabled until verified reload", async () => {
  vi.mocked(controls.policy).mockRejectedValue(new Error("offline"));
  render(<MemoryRouter><ControlCenter/></MemoryRouter>);
  expect(await screen.findByRole("alert")).toHaveTextContent("could not be loaded");
  expect(screen.getByRole("button",{name:"Save account limits"})).toBeDisabled();
  expect(controls.save).not.toHaveBeenCalled();
});

test("an uncertain save requires a verified reload before another mutation", async () => {
  vi.mocked(controls.save).mockRejectedValue(new Error("response lost"));
  render(<MemoryRouter><ControlCenter/></MemoryRouter>);
  await screen.findByText(/Used today/);
  fireEvent.click(screen.getByRole("button", {name:"Save account limits"}));
  expect(await screen.findByRole("alert")).toHaveTextContent("could not be saved");
  expect(screen.getByRole("button", {name:"Save account limits"})).toBeDisabled();
  expect(screen.queryByText(/Account limits saved/)).not.toBeInTheDocument();
});
