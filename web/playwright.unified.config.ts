import {defineConfig} from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  testMatch: '**/unified-queue.spec.ts',
  fullyParallel: false,
  use: {baseURL: process.env.UNIFIED_QA_URL, channel: process.env.PLAYWRIGHT_CHANNEL || 'chrome', trace: 'retain-on-failure'},
});
