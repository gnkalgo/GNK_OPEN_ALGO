import type { Order, Snapshot, Strategy, Ticket } from "./paper";
const prefix = "/api/v1/gnkalgo";
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}
export type RiskPolicy = {
  max_order_value: string;
  max_daily_value: string;
  max_quantity: number;
  halted: boolean;
  currency: "INR";
  scope: "paper";
  day_timezone: string;
  daily_value_used: string;
  emergency_stop: boolean;
  live_orders_enabled: false;
};
export type PlatformStatus = {
  paper_trading_enabled?: boolean;
  execution: "paper-only" | "paper-and-dhan";
  live_orders_enabled: boolean;
  capabilities: { name: string; status: string }[];
  release_blockers: string[];
};
export const controls = {
  policy: () => request<RiskPolicy>("/risk-policy"),
  platform: () => request<PlatformStatus>("/platform"),
  save: (policy: Pick<RiskPolicy, "max_order_value" | "max_daily_value" | "max_quantity" | "halted">) =>
    request<RiskPolicy>("/risk-policy", "PUT", policy),
};
export type BrokerCode = "dhan" | "fyers" | "zerodha";
export type BrokerProvider = {
  code: BrokerCode;
  name: string;
  configured: boolean;
  connection: {
    account_name: string;
    account_mask: string;
    connected_at: string;
  } | null;
};
export type LiveSessionState =
  | "INACTIVE"
  | "PENDING_CONFIRMATION"
  | "ACTIVE"
  | "SUSPENDED"
  | "EXPIRED"
  | "REVOKED";
