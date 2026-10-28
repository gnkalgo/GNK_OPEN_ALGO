import { server } from "./server";
// Isolated, in-memory simulator. This module never calls a broker or stores credentials.
export type Scenario =
  | "normal"
  | "timeout"
  | "login-failed"
  | "expired-link"
  | "broker-denied"
  | "broker-expired"
  | "feed-offline"
  | "order-rejected"
  | "order-unknown"
  | "session-expired"
  | "loading"
  | "empty";
export type Instrument = {
  symbol: string;
  name: string;
  exchange: "NSE" | "BSE";
  price: number;
  change: number;
  sector: string;
};
export const instruments: Instrument[] = [
  {
    symbol: "RELIANCE",
    name: "Reliance Industries",
    exchange: "NSE",
    price: 2948.5,
    change: 1.24,
    sector: "Energy",
  },
  {
    symbol: "TCS",
    name: "Tata Consultancy Services",
    exchange: "NSE",
    price: 4125.8,
    change: -0.62,
    sector: "Technology",
  },
  {
    symbol: "HDFCBANK",
    name: "HDFC Bank",
    exchange: "NSE",
    price: 1726.35,
    change: 0.85,
    sector: "Banking",
  },
  {
    symbol: "INFY",
    name: "Infosys",
    exchange: "NSE",
    price: 1864.2,
    change: 1.53,
    sector: "Technology",
  },
  {
    symbol: "ICICIBANK",
    name: "ICICI Bank",
    exchange: "NSE",
    price: 1285.4,
    change: 0.93,
    sector: "Banking",
  },
  {
    symbol: "BHARTIARTL",
    name: "Bharti Airtel",
    exchange: "NSE",
    price: 1620.75,
    change: -0.38,
    sector: "Telecom",
  },
];
export type Ticket = {
  symbol: string;
  exchange: string;
  product: string;
  side: "BUY" | "SELL";
  quantity: number;
  type: "MARKET" | "LIMIT";
  price: number;
};
export type Order = Ticket & {
  id: string;
  status: "Filled" | "Rejected" | "Unknown";
  time: string;
  reason?: string;
};
export type Strategy = {
  id: string;
  name: string;
  symbol: string;
  quantity: number;
  loss: number;
  signal: string;
  status: "Draft" | "Validated" | "Tested" | "Active" | "Paused" | "Stopped";
};
export type Session = { name: string; email: string; role: "trader" | "admin" };
export type Snapshot = {
  session: Session | null;
  broker: "Disconnected" | "Connected" | "Expired";
  balance: number;
  orders: Order[];
  strategies: Strategy[];
  activity: string[];
  scenario: Scenario;
  watchlist: string[];
};
const initial = (): Snapshot => ({
  session: null,
  broker: "Disconnected",
  balance: 245680.5,
  orders: [],
  strategies: [
    {
      id: "str-01",
      name: "Nifty momentum",
      symbol: "RELIANCE",
      quantity: 5,
      loss: 1500,
      signal: "EMA crossover",
      status: "Active",
    },
    {
      id: "str-02",
      name: "Opening range breakout",
      symbol: "HDFCBANK",
      quantity: 10,
      loss: 1000,
      signal: "Opening range",
      status: "Paused",
    },
    {
      id: "str-03",
      name: "Mean reversion",
      symbol: "INFY",
      quantity: 5,
      loss: 800,
      signal: "RSI reversal",
      status: "Draft",
    },
  ],
  activity: ["Paper workspace initialized", "Sample strategies loaded"],
  scenario: "normal",
  watchlist: ["RELIANCE", "TCS", "HDFCBANK", "INFY"],
});
let state = initial();
let account: { name: string; email: string; verified: boolean } | null = null;
const listeners = new Set<() => void>();
const requests = new Map<string, Order>();
const emit = (patch: Partial<Snapshot>) => {
  state = { ...state, ...patch };
  listeners.forEach((fn) => fn());
};
const record = (text: string) =>
  emit({ activity: [text, ...state.activity].slice(0, 20) });
