import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Built assets are served by the FastAPI dashboard (dashboard/main.py mounts
// web/dist). In dev, proxy the live API to the running FastAPI backend.
export default defineConfig({
  plugins: [react()],
  build: { outDir: "dist", emptyOutDir: true },
  server: {
    port: 5173,
    proxy: {
      "/events": { target: "http://localhost:8080", changeOrigin: true },
      "/ask": { target: "http://localhost:8080", changeOrigin: true },
    },
  },
});
