// Кабинеты — отдельные интерфейсы для разных пользователей (docs/decisions.md, № 52).
// Один код, отдельные точки входа сборки (frontend/<кабинет>/index.html), единый вход (/login), общий домен.
// Права API не меняются: здесь только то, в какой кабинет роль может войти.

const STAFF = ['admin', 'ichthyologist', 'mathematician']

export const CABINETS = [
  { key: 'monitoring', base: '/monitoring/', icon: 'TrendCharts', roles: [...STAFF, 'viewer'] },
  { key: 'input', base: '/input/', icon: 'Upload', roles: STAFF },
  { key: 'calc', base: '/calc/', icon: 'Odometer', roles: STAFF },
  { key: 'design', base: '/design/', icon: 'EditPen', roles: STAFF },
  { key: 'admin', base: '/admin/', icon: 'Setting', roles: ['admin', 'mathematician'] },
]

export const cabinet = (key) => CABINETS.find((c) => c.key === key)

/** Кабинет, которому принадлежит адрес (null — страница входа, выбор кабинета, старый адрес). */
export function cabinetOf(path) {
  const seg = String(path || '').split(/[?#]/)[0].split('/')[1]
  return CABINETS.find((c) => c.key === seg) || null
}

export const canEnter = (cab, role) => !!cab && !!role && cab.roles.includes(role)
export const cabinetsFor = (role) => CABINETS.filter((c) => canEnter(c, role))

/** Можно ли роли перейти по адресу (адреса вне кабинетов — да). */
export function canGo(path, role) {
  const cab = cabinetOf(path)
  return !cab || canEnter(cab, role)
}

// Старые адреса единого интерфейса (до 23.10.2026) → адреса кабинетов. Порядок важен: сначала длинные.
const LEGACY = [
  ['/data', '/input/datasets'],
  ['/calculations', '/calc/calculations'],
  ['/runs', '/calc/runs'],
  ['/profiles', '/calc/profiles'],
  ['/dictionaries', '/design/dictionaries'],
  ['/algorithms', '/design/algorithms'],
  ['/dashboards', '/monitoring/dashboards'],
  ['/catalog', '/admin/catalog'],
  ['/users', '/admin/users'],
  ['/audit', '/admin/audit'],
  ['/help', '/monitoring/help'],
]

const under = (p, prefix) => p === prefix || p.startsWith(prefix + '/')

/** Старый адрес → новый (с сохранением хвоста и параметров); null — адрес не старый. */
export function legacyToNew(fullPath) {
  const m = String(fullPath || '').match(/^([^?#]*)(.*)$/)
  const p = m[1].replace(/\/+$/, '') || '/'
  const rest = m[2]
  if (p === '/') return null
  if (cabinetOf(p) && cabinetOf(p).key !== 'monitoring') return null
  if (p === '/monitoring') return null // главная кабинета (карта); прежний выбор водоёма — та же карта
  if (p.startsWith('/monitoring/')) {
    // старый мониторинг водоёма /monitoring/<код>; остальные адреса кабинета — новые
    const seg = p.split('/')[2]
    if (['waterbody', 'dashboards', 'help'].includes(seg)) return null
    return '/monitoring/waterbody' + p.slice('/monitoring'.length) + rest
  }
  for (const [old, now] of LEGACY) if (under(p, old)) return now + p.slice(old.length) + rest
  return null
}

// Новый адрес → вид старого: справка привязывает статьи к экранам по старым адресам (сервис help, поле routes),
// поэтому для значка «?» адрес переводится обратно — хранимые статьи менять не нужно.
const REVERSE = [
  ['/monitoring/waterbody', '/monitoring'],
  ['/monitoring/dashboards', '/dashboards'],
  ['/input/datasets', '/data'],
  ['/calc/calculations', '/calculations'],
  ['/calc/runs', '/runs'],
  ['/calc/profiles', '/profiles'],
  ['/design/dictionaries', '/dictionaries'],
  ['/design/algorithms', '/algorithms'],
  ['/admin/catalog', '/catalog'],
  ['/admin/users', '/users'],
  ['/admin/audit', '/audit'],
]

export function helpRoute(path) {
  const p = String(path || '').split(/[?#]/)[0].replace(/\/+$/, '') || '/'
  const h = p.match(/^\/[a-z]+\/help(\/.*)?$/)
  if (h && cabinetOf(p)) return '/help' + (h[1] || '')
  for (const [now, old] of REVERSE) if (under(p, now)) return old + p.slice(now.length)
  if (p === '/monitoring') return '/'
  const cab = cabinetOf(p)
  if (cab && p === cab.base.replace(/\/$/, '')) {
    return { input: '/data', calc: '/calculations', design: '/dictionaries', admin: '/users' }[cab.key] || p
  }
  return p
}

/** Куда вести после входа: адрес из next (если роли можно), единственный кабинет или выбор кабинета. */
export function homeFor(role, next) {
  if (next && next.startsWith('/') && !next.startsWith('//') && !next.startsWith('/login')) {
    const n = legacyToNew(next) || next
    if (n !== '/' && canGo(n, role)) return n
  }
  const cabs = cabinetsFor(role)
  return cabs.length === 1 ? cabs[0].base : '/'
}

// ------------------------------------------------------------------ текущий кабинет (задаётся точкой входа)
let current = null
export const setCurrentCabinet = (key) => { current = key ? cabinet(key) : null }
export const currentCabinet = () => current

/** Адрес статьи справки в текущем кабинете (на странице выбора кабинета — в мониторинге). */
export const helpPath = (id) => (current ? current.base : '/monitoring/') + 'help' + (id ? '/' + id : '')

/** Переход с перезагрузкой страницы — в другой кабинет или на вход. */
export function hardGo(path) { window.location.assign(path) }
