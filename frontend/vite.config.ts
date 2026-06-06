import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    manifest: true
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8001",
      "/data": "http://127.0.0.1:8001",
      "/static": "http://127.0.0.1:8001"
    }
  }
});
