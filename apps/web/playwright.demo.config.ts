import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e", testMatch: "demo.spec.ts", workers: 1,
  use: { baseURL: "http://127.0.0.1:3019", launchOptions: process.env.COMPASSIO_BROWSER_PATH ? { executablePath: process.env.COMPASSIO_BROWSER_PATH } : {} },
  webServer: { command: "node node_modules/next/dist/bin/next start --port 3019", url: "http://127.0.0.1:3019", reuseExistingServer: false },
});
