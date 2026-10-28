import { server } from "./server";
afterEach(() => vi.unstubAllGlobals());
test("server session and CSRF remain in memory; mutations use same-origin cookie transport", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({ csrf: "fixture-csrf" }),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        session: {
          name: "Account",
          email: "account@example.com",
          role: "trader",
        },
        broker: "Connected",
        balance: 100,
        orders: [],
        strategies: [],
        watchlist: [],
        activity: [],
        scenario: "normal",
      }),
    })
    .mockResolvedValueOnce({ ok: true, json: async () => ({}) })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        session: {
          name: "Updated",
          email: "account@example.com",
          role: "trader",
        },
      }),
    });
  vi.stubGlobal("fetch", fetchMock);
  await server.initialize();
  await server.profile("Updated");
  expect(fetchMock.mock.calls[2][1]).toMatchObject({
    credentials: "same-origin",
    method: "PUT",
    headers: { "X-CSRF-Token": "fixture-csrf" },
  });
  expect(localStorage.length).toBe(0);
  expect(sessionStorage.length).toBe(0);
});
test("lost order response preserves the same request identifier as Unknown", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockRejectedValue(new TypeError("Network unavailable")),
  );
  const order = await server.submit(
    {
      symbol: "TCS",
      exchange: "NSE",
      product: "Delivery",
      side: "BUY",
      quantity: 1,
      type: "MARKET",
      price: 0,
    },
    "fixture-request",
  );
  expect(order.status).toBe("Unknown");
  expect(order.id).toBe("fixture-request");
  await expect(
    server.submit(
      {
        symbol: "TCS",
        exchange: "NSE",
        product: "Delivery",
        side: "BUY",
        quantity: 1,
        type: "MARKET",
        price: 0,
      },
      "new-request",
    ),
  ).rejects.toThrow(/Reconcile/);
});
test("server-only controls cannot manufacture roles or demo sessions", () => {
  const before = server.snapshot().session;
  server.previewRole();
  expect(server.snapshot().session).toEqual(before);
  expect(() => server.explore()).toThrow(/unavailable/);
});

test("live trading status uses the GNK v1 namespace and reports paper-only execution", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({
      mode: "PAPER",
      live_available: false,
      live_orders_enabled: false,
      execution: "paper-only",
      emergency_stop: false,
      session_status: "INACTIVE",
      last_connection_check: null,
      broker_auth_valid: false,
      risk_limits: null,
      blockers: ["OPENALGO_PER_USER_ISOLATION_UNAVAILABLE"],
      brokers: [],
      session: null,
    }),
  });
  vi.stubGlobal("fetch", fetchMock);
  const status = await server.liveTradingStatus();
  expect(status.live_orders_enabled).toBe(false);
  expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/gnkalgo/trading-mode");
  expect(fetchMock.mock.calls[0][1]).toMatchObject({
    credentials: "same-origin",
    method: "GET",
  });
});