export const money = (n: number) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(n);
export function validateTicket(t: Ticket): string | null {
  const instrument = instruments.find((i) => i.symbol === t.symbol);
  if (!instrument || instrument.exchange !== t.exchange)
    return "Select a listed instrument and its exchange.";
  if (
    !["Intraday", "Delivery"].includes(t.product) ||
    !["BUY", "SELL"].includes(t.side) ||
    !["MARKET", "LIMIT"].includes(t.type)
  )
    return "Invalid order parameters.";
  if (!Number.isSafeInteger(t.quantity) || t.quantity < 1 || t.quantity > 1000)
    return "Quantity must be a whole number between 1 and 1,000.";
  if (t.type === "LIMIT" && (!Number.isFinite(t.price) || t.price <= 0))
    return "Enter a valid limit price greater than zero.";
  return null;
}
async function delay() {
  if (!navigator.onLine)
    throw new Error(
      "You are offline. Reconnect before retrying. No action was taken.",
    );
  await new Promise((resolve) =>
    setTimeout(resolve, state.scenario === "loading" ? 1800 : 220),
  );
  if (state.scenario === "timeout")
    throw new Error("Request timed out. No action was taken. Please retry.");
  if (state.scenario === "session-expired" || !state.session) {
    emit({ session: null });
    throw new Error("Session expired. Sign in again.");
  }
}
const demo = {
  subscribe: (fn: () => void) => {
    listeners.add(fn);
    return () => {
      listeners.delete(fn);
    };
  },
  snapshot: () => state,
  scenario: (scenario: Scenario) =>
    emit({
      scenario,
      ...(scenario === "broker-expired" ? { broker: "Expired" as const } : {}),
      ...(scenario === "session-expired" ? { session: null } : {}),
    }),
  async register(name: string, email: string, _password?: string) {
    await new Promise((r) => setTimeout(r, 220));
    account = { name, email, verified: false };
  },
  async verify(_token?: string) {
    if (state.scenario === "expired-link")
      throw new Error("This email link has expired. Request a new link.");
    if (!account)
      throw new Error("No pending registration. Create a demo account first.");
    account.verified = true;
  },
  async login(email: string, password: string) {
    await new Promise((r) => setTimeout(r, 220));
    if (state.scenario === "login-failed" || password !== "PaperDemo!2026")
      throw new Error("Email or password is incorrect.");
    if (email !== "trader@gnk.demo" && email !== account?.email)
      throw new Error("Email or password is incorrect.");
    if (email === account?.email && !account?.verified)
      throw new Error("Verify your email before signing in.");
    emit({
      session: {
        name: account?.email === email ? account.name : "Alex Morgan",
        email,
        role: "trader",
      },
    });
  },
  explore() {
    emit({
      session: {
        name: "Alex Morgan",
        email: "trader@gnk.demo",
        role: "trader",
      },
      broker: "Connected",
    });
  },
  logout() {
    state = initial();
    account = null;
    requests.clear();
    listeners.forEach((fn) => fn());
  },
  async connect() {
    await delay();
    if (state.scenario === "broker-denied")
      throw new Error("Broker authorization denied. You can safely try again.");
    emit({ broker: "Connected" });
    record("Paper broker connected");
  },
  async submit(ticket: Ticket, key: string) {
    if (requests.has(key)) return requests.get(key)!;
    await delay();
    if (requests.has(key)) return requests.get(key)!;
    const error = validateTicket(ticket);
    if (error) throw new Error(error);
    if (state.broker !== "Connected")
      throw new Error("Connect or reconnect your paper broker first.");
    if (state.scenario === "feed-offline")
      throw new Error("Market feed disconnected. Reconnect before ordering.");
    if (state.orders.some((o) => o.status === "Unknown"))
      throw new Error(
        "Reconcile the unknown order before placing another order.",
      );
    const price =
      ticket.type === "MARKET"
        ? instruments.find((i) => i.symbol === ticket.symbol)!.price
        : ticket.price;
    const insufficient =
      ticket.side === "BUY" && price * ticket.quantity > state.balance;
    const order: Order = {
      ...ticket,
      price,
      id: key,
      time: new Date().toLocaleTimeString("en-IN"),
      status:
        state.scenario === "order-rejected" || insufficient
          ? "Rejected"
          : state.scenario === "order-unknown"
            ? "Unknown"
            : "Filled",
      reason: insufficient
        ? "Insufficient paper balance"
        : state.scenario === "order-rejected"
          ? "Simulated risk check rejected this order"
          : undefined,
    };
    requests.set(key, order);
    emit({
      orders: [order, ...state.orders],
      balance:
        state.balance -
        (order.status === "Filled"
          ? price * ticket.quantity * (ticket.side === "BUY" ? 1 : -1)
          : 0),
    });
    record(
      `${order.symbol} · ${order.side} ${order.quantity} · ${order.status}`,
    );
    return order;
  },
  async reconcile(id: string) {
    await delay();
    const order = state.orders.find((o) => o.id === id);
    if (!order || order.status !== "Unknown") return;
    const filled = { ...order, status: "Filled" as const };
    requests.set(id, filled);
    emit({
      orders: state.orders.map((o) => (o.id === id ? filled : o)),
      balance:
        state.balance -
        order.price * order.quantity * (order.side === "BUY" ? 1 : -1),
    });
    record("Unknown paper order reconciled as filled");
  },
  async saveStrategy(s: Omit<Strategy, "id" | "status">, id?: string) {
    await delay();
    if (
      !s.name.trim() ||
      s.quantity < 1 ||
      s.quantity > 1000 ||
      !Number.isSafeInteger(s.quantity) ||
      !instruments.some((i) => i.symbol === s.symbol) ||
      s.loss <= 0 ||
      !Number.isFinite(s.loss)
    )
      throw new Error(
        "Name, whole quantity and positive loss limit are required.",
      );
    const old = state.strategies.find((x) => x.id === id);
    if (old?.status === "Active")
      throw new Error("Pause this strategy before editing.");
    const next: Strategy = {
      ...s,
      id: id ?? crypto.randomUUID(),
      status: "Draft",
    };
    emit({
      strategies: [...state.strategies.filter((x) => x.id !== id), next],
    });
    record(`Strategy saved: ${s.name}`);
    return next.id;
  },
  async transition(id: string, next: Strategy["status"]) {
    await delay();
    const s = state.strategies.find((x) => x.id === id);
    const allowed: Record<Strategy["status"], Strategy["status"][]> = {
      Draft: ["Validated"],
      Validated: ["Tested"],
      Tested: ["Active"],
      Active: ["Paused", "Stopped"],
      Paused: ["Active", "Stopped"],
      Stopped: ["Validated"],
    };
    if (!s || !allowed[s.status].includes(next))
      throw new Error("Complete validation and paper testing first.");
    if (
      next === "Active" &&
      (state.broker !== "Connected" || state.scenario === "feed-offline")
    )
      throw new Error("A connected paper broker and feed are required.");
    emit({
      strategies: state.strategies.map((x) =>
        x.id === id ? { ...x, status: next } : x,
      ),
    });
    record(`${s.name} · ${next}`);
  },
  toggleWatch(symbol: string) {
    emit({
      watchlist: state.watchlist.includes(symbol)
        ? state.watchlist.filter((x) => x !== symbol)
        : [...state.watchlist, symbol],
    });
  },
  async profile(name: string) {
    await delay();
    if (!name.trim()) throw new Error("Name is required.");
    emit({ session: { ...state.session!, name } });
    record("Profile updated");
  },
  previewRole(role: Session["role"]) {
    if (state.session) emit({ session: { ...state.session, role } });
  },
  resetForTests() {
    state = initial();
    account = null;
    requests.clear();
    listeners.forEach((fn) => fn());
  },
};

export const serverMode = import.meta.env.VITE_API_MODE === "server";
export const paper = serverMode
  ? server
  : {
      ...demo,
      initialize: async () => {},
      forgot: async (_email: string) => {},
      resend: async (_email: string) => {},
      reset: async (_token: string, _password: string) => {},
    };
