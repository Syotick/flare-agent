import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// dev 代理：/v1 -> 后端 FastAPI(:8000)，前端无跨域烦恼
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/v1": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
