import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, /api goes to the FastAPI backend on :8000.
export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // reachable from your phone on the same wifi
    proxy: { "/api": { target: "http://localhost:8000", timeout: 600000, proxyTimeout: 600000 } },
  },
});
