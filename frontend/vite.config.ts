import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // Needed for Docker to expose the port
    allowedHosts: ["amoeba.space"], // Fix for Blocked Request
    proxy: {
      // 1. Proxy API requests to the backend container
      "^/api": {
        target: process.env.VITE_BACKEND_URL || "http://backend:8000",
        changeOrigin: true,
        secure: false,
        ws: true,
        xfwd: true,
      },
    },
  },
});
