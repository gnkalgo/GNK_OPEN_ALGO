import { test, expect } from "@playwright/test";
import { mkdir } from "node:fs/promises";
test("landing and dashboard visual artifacts; route layouts have no horizontal overflow", async ({
  page,
}, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await mkdir("../docs/screenshots", { recursive: true });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /Intelligence behind/ }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: `../docs/screenshots/${testInfo.project.name}-landing.png`,
    fullPage: true,
  });
  await page.getByRole("button", { name: "Explore paper workspace" }).click();
  await expect(
    page.getByRole("heading", { name: "Good morning, Alex." }),
  ).toBeVisible();
  const layout = await page.evaluate(() => {
    const sidebar = document.querySelector(".sidebar")!.getBoundingClientRect();
    const workspace = document
      .querySelector(".workspace")!
      .getBoundingClientRect();
    const heading = document.querySelector("main h1")!.getBoundingClientRect();
    return {
      sidebarRight: sidebar.right,
      workspaceLeft: workspace.left,
      headingLeft: heading.left,
      sidebarWidth: sidebar.width,
      boxSizing: getComputedStyle(document.querySelector(".sidebar")!)
        .boxSizing,
    };
  });
  await testInfo.attach("layout.json", {
    body: JSON.stringify(layout),
    contentType: "application/json",
  });
  if (testInfo.project.name.startsWith("desktop"))
    expect(layout.sidebarRight).toBeLessThanOrEqual(layout.headingLeft);
  await page.screenshot({
    path: `../docs/screenshots/${testInfo.project.name}-dashboard.png`,
    fullPage: true,
  });
  for (const path of [
    "markets",
    "orders/new",
    "orders",
    "positions",
    "portfolio",
    "strategies",
    "profile",
    "admin",
    "help",
  ]) {
    await page.evaluate((path) => {
      history.pushState({}, "", `/app/${path}`);
      dispatchEvent(new PopStateEvent("popstate"));
    }, path);
    await expect(page.locator("main h1")).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
      path,
    ).toBe(true);
  }
  expect(errors).toEqual([]);
});
test("browser offline state blocks mutations and recovers", async ({
  page,
  context,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Explore paper workspace" }).click();
  await page.getByRole("link", { name: "New paper order" }).click();
  await context.setOffline(true);
  await expect(page.getByRole("alert")).toContainText("You are offline");
  await page
    .getByRole("button", { name: "Review paper order", exact: true })
    .click();
  await page.getByRole("button", { name: "Confirm paper order" }).click();
  await expect(page.getByRole("dialog").getByRole("alert")).toContainText(
    "No action was taken",
  );
  await context.setOffline(false);
  await page.getByRole("button", { name: "Confirm paper order" }).click();
  await expect(page.locator("tbody tr")).toHaveCount(1);
});
test("invalid order fields and unsaved strategy edits cannot bypass review", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Explore paper workspace" }).click();
  await page.getByRole("link", { name: "New paper order" }).click();
  await page.getByLabel("Quantity", { exact: true }).fill("0");
  await page
    .getByRole("button", { name: "Review paper order", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByLabel("Quantity", { exact: true }).fill("2");
  await page
    .getByRole("combobox", { name: "Exchange", exact: true })
    .selectOption("BSE");
  await page
    .getByRole("button", { name: "Review paper order", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText("exchange");
  await page.evaluate(() => {
    history.pushState({}, "", "/app/strategies/str-03");
    dispatchEvent(new PopStateEvent("popstate"));
  });
  await expect(
    page.getByRole("heading", { name: "Mean reversion", exact: true }),
  ).toBeVisible();
  await page.getByLabel("Strategy name").fill("Changed rules");
  await page.getByRole("button", { name: "Validate configuration" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Save the modified configuration",
  );
});
