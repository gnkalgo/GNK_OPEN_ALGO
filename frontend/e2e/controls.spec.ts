import { test, expect } from "@playwright/test";
test("account control center keeps demo controls disabled and live execution locked", async ({page}, info) => {
  await page.goto("/");
  await page.getByRole("button", {name:"Explore paper workspace"}).click();
  await page.evaluate(() => {history.pushState({}, "", "/app/controls");dispatchEvent(new PopStateEvent("popstate"));});
  await expect(page.getByRole("heading",{name:"Control center",exact:true})).toBeVisible();
  await expect(page.getByRole("button",{name:"Save account limits"})).toBeDisabled();
  await expect(page.getByText("Live execution locked")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({path:`../docs/screenshots/${info.project.name}-controls.png`,fullPage:true});
});
