import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./server-e2e",
  use: {
    baseURL: "http://127.0.0.1:5174",
    trace: "off",
    screenshot: "off",
    video: "off",
  },
  projects: [{ name: "server-desktop", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "npm run dev -- --port 5174",
    url: "http://127.0.0.1:5174",
    env: { VITE_API_MODE: "server" },
    reuseExistingServer: false,
  },
  reporter: "list",
});
