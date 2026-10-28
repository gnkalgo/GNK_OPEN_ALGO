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
  await page.route("**/api/gnk/v1/**", async (route) => {
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
  expect(requests).toContain("/api/gnk/v1/auth/login");
  expect(requests).toContain("/api/gnk/v1/workspace");
});
test("verification token is consumed from fragment and removed from address bar", async ({
  page,
}) => {
  let consumed = "";
  await page.route("**/api/gnk/v1/**", async (route) => {
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
