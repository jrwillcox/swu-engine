import { defineConfig, devices } from "@playwright/test";

// E2E config. The webServers auto-start the backend (venv python) and the Vite
// dev server; `reuseExistingServer` means it latches onto ones you already have
// running. testDir is isolated to tests/e2e so Playwright never tries to run the
// vitest unit files under tests/.
const py = process.platform === "win32" ? "..\\.venv\\Scripts\\python.exe" : "../.venv/bin/python";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 60_000,
  fullyParallel: false,
  reporter: "list",
  use: {
    baseURL: "http://localhost:5173",
    ...devices["Desktop Chrome"],
  },
  webServer: [
    {
      command: `${py} -m swu.web --port 8000`,
      cwd: "..",
      url: "http://127.0.0.1:8000/api/health",
      reuseExistingServer: true,
      timeout: 60_000,
    },
    {
      command: "npm run dev",
      url: "http://localhost:5173",
      reuseExistingServer: true,
      timeout: 60_000,
    },
  ],
});
