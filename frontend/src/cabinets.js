// Кабинеты — отдельные интерфейсы для разных пользователей (docs/decisions.md, № 52).
// Один код, отдельные точки входа сборки (frontend/<кабинет>/index.html), единый вход (/login), общий домен.
// Права API не меняются: здесь только то, в какой кабинет роль может войти.

const STAFF = ['admin', 'ichthyologist', 'mathematician']

export const CABINETS = [
  { key: 'monitoring', base: '/monitoring/', icon: 'TrendCharts', roles: [...STAFF, 'operator', 'viewer', 'presenter'] },
  { key: 'input', base: '/input/', icon: 'Upload', roles: [...STAFF, 'operator', 'presenter'] },
  { key: 'calc', base: '/calc/', icon: 'Odometer', roles: [...STAFF, 'presenter'] },
  { key: 'design', base: '/design/', icon: 'EditPen', roles: [...STAFF, 'presenter'] },
  // каталог алгоритмов перенесён в «Расчёты запасов рыб» (решение № 66) — в «Администрировании» только пользователи и журнал
  { key: 'admin', base: '/admin/', icon: 'Setting', roles: ['admin'] },
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
  ['/dictionaries', '/design/dictionaries'],
  ['/algorithms', '/design/algorithms'],
  ['/dashboards', '/monitoring/dashboards'],
  ['/catalog', '/calc/catalog'],
  ['/users', '/admin/users'],
  ['/audit', '/admin/audit'],
  ['/help', '/monitoring/help'],
]

const under = (p, prefix) => p === prefix || p.startsWith(prefix + '/')

// перенесённые экраны (решение № 66): «хвост» адреса не сохраняется — у расчётов и запусков разные номера
const MOVED = [
  ['/runs', '/calc/calculations'],
  ['/profiles', '/calc/params'],
  ['/admin/catalog', '/calc/catalog'],
  ['/design/catalog', '/calc/catalog'],
  ['/calc/runs', '/calc/calculations'],
  ['/calc/profiles', '/calc/params'],
  ['/design/calculations', '/calc/calculations'],
]

/** Старый адрес → новый (с сохранением хвоста и параметров); null — адрес не старый. */
export function legacyToNew(fullPath) {
  const m = String(fullPath || '').match(/^([^?#]*)(.*)$/)
  const p = m[1].replace(/\/+$/, '') || '/'
  const rest = m[2]
  if (p === '/') return null
  // адреса кабинетов до решения № 66: каталог — в «Расчётах запасов рыб», запусков и параметров водоёмов больше нет
  for (const [old, now] of MOVED) if (under(p, old)) return now + rest
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
  ['/calc/catalog', '/catalog'],
  ['/calc/params', '/profiles'],
  ['/design/dictionaries', '/dictionaries'],
  ['/design/algorithms', '/algorithms'],
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

// Стартовая страница «Поток» (/) — для тех, кто ведёт данные через весь путь (№ 53); остальные сразу попадают
// в свой главный кабинет. Порядок «Потока»: путь данных, затем основа; номер — клавиша на странице.
// «Презентация» (№ 62) — тоже с «Потока»: показ всего пути данных без права что-либо менять
export const FLOW_ROLES = ['admin', 'mathematician', 'ichthyologist', 'presenter']
export const FLOW_PATH = ['input', 'calc', 'monitoring']
export const FLOW_BASE = ['design', 'admin']
const MAIN = { viewer: 'monitoring', operator: 'input' }

export const hasFlow = (role) => FLOW_ROLES.includes(role)
/** Главная страница роли: «Поток» или главный кабинет. */
export function mainPage(role) {
  if (hasFlow(role)) return '/'
  const key = MAIN[role] || cabinetsFor(role)[0]?.key
  return key ? cabinet(key).base : '/'
}

/** Куда вести после входа: адрес из next (если роли можно), иначе главная страница роли. */
export function homeFor(role, next) {
  if (next && next.startsWith('/') && !next.startsWith('//') && !next.startsWith('/login')) {
    const n = legacyToNew(next) || next
    if (n !== '/' && canGo(n, role)) return n
  }
  return mainPage(role)
}

// ------------------------------------------------------------------ текущий кабинет (задаётся точкой входа)
let current = null
export const setCurrentCabinet = (key) => { current = key ? cabinet(key) : null }
export const currentCabinet = () => current

/** Адрес статьи справки в текущем кабинете (на странице выбора кабинета — в мониторинге). */
export const helpPath = (id) => (current ? current.base : '/monitoring/') + 'help' + (id ? '/' + id : '')

/** Переход с перезагрузкой страницы — в другой кабинет или на вход. */
export function hardGo(path) { window.location.assign(path) }
