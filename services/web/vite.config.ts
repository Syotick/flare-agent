import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// dev 代理：/v1 -> 后端 FastAPI(:8000)，前端无跨域烦恼
export default defineConfig({
  plugins: [react(), tailwindcss()],
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
