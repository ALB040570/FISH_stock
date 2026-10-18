import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// В разработке /api проксируется на шлюз (deploy/run_local.py, порт 8080)
export default defineConfig({
  plugins: [vue()],
  server: { port: 5173, proxy: { '/api': 'http://127.0.0.1:8080' } },
  build: { chunkSizeWarningLimit: 2500 },
  test: { environment: 'jsdom' },
})
