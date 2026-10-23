import { expect, test } from "@playwright/test";

test("Companion serves its jobs and settings from the actual backend", async ({ page, request }) => {
  const jobs = await request.get("/companion-api/jobs");
  expect(jobs.ok()).toBe(true);
  expect(await jobs.json()).toEqual([]);
  const settings = await request.get("/companion-api/studio-settings");
  expect(settings.ok()).toBe(true);
  await page.goto("/");
  await page.getByRole("button", { name: "设置", exact: true }).click();
  await expect(page.getByRole("heading", { name: "设置中心" })).toBeVisible();
  await page.getByRole("button", { name: "返回工作区" }).click();
  await expect(page.getByRole("button", { name: "设置", exact: true })).toBeVisible();
});
