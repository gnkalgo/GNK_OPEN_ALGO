import { test, expect } from "@playwright/test";
test("server mode authenticates through API boundary and hides demo authority controls", async ({
  page,
}) => {
  let loggedIn = false;
  const user = {
    name: "Server Trader",
    email: "server@example.com",
    role: "trader",
  };
  const requests: string[] = [];
  await page.route("**/api/v1/gnkalgo/**", async (route) => {
    const request = route.request(),
      path = new URL(request.url()).pathname;
    requests.push(path);
    if (path.endsWith("/session") && !loggedIn)
      return route.fulfill({
        status: 401,
        json: { detail: { message: "Sign in" } },
      });
    if (path.endsWith("/auth/login")) {
      loggedIn = true;
      return route.fulfill({ json: { session: user, csrf: "fictional-csrf" } });
    }
    if (path.endsWith("/workspace"))
      return route.fulfill({
        json: {
          session: user,
          broker: "Connected",
          balance: 245680.5,
          orders: [],
          strategies: [],
          watchlist: [],
          activity: [],
          scenario: "normal",
        },
      });
    return route.fulfill({ json: {} });
  });
  await page.goto("/login");
  await page.getByLabel("Email address").fill("server@example.com");
  await page
    .getByLabel("Password", { exact: true })
    .fill("FictionalServer!2026");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Broker connections" }),
  ).toBeVisible();
  await expect(page.getByText("Demo scenarios", { exact: true })).toHaveCount(
    0,
  );
  await expect(page.getByLabel("Preview role (demo only)")).toHaveCount(0);
  expect(requests).toContain("/api/v1/gnkalgo/auth/login");
  expect(requests).toContain("/api/v1/gnkalgo/workspace");
});
test("verification token is consumed from fragment and removed from address bar", async ({
  page,
}) => {
  let consumed = "";
  await page.route("**/api/v1/gnkalgo/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/session"))
      return route.fulfill({
        status: 401,
        json: { detail: { message: "Sign in" } },
      });
    if (path.endsWith("/auth/verify"))
      consumed = route.request().postDataJSON().token;
    return route.fulfill({ json: {} });
  });
  await page.goto(
    "/verify-email#token=fictional-single-use-token-for-transport-test",
  );
  await expect(page).toHaveURL(/verify-email$/);
  await page.getByRole("button", { name: "Verify email link" }).click();
  await expect(
    page.getByRole("heading", { name: "Welcome back." }),
  ).toBeVisible();
  expect(consumed).toBe("fictional-single-use-token-for-transport-test");
});

test("server account controls save paper limits with the session CSRF token", async ({page}) => {
  const policy = {max_order_value:"1000.00",max_daily_value:"5000.00",max_quantity:5,halted:false,currency:"INR",scope:"paper",day_timezone:"Asia/Kolkata",daily_value_used:"0",emergency_stop:false,live_orders_enabled:false};
  let saved = false;
  await page.route("**/api/v1/gnkalgo/**", async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const user = {name:"Fixture Trader",email:"fixture@example.com",role:"trader"};
    if (path.endsWith("/session")) return route.fulfill({json:{session:user,csrf:"fictional-controls-csrf"}});
    if (path.endsWith("/workspace")) return route.fulfill({json:{session:user,broker:"Disconnected",balance:1000,orders:[],strategies:[],activity:[],watchlist:[],scenario:"normal"}});
    if (path.endsWith("/platform")) return route.fulfill({json:{execution:"paper-only",live_orders_enabled:false,capabilities:[],release_blockers:[]}});
    if (path.endsWith("/risk-policy")) {
      if (request.method() === "PUT") {
        expect(request.headers()["x-csrf-token"]).toBe("fictional-controls-csrf");
        expect(request.postDataJSON()).toEqual({max_order_value:"1000.00",max_daily_value:"5000.00",max_quantity:5,halted:true});
        saved = true;
        policy.halted = true;
      }
      return route.fulfill({json:policy});
    }
    return route.fulfill({status:404,json:{detail:{message:"Unknown fixture endpoint"}}});
  });
  await page.goto("/app/controls");
  await expect(page.getByLabel("Maximum order value (INR)")).toHaveValue("1000.00");
  await page.getByLabel("Halt new paper orders").check();
  await page.getByRole("button",{name:"Save account limits"}).click();
  await expect(page.getByRole("status")).toContainText("Account limits saved");
  expect(saved).toBe(true);
  await expect(page.getByText("Live execution locked")).toBeVisible();
});
