// Обращение к сервисам через шлюз: /api/<сервис>/... ; токен обновляется автоматически.
import { useAuth } from './store/auth'
import i18n from './i18n'

export class ApiError extends Error {
  constructor(status, code, message, details) {
    super(message); this.status = status; this.code = code; this.details = details
  }
}

let refreshing = null

async function refresh(auth) {
  if (!auth.refreshToken) return false
  if (!refreshing) {
    refreshing = fetch('/api/users/auth/refresh', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: auth.refreshToken }),
    }).then(async (r) => {
      if (!r.ok) return false
      auth.setSession(await r.json()); return true
    }).catch(() => false).finally(() => { setTimeout(() => (refreshing = null), 0) })
  }
  return refreshing
}

function errorText(code, message) {
  const key = `errors.${code}`
  return code && i18n.global.te(key) ? i18n.global.t(key) : message
}

export async function request(service, path, { method = 'GET', body, form, query, raw = false, retry = true } = {}) {
  const auth = useAuth()
  const url = new URL(`/api/${service}${path}`, window.location.origin)
  for (const [k, v] of Object.entries(query || {})) if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, v)
  const headers = {}
  if (auth.accessToken) headers.Authorization = `Bearer ${auth.accessToken}`
  let payload
  if (form) { payload = form } else if (body !== undefined) { headers['Content-Type'] = 'application/json'; payload = JSON.stringify(body) }
  let r
  try {
    r = await fetch(url, { method, headers, body: payload })
  } catch (e) {
    throw new ApiError(0, 'network', i18n.global.t('errors.network'))
  }
  if (r.status === 401 && retry && auth.refreshToken && !path.startsWith('/auth/')) {
    if (await refresh(auth)) return request(service, path, { method, body, form, query, raw, retry: false })
    auth.logout(true)
  }
  if (!r.ok) {
    let j = null
    try { j = await r.json() } catch (e) { /* не JSON */ }
    const err = j?.error || {}
    throw new ApiError(r.status, err.code, errorText(err.code, err.message || `${r.status} ${r.statusText}`), err.details)
  }
  if (raw) return r
  const ct = r.headers.get('content-type') || ''
  return ct.includes('application/json') ? r.json() : r.text()
}

export const api = {
  get: (s, p, query) => request(s, p, { query }),
  post: (s, p, body, query) => request(s, p, { method: 'POST', body: body ?? {}, query }),
  put: (s, p, body) => request(s, p, { method: 'PUT', body }),
  patch: (s, p, body) => request(s, p, { method: 'PATCH', body }),
  del: (s, p, query) => request(s, p, { method: 'DELETE', query }),
  upload: (s, p, fields) => {
    const fd = new FormData()
    for (const [k, v] of Object.entries(fields)) if (v !== undefined && v !== null) fd.append(k, v)
    return request(s, p, { method: 'POST', form: fd })
  },
}

// Скачивание файла с авторизацией (Excel, NetCDF, отчёты)
export async function download(service, path, query, filename) {
  const r = await request(service, path, { query, raw: true })
  const blob = await r.blob()
  const cd = r.headers.get('content-disposition') || ''
  const m = /filename="?([^"]+)"?/.exec(cd)
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = filename || (m ? m[1] : 'file')
  document.body.appendChild(a); a.click(); a.remove()
  setTimeout(() => URL.revokeObjectURL(a.href), 2000)
}
