// Общий запуск приложения кабинета или страницы входа (точки входа — src/entries/*.js).
import { createApp, h } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import 'leaflet/dist/leaflet.css'
import * as Icons from '@element-plus/icons-vue'
import App from './App.vue'
import i18n, { elLocale } from './i18n'
import '@fontsource/inter/400.css'
import '@fontsource/inter/500.css'
import '@fontsource/inter/600.css'
import './assets/app.css'
import { initTheme } from './theme'
import { useAuth } from './store/auth'
import { request } from './api'
import { cabinet, cabinetOf, canEnter, hardGo, legacyToNew, setCurrentCabinet } from './cabinets'

export const view = (n) => () => import(`./views/${n}.vue`)
const Empty = { render: () => h('div') }

/** Маршруты справки внутри кабинета. */
export const helpRoutes = (base) => [{ path: base + 'help/:id?', component: view('Help') }]

/**
 * Адрес вне маршрутов приложения: старый адрес → новый; адрес другого кабинета — переход с перезагрузкой;
 * неизвестный адрес своего кабинета — его главная.
 */
export function leaveTo(own, to) {
  const target = legacyToNew(to.fullPath) || to.fullPath
  const cab = cabinetOf(target)
  if (own && cab && cab.key === own.key) return target === to.fullPath ? own.base : target
  if (!own && !cab) return '/'
  hardGo(target)
  return false
}

export function makeRouter(key, routes) {
  const own = key ? cabinet(key) : null
  const router = createRouter({
    history: createWebHistory(),
    routes: [...routes, { path: '/:pathMatch(.*)*', component: Empty, beforeEnter: (to) => leaveTo(own, to) }],
  })
  router.beforeEach((to) => {
    const auth = useAuth()
    if (to.meta.public) return true
    if (!auth.loggedIn) { hardGo('/login?next=' + encodeURIComponent(to.fullPath)); return false }
    // перенесённый экран (например, каталог из «Администрирования» в «Расчёты», № 66) — сразу на новый адрес,
    // даже если в прежний кабинет роль не входит
    const moved = !to.matched.length || to.matched[0].path === '/:pathMatch(.*)*' ? legacyToNew(to.fullPath) : null
    if (moved && moved !== to.fullPath) return leaveTo(own, to)
    if (own && !canEnter(own, auth.role)) { hardGo('/'); return false }
    if (to.meta.perm && !auth.can(to.meta.perm)) return own ? own.base : '/'
    return true
  })
  return router
}

/** При открытии приложения — свежий профиль: имя или фото мог изменить администратор (решение № 58). */
export async function refreshProfile() {
  const auth = useAuth()
  if (!auth.loggedIn) return
  try { auth.setUser(await request('users', '/auth/me')) } catch (e) { /* нет связи — остаётся сохранённый профиль */ }
}

export function boot(key, routes) {
  setCurrentCabinet(key)
  initTheme()
  const app = createApp(App)
  for (const [k, c] of Object.entries(Icons)) app.component(k, c)
  app.use(createPinia())
  app.use(makeRouter(key, routes)).use(i18n).use(ElementPlus, { locale: elLocale() })
  app.mount('#app')
  refreshProfile()
  return app
}