export type LiveTradingSession = {
  id: string;
  broker_code: BrokerCode;
  broker_account_mask: string | null;
  status: LiveSessionState;
  created_at: string;
  confirmed_at: string | null;
  activated_at: string | null;
  last_validated_at: string | null;
  expires_at: string;
  ended_at: string | null;
  suspension_reason: string | null;
  broker_auth_valid: boolean;
  live_orders_enabled: boolean;
};
export type LiveTradingStatus = {
  mode: "PAPER" | "LIVE" | "DISABLED";
  paper_trading_enabled?: boolean;
  live_available: boolean;
  live_orders_enabled: boolean;
  execution: "paper-only" | "paper-and-dhan";
  emergency_stop: boolean;
  session_status: LiveSessionState;
  last_connection_check: string | null;
  broker_auth_valid: boolean;
  risk_limits: { max_order_value: string; max_daily_value: string; max_quantity: number } | null;
  blockers: string[];
  brokers: Array<{
    code: BrokerCode;
    name: string;
    account_mask: string;
    account_linked: true;
    broker_auth_valid: boolean;
  }>;
  session: LiveTradingSession | null;
};
let state: Snapshot = {
  session: null,
  broker: "Disconnected",
  balance: 0,
  orders: [],
  strategies: [],
  activity: [],
  scenario: "normal",
  watchlist: [],
};
let csrf = "";
const listeners = new Set<() => void>();
const emit = (patch: Partial<Snapshot>) => {
  state = { ...state, ...patch };
  listeners.forEach((fn) => fn());
};
async function request<T>(
  path: string,
  method = "GET",
  body?: unknown,
  headers: Record<string, string> = {},
): Promise<T> {
  const abort = new AbortController(),
    timeout = setTimeout(() => abort.abort(), 15000);
  try {
    const url = path.startsWith("/api/")
      ? path
      : prefix + path;
    const response = await fetch(url, {
      method,
      credentials: "same-origin",
      cache: "no-store",
      signal: abort.signal,
      headers: {
        "Content-Type": "application/json",
        ...(csrf ? { "X-CSRF-Token": csrf } : {}),
        ...headers,
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
    const data = await response.json();
    if (!response.ok) {
      if (response.status === 401 && path !== "/auth/login")
        emit({ session: null });
      throw new ApiError(
        data.detail?.message ?? "Request failed. Please retry.",
        response.status,
      );
    }
    return data as T;
  } finally {
    clearTimeout(timeout);
  }
}
async function refresh() {
  emit(await request<Snapshot>("/workspace"));
}
export const server = {
  subscribe(fn: () => void) {
    listeners.add(fn);
    return () => {
      listeners.delete(fn);
    };
  },
  snapshot: () => state,
  async initialize() {
    try {
      const data = await request<{ csrf: string }>("/session");
      csrf = data.csrf;
      await refresh();
    } catch {
      emit({ session: null });
    }
  },
  async register(name: string, email: string, password?: string) {
    await request("/auth/register", "POST", { name, email, password });
  },
  async verify(token?: string) {
    await request("/auth/verify", "POST", { token });
  },
  async forgot(email: string) {
    await request("/auth/forgot", "POST", { email });
  },
  async resend(email: string) {
    await request("/auth/resend", "POST", { email });
  },
  async reset(token: string, password: string) {
    await request("/auth/reset", "POST", { token, password });
  },
  async login(email: string, password: string) {
    const data = await request<{ csrf: string }>("/auth/login", "POST", {
      email,
      password,
    });
    csrf = data.csrf;
    await refresh();
  },
  async logout() {
    await request("/auth/logout", "POST");
    csrf = "";
    emit({
      session: null,
      orders: [],
      strategies: [],
      activity: [],
      watchlist: [],
      balance: 0,
      broker: "Disconnected",
    });
  },
  explore() {
    throw new Error("Public demo sessions are unavailable in server mode.");
  },
  async connect() {
    await request("/brokers/paper/connect", "POST");
    await refresh();
  },
  brokers: async () =>
    request<{ providers: BrokerProvider[]; live_orders_enabled: false }>("/brokers"),
  async authorizeBroker(code: BrokerCode) {
    return request<{ authorization_url: string }>(
      `/brokers/${code}/authorization`,
      "POST",
    );
  },
  brokerPending: (token: string) =>
    request<{
      code: BrokerCode;
      name: string;
      account_name: string;
      account_mask: string;
    }>("/brokers/pending", "POST", { token }),
  async confirmBroker(code: BrokerCode, token: string) {
    await request(`/brokers/${code}/confirm`, "POST", { token });
  },
  async disconnectBroker(code: BrokerCode) {
    await request(`/brokers/${code}`, "DELETE");
  },
  liveTradingStatus: () =>
    request<LiveTradingStatus>("/trading-mode"),
  setTradingMode: (mode: "PAPER" | "LIVE") =>
    request<LiveTradingStatus>("/trading-mode", "PUT", { mode }),
  createLiveSession: (broker_code: BrokerCode) =>
    request<{
      session: LiveTradingSession;
      live_available: false;
      live_orders_enabled: false;
      blockers: string[];
    }>("/live-sessions", "POST", { broker_code }),
  confirmLiveSession: (id: string) =>
    request(
      `/live-sessions/${encodeURIComponent(id)}/confirm`,
      "POST",
      { confirmed: true },
    ),
  suspendLiveSession: (id: string) =>
    request(
      `/live-sessions/${encodeURIComponent(id)}/suspend`,
      "POST",
    ),
  resumeLiveSession: (id: string) =>
    request(
      `/live-sessions/${encodeURIComponent(id)}/resume`,
      "POST",
    ),
  endLiveSession: (id: string) =>
    request(
      `/live-sessions/${encodeURIComponent(id)}/end`,
      "POST",
    ),
  activateEmergencyStop: () =>
    request("/emergency-stop", "POST"),
  async submit(ticket: Ticket, key: string) {
    if (state.orders.some((o) => o.status === "Unknown" && o.id !== key))
      throw new Error(
        "Reconcile the unknown order before placing another order.",
      );
    try {
      const result = await request<Order>("/orders", "POST", ticket, {
        "Idempotency-Key": key,
      });
      await refresh();
      return result;
    } catch (e) {
      // A lost response can hide a committed order. Preserve the original request key.
      if (
        e instanceof TypeError ||
        (e instanceof DOMException && e.name === "AbortError") ||
        (e instanceof ApiError && e.status >= 500)
      ) {
        const existing = state.orders.find((o) => o.id === key);
        const unknown: Order = existing ?? {
          ...ticket,
          id: key,
          status: "Unknown",
          time: new Date().toISOString(),
        };
        emit({
          orders: [unknown, ...state.orders.filter((o) => o.id !== key)],
        });
        return unknown;
      }
      throw e;
    }
  },
  async reconcile(key: string) {
    await request(`/orders/${encodeURIComponent(key)}`);
    await refresh();
  },
  async saveStrategy(s: Omit<Strategy, "id" | "status">, id?: string) {
    const data = await request<{ id: string }>(
      id ? `/strategies/${encodeURIComponent(id)}` : "/strategies",
      id ? "PUT" : "POST",
      s,
    );
    await refresh();
    return data.id;
  },
  async transition(id: string, status: Strategy["status"]) {
    await request(`/strategies/${encodeURIComponent(id)}/transition`, "POST", {
      status,
    });
    await refresh();
  },
  async profile(name: string) {
    await request("/profile", "PUT", { name });
    await refresh();
  },
  async toggleWatch(symbol: string) {
    await request(`/watchlist/${encodeURIComponent(symbol)}`, "PUT");
    await refresh();
  },
  scenario() {
    /* No client fixture controls in server mode. */
  },
  previewRole() {
    /* Roles are issued exclusively by the server. */
  },
  resetForTests() {
    /* No server data reset from browser code. */
  },
  adminUsers: () =>
    request<
      Array<{
        id: string;
        name: string;
        email: string;
        role: string;
        enabled: boolean;
      }>
    >("/admin/users"),
  adminStatus: () => request<Record<string, string | number>>("/admin/status"),
  adminAudit: () =>
    request<Array<{ id: string; action: string; time: string }>>(
      "/admin/audit",
    ),
  async adminToggle(id: string, enabled: boolean) {
    await request(`/admin/users/${encodeURIComponent(id)}`, "PATCH", {
      enabled,
    });
  },
};


export type DhanInstrument = {security_id:string; name:string; tick_size:string; lower_limit:string; upper_limit:string};
export type DhanOrder = {id:string; session_id:string; security_id:string; name:string; side:"BUY"; product:"CNC";
  type:"LIMIT"; quantity:number; price:string; status:string; broker_order_id:string|null; filled_quantity:number;
  average_price:string; reason:string|null; created_at:string};
export type DhanPreview = {preview_token:string; expires_in:number; account_mask:string;
  ticket:{security_id:string;name:string;quantity:number;price:string};
  margin:{available:string;required_margin:string;brokerage_estimate:string};mode:"LIVE";side:"BUY";product:"CNC";type:"LIMIT"};
export const dhan = {
  instruments: () => request<{instruments:DhanInstrument[]}>("/dhan/instruments"),
  orders: () => request<{orders:DhanOrder[]}>("/dhan/orders"),
  preview: (body:{session_id:string;security_id:string;quantity:number;price:string}) => request<DhanPreview>("/dhan/orders/preview", "POST", body),
  submit: (preview_token:string, key:string) => request<DhanOrder>("/dhan/orders", "POST", {preview_token,confirmed:true}, {"Idempotency-Key":key}),
  reconcile: (id:string) => request<DhanOrder>(`/dhan/orders/${encodeURIComponent(id)}/reconcile`, "POST"),
};
