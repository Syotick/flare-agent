import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// dev 代理：/v1 -> 后端 FastAPI(:8000)，前端无跨域烦恼
export default defineConfig({
  plugins: [react(), tailwindcss()],
  define: {
    // 构建时间戳：前端版本标识，刷新后确认是否加载到最新构建
    __BUILD_TIME__: JSON.stringify(new Date().toISOString()),
  },
  server: {
    port: 5173,
    proxy: {
      "/v1": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          "vendor-react": ["react", "react-dom"],
          "vendor-radix": ["@radix-ui/react-alert-dialog", "@radix-ui/react-dropdown-menu"],
          "vendor-lucide": ["lucide-react"],
          "vendor-ui": ["clsx", "tailwind-merge", "class-variance-authority"],
        },
      },
    },
  },
});
