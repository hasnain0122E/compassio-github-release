import { defineConfig } from "@playwright/test";

// Run against the checked-in local API/web launchers. Never mocks source responses.
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 90_000,
  expect: { timeout: 25_000 },
  outputDir: "../../artifacts/frontend/browser",
  reporter: [["list"], ["json", { outputFile: "../../artifacts/frontend/browser-results.json" }]],
  use: {
    baseURL: process.env.COMPASSIO_WEB_URL ?? "http://127.0.0.1:3000",
    viewport: { width: 1440, height: 1000 },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    launchOptions: process.env.COMPASSIO_BROWSER_PATH
      ? { executablePath: process.env.COMPASSIO_BROWSER_PATH }
      : {},
  },
});
