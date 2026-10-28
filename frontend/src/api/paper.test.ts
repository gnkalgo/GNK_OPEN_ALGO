import { paper, validateTicket, type Ticket } from "./paper";
const ticket: Ticket = {
  symbol: "RELIANCE",
  exchange: "NSE",
  product: "Delivery",
  side: "BUY",
  quantity: 2,
  type: "MARKET",
  price: 0,
};
beforeEach(() => {
  paper.resetForTests();
  paper.explore();
});
test.each([0, -1, 1.5, 1001, NaN, Infinity])(
  "rejects invalid quantity %s",
  (quantity) => {
    expect(validateTicket({ ...ticket, quantity })).toMatch(/Quantity/);
  },
);
test("validates exchange, instrument and limit price", () => {
  expect(validateTicket({ ...ticket, exchange: "BSE" })).toMatch(/exchange/);
  expect(validateTicket({ ...ticket, symbol: "FAKE" })).toMatch(/instrument/);
  expect(validateTicket({ ...ticket, type: "LIMIT", price: 0 })).toMatch(
    /price/,
  );
  expect(validateTicket(ticket)).toBeNull();
});
test("idempotency prevents sequential and concurrent duplicate fills", async () => {
  const initial = paper.snapshot().balance;
  await Promise.all([
    paper.submit(ticket, "same-key"),
    paper.submit(ticket, "same-key"),
  ]);
  await paper.submit(ticket, "same-key");
  expect(paper.snapshot().orders).toHaveLength(1);
  expect(paper.snapshot().balance).toBe(initial - 2948.5 * 2);
});
test("rejected orders never change balance or produce fills", async () => {
  paper.scenario("order-rejected");
  const balance = paper.snapshot().balance;
  const order = await paper.submit(ticket, "reject");
  expect(order.status).toBe("Rejected");
  expect(paper.snapshot().balance).toBe(balance);
});
test("insufficient funds reject the paper order", async () => {
  const order = await paper.submit({ ...ticket, quantity: 1000 }, "large");
  expect(order.reason).toMatch(/Insufficient/);
  expect(order.status).toBe("Rejected");
});
test("unknown outcomes block new orders and reconcile exactly once", async () => {
  paper.scenario("order-unknown");
  const initial = paper.snapshot().balance;
  await paper.submit(ticket, "unknown");
  expect(paper.snapshot().balance).toBe(initial);
  await expect(paper.submit(ticket, "duplicate")).rejects.toThrow(/Reconcile/);
  await paper.reconcile("unknown");
  await paper.reconcile("unknown");
  expect(paper.snapshot().balance).toBe(initial - 5897);
  expect(paper.snapshot().orders[0].status).toBe("Filled");
});
test("timeout has no order side effect", async () => {
  paper.scenario("timeout");
  await expect(paper.submit(ticket, "timeout")).rejects.toThrow(/timed out/);
  expect(paper.snapshot().orders).toHaveLength(0);
});
test("disconnected feed and expired broker block execution", async () => {
  paper.scenario("feed-offline");
  await expect(paper.submit(ticket, "feed")).rejects.toThrow(/disconnected/);
  paper.scenario("broker-expired");
  await expect(paper.submit(ticket, "broker")).rejects.toThrow(/reconnect/);
  expect(paper.snapshot().orders).toHaveLength(0);
});
test("lifecycle enforces validation and testing; edits reset validation", async () => {
  const id = await paper.saveStrategy({
    name: "Test",
    symbol: "RELIANCE",
    quantity: 2,
    loss: 500,
    signal: "EMA crossover",
  });
  await expect(paper.transition(id, "Active")).rejects.toThrow(/validation/);
  for (const next of ["Validated", "Tested", "Active"] as const)
    await paper.transition(id, next);
  await expect(
    paper.saveStrategy(
      {
        name: "Edited",
        symbol: "TCS",
        quantity: 2,
        loss: 200,
        signal: "EMA crossover",
      },
      id,
    ),
  ).rejects.toThrow(/Pause/);
  await paper.transition(id, "Paused");
  await paper.transition(id, "Stopped");
  await paper.saveStrategy(
    {
      name: "Edited",
      symbol: "TCS",
      quantity: 2,
      loss: 200,
      signal: "EMA crossover",
    },
    id,
  );
  expect(paper.snapshot().strategies.find((s) => s.id === id)?.status).toBe(
    "Draft",
  );
});
test("registration requires verification and never stores passwords in snapshot", async () => {
  paper.logout();
  await paper.register("Demo", "demo@example.test");
  await expect(
    paper.login("demo@example.test", "PaperDemo!2026"),
  ).rejects.toThrow(/Verify/);
  await paper.verify();
  await paper.login("demo@example.test", "PaperDemo!2026");
  expect(JSON.stringify(paper.snapshot())).not.toContain("PaperDemo!2026");
  paper.logout();
  expect(paper.snapshot().session).toBeNull();
});
