import { resolve } from 'node:path'
import { existsSync } from 'node:fs'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// Кабинеты — отдельные точки входа сборки (docs/decisions.md, № 52): dist/<кабинет>/index.html.
// Корневой index.html — вход, выбор кабинета и перенаправление старых адресов.
const CABINETS = ['monitoring', 'input', 'calc', 'design', 'admin']

// В разработке (vite dev) адреса внутри кабинета отдаются его index.html — как в nginx и devgateway.
const cabinetFallback = () => ({
  name: 'fishstock-cabinet-fallback',
  configureServer(server) {
    server.middlewares.use((req, _res, next) => {
      const [path, query = ''] = (req.url || '').split('?')
      const seg = path.split('/')[1]
      const isFile = /\.[a-z0-9]+$/i.test(path) || path.startsWith('/@') || path.startsWith('/src/') || path.startsWith('/node_modules/')
      if (!isFile && !path.startsWith('/api/')) {
        const page = CABINETS.includes(seg) ? `/${seg}/index.html` : '/index.html'
        if (existsSync(resolve(__dirname, '.' + page))) req.url = page + (query ? '?' + query : '')
      }
      next()
    })
  },
})

// В разработке /api проксируется на шлюз (deploy/run_local.py, порт 8080)
export default defineConfig({
  plugins: [vue(), cabinetFallback()],
  appType: 'mpa',
  server: { port: 5173, proxy: { '/api': 'http://127.0.0.1:8080' } },
  build: {
    chunkSizeWarningLimit: 2500,
    rollupOptions: {
      input: Object.fromEntries([['portal', resolve(__dirname, 'index.html')],
        ...CABINETS.map((k) => [k, resolve(__dirname, k, 'index.html')])]),
    },
  },
  test: { environment: 'jsdom' },
})
