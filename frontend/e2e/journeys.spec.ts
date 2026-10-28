import { test, expect, type Page } from "@playwright/test";
async function explore(page: Page) {
  await page.goto("/");
  await page.getByRole("button", { name: "Explore paper workspace" }).click();
  await expect(
    page.getByRole("heading", { name: "Good morning, Alex." }),
  ).toBeVisible();
}
async function go(page: Page, path: string) {
  await page.evaluate((path) => {
    window.history.pushState({}, "", path);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }, path);
}
async function scenario(page: Page, value: string) {
  const details = page.locator(".demo-lab");
  if (!(await details.getAttribute("open")))
    await details.locator("summary").click();
  await page.getByLabel("Demo scenario").selectOption(value);
  if ((await details.count()) && (await details.getAttribute("open")) !== null)
    await details.locator("summary").click();
}
async function order(page: Page) {
  await go(page, "/app/orders/new?symbol=RELIANCE");
  await page.getByLabel("Quantity", { exact: true }).fill("2");
  await page
    .getByRole("button", { name: "Review paper order", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Confirm paper order", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Order book", exact: true }),
  ).toBeVisible();
}
test("complete registration to paper order, review, profile and logout journey", async ({
  page,
  isMobile,
}) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Build your trading edge" }).click();
  await page.getByLabel("Full name").fill("Jamie Demo");
  await page.getByLabel("Email address").fill("jamie@example.test");
  await page.getByLabel("Demo password").fill("PaperDemo!2026");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Create account" }).click();
  await page
    .getByRole("button", { name: "Simulate verification link" })
    .click();
  await page.getByLabel("Email address").fill("jamie@example.test");
  await page.getByLabel("Demo password").fill("PaperDemo!2026");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page
    .getByRole("button", { name: "Connect paper broker", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Approve simulated authorization" })
    .click();
  await page.getByRole("link", { name: "Go to dashboard" }).click();
  await expect(
    page.getByRole("heading", { name: "Good morning, Jamie." }),
  ).toBeVisible();
  if (isMobile) await page.getByRole("button", { name: "Open menu" }).click();
  await page.getByRole("link", { name: "Markets", exact: true }).click();
  await page.getByLabel("Search symbols").fill("Reliance");
  await page
    .getByRole("button", { name: "RELIANCE Reliance Industries · NSE" })
    .click();
  await page.getByRole("link", { name: "Create paper order" }).click();
  await page.getByLabel("Quantity", { exact: true }).fill("2");
  await page
    .getByRole("button", { name: "Review paper order", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText("BUY 2 × RELIANCE");
  await page.getByRole("button", { name: "Confirm paper order" }).click();
  await expect(
    page.getByRole("cell", { name: "Filled", exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Review trade book" }).click();
  await expect(page.locator("tbody")).toContainText("RELIANCE");
  await page.getByRole("link", { name: "Review positions" }).click();
  await expect(page.locator("tbody")).toContainText("RELIANCE");
  if (isMobile) await page.getByRole("button", { name: "Open menu" }).click();
  await page.getByRole("link", { name: "Settings", exact: true }).click();
  await page.getByLabel("Full name").fill("Jamie Updated");
  await page.getByRole("button", { name: "Save profile" }).click();
  await expect(page.getByRole("status")).toContainText("Profile saved");
  if (isMobile) await page.getByRole("button", { name: "Open menu" }).click();
  await page.getByRole("button", { name: "Logout", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Welcome back." }),
  ).toBeVisible();
  await page.goBack();
  await expect(page).toHaveURL(/login/);
});
test("strategy lifecycle: create, configure, validate, paper test, activate, monitor, pause and stop", async ({
  page,
}) => {
  await explore(page);
  await go(page, "/app/strategies");
  await page.getByRole("link", { name: "Create strategy" }).click();
  await page.getByLabel("Strategy name").fill("Momentum demo");
  await page.getByLabel("Quantity", { exact: true }).fill("3");
  await page.getByRole("button", { name: "Save configuration" }).click();
  await page.getByRole("button", { name: "Validate configuration" }).click();
  await page.getByRole("button", { name: "Run paper test" }).click();
  await expect(page.getByRole("status")).toContainText("Paper test passed");
  await page.getByRole("button", { name: "Activate paper strategy" }).click();
  await page.getByRole("button", { name: "Confirm activation" }).click();
  await expect(
    page.getByRole("heading", { name: "Your paper strategy is active." }),
  ).toBeVisible();
  await expect(page.getByLabel("Strategy name")).toBeDisabled();
  await page.getByRole("button", { name: "Pause strategy" }).click();
  await page.getByRole("button", { name: "Stop strategy" }).click();
  await page.getByRole("button", { name: "Confirm stop" }).click();
  await expect(page.getByRole("status")).toContainText("stopped successfully");
});
test("invalid forms and failed login", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email address").fill("invalid");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  expect(
    await page
      .getByLabel("Email address")
      .evaluate((e: HTMLInputElement) => e.validity.valid),
  ).toBe(false);
  await page.getByLabel("Email address").fill("trader@gnk.demo");
  await page.getByLabel("Demo password").fill("WrongPassword2026");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("incorrect");
});
test("expired verification link can be renewed", async ({ page }) => {
  await page.goto("/register");
  await page.getByLabel("Full name").fill("Demo Test");
  await page.getByLabel("Email address").fill("demo@example.test");
  await page.getByLabel("Demo password").fill("PaperDemo!2026");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Create account" }).click();
  await scenario(page, "expired-link");
  await page
    .getByRole("button", { name: "Simulate verification link" })
    .click();
  await expect(page.getByRole("alert")).toContainText("expired");
  await page.getByRole("button", { name: "Request a new demo link" }).click();
  await page
    .getByRole("button", { name: "Simulate verification link" })
    .click();
  await expect(page).toHaveURL(/login/);
});
test("reset links expire and valid demo recovery succeeds", async ({
  page,
}) => {
  await page.goto("/reset-password");
  await page.getByLabel("Demo password").fill("PaperDemo!2026");
  await page.getByRole("button", { name: "Reset demo password" }).click();
  await expect(page.getByRole("alert")).toContainText("expired");
  await page.getByRole("link", { name: "Sign in", exact: true }).click();
  await page.getByRole("link", { name: "Forgot password?" }).click();
  await expect(
    page.getByRole("heading", { name: "Forgot your password?" }),
  ).toBeVisible();
  await page.getByLabel("Email address").fill("trader@gnk.demo");
  await page.getByRole("button", { name: "Request reset link" }).click();
  await page.getByRole("link", { name: "Open simulated reset link" }).click();
  await expect(
    page.getByRole("heading", { name: "A fresh start." }),
  ).toBeVisible();
  await page.getByLabel("Demo password").fill("PaperDemo!2026");
  await page.getByRole("button", { name: "Reset demo password" }).click();
  await expect(page.getByRole("status")).toContainText("reset complete");
});
test("denied authorization and callback error permit retry", async ({
  page,
}) => {
  await explore(page);
  await scenario(page, "broker-expired");
  await go(page, "/app/brokers");
  await page.getByRole("button", { name: "Reconnect paper broker" }).click();
  await page.getByRole("link", { name: "Deny authorization" }).click();
  await expect(
    page.getByRole("alert").filter({ hasText: "denied" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Return to connections" }).click();
  await scenario(page, "broker-denied");
  await page.getByRole("button", { name: "Reconnect paper broker" }).click();
  await page
    .getByRole("button", { name: "Approve simulated authorization" })
    .click();
  await expect(
    page.getByRole("alert").filter({ hasText: "denied" }),
  ).toBeVisible();
  await scenario(page, "normal");
  await page
    .getByRole("button", { name: "Approve simulated authorization" })
    .click();
  await expect(page.getByRole("status")).toContainText(
    "connected successfully",
  );
});
test("expired broker blocks entry and reconnect restores it", async ({
  page,
}) => {
  await explore(page);
  await scenario(page, "broker-expired");
  await go(page, "/app/orders/new");
  await expect(
    page.getByRole("button", { name: "Review paper order" }),
  ).toBeDisabled();
  await page
    .getByRole("link", { name: "Connect broker →", exact: true })
    .click();
  await page.getByRole("button", { name: "Reconnect paper broker" }).click();
  await page
    .getByRole("button", { name: "Approve simulated authorization" })
    .click();
  await page.getByRole("link", { name: "Go to dashboard" }).click();
  await page.getByRole("link", { name: "New paper order" }).click();
  await expect(
    page.getByRole("button", { name: "Review paper order" }),
  ).toBeEnabled();
});
test("disconnected feed blocks orders and recovers", async ({ page }) => {
  await explore(page);
  await scenario(page, "feed-offline");
  await go(page, "/app/orders/new");
  await expect(
    page.getByRole("button", { name: "Review paper order" }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Reconnect feed" }).click();
  await expect(
    page.getByRole("button", { name: "Review paper order" }),
  ).toBeEnabled();
});
test("API timeout is recoverable without duplicate submission", async ({
  page,
}) => {
  await explore(page);
  await go(page, "/app/orders/new");
  await scenario(page, "timeout");
  await page
    .getByRole("button", { name: "Review paper order", exact: true })
    .click();
  await page.getByRole("button", { name: "Confirm paper order" }).click();
  await expect(page.getByRole("alert")).toContainText("timed out");
  await page.getByRole("button", { name: "Edit order" }).click();
  await scenario(page, "normal");
  await page
    .getByRole("button", { name: "Review paper order", exact: true })
    .click();
  await page.getByRole("button", { name: "Confirm paper order" }).click();
  await expect(page.locator("tbody tr")).toHaveCount(1);
});
test("rejected orders have reason and no positions", async ({ page }) => {
  await explore(page);
  await scenario(page, "order-rejected");
  await order(page);
  await expect(page.locator("tbody")).toContainText("Rejected");
  await expect(page.locator("tbody")).toContainText("risk check");
  await go(page, "/app/positions");
  await expect(
    page.getByRole("heading", { name: "No open paper positions" }),
  ).toBeVisible();
});
test("unknown orders require reconciliation before another order", async ({
  page,
}) => {
  await explore(page);
  await scenario(page, "order-unknown");
  await order(page);
  await expect(page.locator("tbody")).toContainText("Unknown");
  await go(page, "/app/orders/new");
  await page
    .getByRole("button", { name: "Review paper order", exact: true })
    .click();
  await page.getByRole("button", { name: "Confirm paper order" }).click();
  await expect(page.getByRole("alert")).toContainText("Reconcile");
  await page.getByRole("button", { name: "Edit order" }).click();
  await go(page, "/app/orders");
  await page.getByRole("button", { name: "Reconcile status" }).click();
  await expect(page.locator("tbody")).toContainText("Filled");
  await expect(page.locator("tbody tr")).toHaveCount(1);
});
test("protected routes, refresh and unauthorized admin access", async ({
  page,
}) => {
  await page.goto("/app/dashboard");
  await expect(page).toHaveURL(/login/);
  await explore(page);
  await go(page, "/app/admin");
  await expect(
    page.getByRole("heading", { name: "Access denied" }),
  ).toBeVisible();
  await page.reload();
  await expect(page).toHaveURL(/login/);
});
test("session expiration redirects and explains recovery", async ({ page }) => {
  await explore(page);
  await scenario(page, "session-expired");
  await expect(page).toHaveURL(/login/);
  await expect(page.getByRole("alert")).toContainText("Session expired");
});
test("loading, empty, watchlist and chart controls", async ({ page }) => {
  await explore(page);
  await scenario(page, "loading");
  await expect(page.getByRole("status")).toContainText("Loading");
  await page.getByRole("button", { name: "1W", exact: true }).click();
  await expect(
    page.getByRole("img", { name: "Fictional 1W performance chart" }),
  ).toBeVisible();
  await scenario(page, "empty");
  await go(page, "/app/markets");
  await expect(
    page.getByRole("heading", { name: "No instruments found" }),
  ).toBeVisible();
  await scenario(page, "normal");
  await page
    .getByRole("button", { name: "Remove RELIANCE from watchlist" })
    .click();
  await page.getByRole("button", { name: "Watchlist", exact: true }).click();
  await expect(page.locator("tbody")).not.toContainText("RELIANCE");
});
test("responsive shell, Back and keyboard dialog recovery", async ({
  page,
  isMobile,
}) => {
  await explore(page);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  if (isMobile) {
    await page.getByRole("button", { name: "Open menu" }).click();
    await expect(
      page.getByRole("navigation", { name: "Main navigation" }),
    ).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.locator(".sidebar")).not.toHaveClass(/mobile-open/);
  } else {
    await page.getByRole("button", { name: "Collapse sidebar" }).click();
    await expect(page.locator(".app-shell")).toHaveClass(/collapsed/);
  }
  await page.getByRole("link", { name: "New paper order" }).click();
  await page
    .getByRole("button", { name: "Review paper order", exact: true })
    .click();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Review paper order", exact: true }),
  ).toBeFocused();
  await page.goBack();
  await expect(
    page.getByRole("heading", { name: "Good morning, Alex." }),
  ).toBeVisible();
});
test("admin preview exposes user, status, audit and configuration screens", async ({
  page,
}) => {
  await explore(page);
  const lab = page.locator(".demo-lab");
  await lab.locator("summary").click();
  await page.getByLabel("Preview role (demo only)").selectOption("admin");
  await lab.locator("summary").click();
  await go(page, "/app/admin");
  await page.getByRole("button", { name: "Suspend demo user" }).click();
  await expect(page.getByText("Suspended", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "System status", exact: true })
    .click();
  await expect(page.getByText("Simulator operational")).toBeVisible();
  await page.getByRole("button", { name: "Audit events", exact: true }).click();
  await expect(page.getByText("Demo event").first()).toBeVisible();
  await page
    .getByRole("button", { name: "Configuration", exact: true })
    .click();
  await page.getByRole("checkbox").check();
  await expect(page.getByRole("status")).toContainText("Maintenance preview");
});
