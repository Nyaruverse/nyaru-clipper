import { expect, test } from "@playwright/test";

test("declares Chinese as the document language for the workstation", async ({ page }) => {
  // Given: the workstation is opened in a real browser.
  await page.goto("/");

  // Then: assistive technology and CJK typography receive the product's primary language.
  await expect(page.locator("html")).toHaveAttribute("lang", "zh-CN");
});

test("keeps legacy routes dark while workstation navigation has a three-pixel focus ring", async ({ page }) => {
  // Given: the legacy entry route and the workstation shell in one production-like browser session.
  await page.goto("/");
  const legacyBaseline = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);

  await page.goto("/workstation");
  const queueLink = page.getByRole("link", { name: "处理队列" });

  // When: keyboard focus reaches the workstation queue navigation.
  await queueLink.focus();

  // Then: legacy global styling is intact and focus is the required tokenized 3px outline.
  await expect(queueLink).toBeFocused();
  expect(await page.evaluate(() => getComputedStyle(document.body).backgroundColor)).toBe(legacyBaseline);
  expect(await queueLink.evaluate((link) => getComputedStyle(link).outlineWidth)).toBe("3px");
  expect(await queueLink.evaluate((link) => getComputedStyle(link).outlineStyle)).toBe("solid");
});

test("redirects a legacy task URL to its workstation overview", async ({ page }) => {
  await page.goto("/tasks/task-legacy-compatibility");
  await expect(page).toHaveURL(/\/workstation\/tasks\/task-legacy-compatibility$/);
});

test("returns keyboard focus to the task-creation trigger after closing its drawer", async ({ page }) => {
  await page.goto("/workstation");
  const trigger = page.getByRole("button", { name: "新建任务" });

  await trigger.click();
  await expect(page.getByRole("dialog", { name: "新建任务" })).toBeVisible();
  await page.getByRole("button", { name: "关闭新建任务" }).click();

  await expect(trigger).toBeFocused();
});
