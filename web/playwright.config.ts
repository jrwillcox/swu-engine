import { defineConfig, devices } from "@playwright/test";

// E2E config. Playwright always starts its own backend and Vite server, on ports
// reserved for e2e, and fails if either port is busy rather than reusing
// whatever is listening there. The backend keeps its accounts in test-results/
// (emptied each run), never in data/users.json. testDir is isolated to tests/e2e so Playwright never
// tries to run the vitest unit files under tests/.
// Relative to the backend's cwd, the repo root.
const py = process.platform === "win32" ? ".venv\\Scripts\\python.exe" : ".venv/bin/python";
const apiPort = process.env.SWU_E2E_API_PORT ?? "8090";
const webPort = process.env.SWU_E2E_WEB_PORT ?? "5190";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 60_000,
  fullyParallel: false,
  reporter: "list",
  use: {
    baseURL: `http://localhost:${webPort}`,
    ...devices["Desktop Chrome"],
  },
  webServer: [
    {
      command: `${py} -m swu.web --port ${apiPort}`,
      cwd: "..",
      url: `http://127.0.0.1:${apiPort}/api/health`,
      reuseExistingServer: false,
      timeout: 60_000,
      env: { SWU_USERS: "web/test-results/e2e-users.json", SWU_ALLOWED_USERS: "player" },
    },
    {
      command: "npm run dev -- --strictPort",
      url: `http://localhost:${webPort}`,
      reuseExistingServer: false,
      timeout: 60_000,
      env: { SWU_PORT: webPort, SWU_API: `http://127.0.0.1:${apiPort}` },
    },
  ],
});
