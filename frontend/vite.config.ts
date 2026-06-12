import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Proxy /claims and /health to the FastAPI backend during development
      "/claims": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
});
