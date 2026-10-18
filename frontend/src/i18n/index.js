import { createI18n } from 'vue-i18n'
import ruEl from 'element-plus/es/locale/lang/ru'
import kkEl from 'element-plus/es/locale/lang/kk'
import ru from './ru'
import kk from './kk'

const KEY = 'fishstocke.lang'
function saved() { try { return localStorage.getItem(KEY) } catch (e) { return null } }

const i18n = createI18n({ legacy: false, locale: saved() || 'ru', fallbackLocale: 'ru', messages: { ru, kk } })

export function setLang(l) {
  i18n.global.locale.value = l
  try { localStorage.setItem(KEY, l) } catch (e) { /* */ }
  document.documentElement.lang = l
}

export function elLocale() { return (saved() || 'ru') === 'kk' ? kkEl : ruEl }

// Название объекта на текущем языке: title_kk / name_kk, иначе русское
export function tr(obj, base = 'title') {
  if (!obj) return ''
  const l = i18n.global.locale.value
  return (l === 'kk' && (obj[`${base}_kk`])) || obj[`${base}_ru`] || obj.name_ru || obj.code || ''
}

export default i18n
