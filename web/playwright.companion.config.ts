import { defineConfig } from "@playwright/test";
import main from "./playwright.config";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/companion-release.spec.ts",
  fullyParallel: false,
  use: { ...main.use, baseURL: process.env.COMPANION_SMOKE_URL },
});
