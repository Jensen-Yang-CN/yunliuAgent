import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': '/src'
    }
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true
        // 不再重写路径，保留 /api 前缀，后端路由为 /api/*
      },
      '/muldetect': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
})
