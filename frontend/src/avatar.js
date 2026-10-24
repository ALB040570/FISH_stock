// Фото пользователей (аватары): загрузка с авторизацией, кэш, подготовка фото в браузере (решение № 58).
import { reactive } from 'vue'
import { request } from './api'

/** Инициалы для аватара без фото: «Пётр Иванов» → «ПИ». */
export function initialsOf(name) {
  return String(name || '?').trim().split(/\s+/).filter(Boolean).map((s) => s[0]).slice(0, 2).join('').toUpperCase() || '?'
}

// адрес картинки зависит от версии фото — смена фото даёт новый ключ, старый адрес освобождается
const cache = reactive({})
const pending = {}

/** Адрес (blob:) фото пользователя или '' — пока не загружено / фото нет. Реактивно. */
export function avatarSrc(uid, ver) {
  if (!uid || !ver) return ''
  const key = `${uid}:${ver}`
  if (key in cache) return cache[key]
  if (!pending[key]) {
    pending[key] = request('users', `/users/${uid}/avatar`, { query: { v: ver }, raw: true })
      .then((r) => r.blob())
      .then((b) => {
        for (const k of Object.keys(cache)) {
          if (k.startsWith(uid + ':') && cache[k]) { URL.revokeObjectURL(cache[k]); delete cache[k] }
        }
        cache[key] = URL.createObjectURL(b)
      })
      .catch(() => { cache[key] = '' })
  }
  return ''
}

export const AVATAR_SIZE = 256

/** Размер и сдвиг квадратной вырезки по центру изображения w×h. */
export function centerSquare(w, h) {
  const side = Math.min(w, h)
  return { sx: Math.round((w - side) / 2), sy: Math.round((h - side) / 2), side }
}

/** Файл изображения → квадрат 256×256 JPEG (data:URL) — так на сервер уходит небольшой файл. */
export function prepareAvatar(file, size = AVATAR_SIZE) {
  return new Promise((resolve, reject) => {
    if (!file || !/^image\//.test(file.type)) { reject(new Error('Выберите файл изображения (JPEG, PNG)')); return }
    const url = URL.createObjectURL(file)
    const img = new Image()
    img.onload = () => {
      const { sx, sy, side } = centerSquare(img.naturalWidth, img.naturalHeight)
      const c = document.createElement('canvas')
      c.width = size; c.height = size
      const ctx = c.getContext('2d')
      ctx.fillStyle = '#ffffff'
      ctx.fillRect(0, 0, size, size)
      ctx.drawImage(img, sx, sy, side, side, 0, 0, size, size)
      URL.revokeObjectURL(url)
      resolve(c.toDataURL('image/jpeg', 0.85))
    }
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('Не удалось открыть изображение')) }
    img.src = url
  })
}

// Люди (имя, фото, должность) для подписей авторов — один запрос на страницу.
export const people = reactive({})
let peopleLoad = null
export function loadPeople(force = false) {
  if (!peopleLoad || force) {
    peopleLoad = request('users', '/users/people')
      .then((p) => { for (const k of Object.keys(people)) delete people[k]; Object.assign(people, p) })
      .catch(() => { peopleLoad = null })
  }
  return peopleLoad
}

/** Автор записи: актуальные имя и фото по id, иначе имя, сохранённое в записи. */
export function personOf(id, savedName) {
  const p = id ? people[id] : null
  return { id, name: p?.name || savedName || '?', avatar_ver: p?.avatar_ver || null,
    position: p?.position || '', organization: p?.organization || '' }
}
