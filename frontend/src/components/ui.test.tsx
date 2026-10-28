import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { Badge, Change, Feedback, Modal } from "./ui";
afterEach(cleanup);
test("feedback announces failures and loading", () => {
  render(<Feedback error="Request timed out" busy />);
  expect(screen.getByRole("alert")).toHaveTextContent("Request timed out");
  expect(screen.getByRole("status")).toHaveTextContent("Processing");
});
test("status and movement remain understandable without color", () => {
  render(
    <>
      <Badge tone="red">Rejected</Badge>
      <Change value={-1.5} />
    </>,
  );
  expect(screen.getByText("Rejected")).toBeVisible();
  expect(screen.getByText("-1.50%")).toBeVisible();
});
test("modal has a named accessible dialog and close control", () => {
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute("open");
  };
  const close = vi.fn();
  render(
    <Modal title="Review paper order" close={close}>
      Details
    </Modal>,
  );
  expect(
    screen.getByRole("dialog", { name: "Review paper order" }),
  ).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Close dialog" }));
  expect(close).toHaveBeenCalledOnce();
});
