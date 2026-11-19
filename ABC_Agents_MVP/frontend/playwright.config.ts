import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  use: {
    baseURL: process.env.ABC_WEB_URL ?? 'http://127.0.0.1:8000',
    launchOptions: { executablePath: process.env.ABC_CHROMIUM || undefined },
  },
});
