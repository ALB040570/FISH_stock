import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import 'leaflet/dist/leaflet.css'
import * as Icons from '@element-plus/icons-vue'
import App from './App.vue'
import router from './router'
import i18n, { elLocale } from './i18n'
import '@fontsource/inter/400.css'
import '@fontsource/inter/500.css'
import '@fontsource/inter/600.css'
import './assets/app.css'

const app = createApp(App)
for (const [k, c] of Object.entries(Icons)) app.component(k, c)
app.use(createPinia()).use(router).use(i18n).use(ElementPlus, { locale: elLocale() })
app.mount('#app')
