import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
// import vueDevTools from 'vite-plugin-vue-devtools'  // 与 vite 8 有注入冲突,临时禁用排查

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue()
    // vueDevTools(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    watch: {
      // 集群 inotify 配额被占满时用轮询代替文件监听
      usePolling: true,
      interval: 300
    },
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000', //   /api->http://127.0.0.1:8000/api
        changeOrigin: true
      },
      '/uploads': {
        target: 'http://127.0.0.1:8000', //   /uploads->http://127.0.0.1:8000/uploads
        changeOrigin: true
      }
    }
  }
})
