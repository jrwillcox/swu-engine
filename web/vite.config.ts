/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The frontend talks to the FastAPI backend only over HTTP. In dev, Vite
// proxies /api to the backend so there's no CORS and no shared filesystem
// assumption — exactly what LAN hosting needs.
//
// Port and proxy target are both env-driven, so one config can serve several
// instances side by side:
//   SWU_PORT=5173 → SWU_API=http://127.0.0.1:8000
//   SWU_PORT=5174 → SWU_API=http://127.0.0.1:8001
const port = Number(process.env.SWU_PORT) || 5173;

// Hosts allowed to reach the dev/preview server by *name*. Vite rejects an
// unknown Host header; IP addresses are always allowed, so this only matters when
// a device browses to http://<hostname>:<port>. Set SWU_ALLOWED_HOSTS
// (comma-separated) to your machine's hostname to permit that.
//
// Lower-cased because the browser sends a lower-case Host header and vite's check
// is case-sensitive — a "MYBOX.local" entry would never match a "mybox.local" host.
const allowedHosts = process.env.SWU_ALLOWED_HOSTS?.split(",")
  .map((h: string) => h.trim().toLowerCase())
  .filter(Boolean);

const proxy = {
  "/api": {
    target: process.env.SWU_API ?? "http://127.0.0.1:8000",
    changeOrigin: true,
  },
};

export default defineConfig({
  plugins: [react()],
  server: {
    port,
    // Listen on all interfaces so another device on the LAN (e.g. an iPad on the
    // same Wi-Fi) can open http://<this-PC-ip>:5173. The /api proxy below runs
    // PC-side against the backend, so the backend can stay bound to 127.0.0.1.
    host: true,
    proxy,
    allowedHosts,
  },
  // `vite preview` serves the built bundle. It needs the SAME /api proxy as the
  // dev server, otherwise the built app can't reach the backend.
  preview: {
    port,
    host: true,
    proxy,
    allowedHosts,
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/**/*.test.{ts,tsx}"],
  },
});
