import { defineConfig } from "@playwright/test";
import path from "node:path";

const root = path.resolve(__dirname, "..");
export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 45_000,
  reporter: "list",
  use: {
    baseURL: "http://localhost:3000",
    browserName: "chromium",
    channel: "msedge",
    headless: true,
    viewport: { width: 1440, height: 900 },
    trace: "off",
    screenshot: "only-on-failure",
  },
  webServer: [
    {
      command: '"backend/.venv/Scripts/python.exe" -B -m backend.tests.auth_browser_server',
      cwd: root,
      url: "http://localhost:8001/",
      env: { SPMS_AUTH_BROWSER_ROLLBACK: "1", SPMS_INVITATION_BROWSER_FIXTURES: "1" },
      reuseExistingServer: false,
      timeout: 30_000,
    },
    {
      command: "npm run dev -- --hostname localhost --port 3000",
      url: "http://localhost:3000",
      env: { NEXT_PUBLIC_API_BASE_URL: "http://localhost:8001" },
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
