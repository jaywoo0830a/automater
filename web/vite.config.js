import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      "/campaigns": "http://localhost:5000",
      "/sessions": "http://localhost:5000",
    },
  },
});
