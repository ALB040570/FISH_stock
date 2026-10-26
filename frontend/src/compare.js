// Страница «Сравнение расчётов» (кабинет «Мониторинг», решение № 77): набор рядов в ссылке, подписи рядов,
// графики (численность по годам, ПДУ по годам прогноза, вероятность снижения запаса) и строки таблицы.
// Ряд — водоём + расчёт + вид (+ k у прогноза j, + орудие у запаса по уловам g); данные отдаёт сервис дашбордов
// (/compare/series), здесь только раскладка.
import { buildChart, fmt, PALETTE } from './components/charts'
import { CHART } from './theme'

export const SOURCES = ['forecast', 'model', 'catch']
const SRC_CODE = { forecast: 'f', model: 'm', catch: 'c' }
const SRC_BY_CODE = { f: 'forecast', m: 'model', c: 'catch' }
export const GEARS = ['сеть', 'невод', 'сеть+невод']
const GEAR_CODE = { сеть: 'n', невод: 's', 'сеть+невод': 'b' }
const GEAR_BY_CODE = { n: 'сеть', s: 'невод', b: 'сеть+невод' }
export const MAX_SERIES = 12

/** k для подписи: 0,25 */
export const kf = (k) => (k === null || k === undefined || k === '' ? '' : String(Number(k)).replace('.', ','))

/** Ряд → строка ссылки: f~расчёт~вид~k | m~расчёт~вид | c~расчёт~вид~орудие(n|s|b) */
export function itemKey(it) {
  const src = SRC_CODE[it.source] || 'f'
  const head = `${src}~${it.calc}~${it.species}`
  if (src === 'f') return `${head}~${Number(it.k ?? 1)}`
  if (src === 'c') return `${head}~${GEAR_CODE[it.gear] || 'b'}`
  return head
}

export function decodeItem(s) {
  const p = String(s || '').split('~')
  const source = SRC_BY_CODE[p[0]]
  if (!source || !p[1] || !p[2]) return null
  const it = { source, calc: p[1], species: p[2] }
  if (source === 'forecast') {
    const k = Number(String(p[3] ?? '1').replace(',', '.'))
    if (!Number.isFinite(k) || k < 0 || k > 10) return null
    it.k = k
  }
  if (source === 'catch') it.gear = GEAR_BY_CODE[p[3]] || 'сеть+невод'
  return it
}

/** Уникальные ряды, не больше MAX_SERIES. */
export function uniqItems(items) {
  const seen = new Set()
  const out = []
  for (const it of items) {
    if (!it) continue
    const key = itemKey(it)
    if (seen.has(key)) continue
    seen.add(key)
    out.push(it)
  }
  return out.slice(0, MAX_SERIES)
}

/** Состояние страницы → query ссылки (s — ряды, m=f — промысловая биомасса, log=1, b=1|0 — интервалы). */
export function toQuery({ items = [], measure = 'total', log = false, bands = null } = {}) {
  const q = {}
  if (items.length) q.s = items.map(itemKey)
  if (measure === 'fishable') q.m = 'f'
  if (log) q.log = '1'
  if (bands === true) q.b = '1'
  if (bands === false) q.b = '0'
  return q
}

export function fromQuery(q = {}) {
  const s = q.s == null ? [] : Array.isArray(q.s) ? q.s : [q.s]
  return {
    items: uniqItems(s.map(decodeItem)),
    measure: q.m === 'f' ? 'fishable' : 'total',
    log: q.log === '1',
    bands: q.b === '1' ? true : q.b === '0' ? false : null,
  }
}

/** Цвет и вид линии ряда: цвет — по номеру; k = 0 — пунктир; с одиннадцатого ряда цвета повторяются точками. */
export function seriesStyle(i, s) {
  const color = PALETTE[i % PALETTE.length]
  const dash = s?.source === 'forecast' && Number(s.k) === 0 ? 'dashed' : i >= PALETTE.length ? 'dotted' : null
  return { color, dash }
}

function parts(s, t) {
  const src = s.source === 'model' ? t('cmp.src_model_short') : s.source === 'catch' ? `${t('cmp.src_catch_short')}: ${s.gear || 'сеть+невод'}` : t('cmp.src_forecast_short')
  return {
    wb: s.water_body_name || s.water_body || '',
    sp: s.species_name || s.species || '',
    calc: s.calc_title ? `${s.calc_title}${s.is_main ? ' ★' : ''}` : '',
    src,
    k: s.source === 'forecast' && s.k !== undefined && s.k !== null ? `k = ${kf(s.k)}` : '',
  }
}

const KEYS = ['wb', 'sp', 'calc', 'src', 'k']

/**
 * Короткие подписи рядов: только то, чем ряды различаются (водоём, вид, расчёт, источник, k); расчёт — только если
 * ряды одного источника взяты из разных расчётов. Общее — отдельной строкой над графиками; full — полные подписи.
 */
export function seriesLabels(series, t) {
  const ps = series.map((s) => parts(s, t))
  const full = ps.map((p) => KEYS.map((k) => p[k]).filter(Boolean).join(' · '))
  if (ps.length <= 1) return { labels: full, common: '', full }
  const differs = (k) => {
    if (k !== 'calc') return new Set(ps.map((p) => p[k])).size > 1
    const by = new Map()
    series.forEach((s, i) => { if (!by.has(s.source)) by.set(s.source, new Set()); by.get(s.source).add(ps[i].calc) })
    return [...by.values()].some((v) => v.size > 1)
  }
  const varying = KEYS.filter(differs)
  const show = varying.length ? varying : KEYS
  const common = KEYS.filter((k) => !show.includes(k) && new Set(ps.map((p) => p[k])).size === 1).map((k) => ps[0][k]).filter(Boolean).join(' · ')
  return { labels: ps.map((p) => show.map((k) => p[k]).filter(Boolean).join(' · ') || '—'), common, full }
}

const hasQ = (q) => Array.isArray(q) && q.length === 5

function axisTooltip(unit) {
  return {
    trigger: 'axis',
    formatter: (ps) => {
      const rows = (Array.isArray(ps) ? ps : [ps]).filter((p) => p.seriesType === 'line' && p.seriesName !== '_' && p.value != null && !Number.isNaN(p.value))
      if (!rows.length) return ''
      return `<b>${rows[0].axisValue}</b><br>` + rows.map((p) => `${p.marker}${p.seriesName}: <b>${fmt(p.value, 'auto')}</b>${unit ? ' ' + unit : ''}`).join('<br>')
    },
  }
}

/**
 * Численность (или промысловая биомасса) по годам: история и прогноз. История одного расчёта прогноза и вида,
 * общая для нескольких рядов (разные k), рисуется один раз серым; прогноз каждого ряда продолжает последний год
 * истории. Полосы 95 % (при одном ряде и 50 %) — если включены интервалы.
 */
export function stockChart(series, { labels, bands = false, log = false, t, measure = 'total' }) {
  const ok = series.map((s, i) => ({ s, i })).filter(({ s }) => !s.error && Array.isArray(s.hist_q) && s.hist_q.length)
  if (!ok.length) return null
  const years = [...new Set(ok.flatMap(({ s }) => [...(s.years_hist || []), ...(s.years_fc || [])]))].sort((a, b) => a - b)
  const at = new Map(years.map((y, j) => [y, j]))
  const put = (pts) => {
    const a = years.map(() => null)
    for (const [y, v] of pts) if (at.has(y) && v !== undefined) a[at.get(y)] = v
    return a
  }
  // группы истории: ряды прогноза одного расчёта и вида
  const groups = new Map()
  for (const o of ok) {
    const key = o.s.source === 'forecast' ? `f~${o.s.calc}~${o.s.species}` : `${o.i}`
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key).push(o)
  }
  const unit = measure === 'fishable' ? t('cmp.unit_t') : t('cmp.unit_pcs')
  const bandsOut = []
  const lines = []
  const single = ok.length === 1
  for (const g of groups.values()) {
    const { s, i } = g[0]
    const shared = g.length > 1
    const color = shared ? CHART.label : seriesStyle(i, s).color
    const hq = s.hist_q
    const yh = s.years_hist
    const rest = labels[i].split(' · ').filter((x) => !x.startsWith('k = ')).join(' · ')
    const name = shared
      ? (rest ? `${t('cmp.history')}: ${rest}` : t('cmp.history'))
      : s.source === 'forecast' ? `${labels[i]} — ${t('cmp.history_short')}` : labels[i]
    if (bands && hasQ(hq)) {
      bandsOut.push({ name: `${name}, 95 %`, lo: put(yh.map((y, j) => [y, hq[0][j]])), hi: put(yh.map((y, j) => [y, hq[4][j]])), color, op: 0.13 })
      if (single) bandsOut.push({ name: `${name}, 50 %`, lo: put(yh.map((y, j) => [y, hq[1][j]])), hi: put(yh.map((y, j) => [y, hq[3][j]])), color, op: 0.22 })
    }
    const med = hq.length === 5 ? hq[2] : hq[0]
    lines.push({ name, values: put(yh.map((y, j) => [y, med[j]])), color, bold: shared || s.source !== 'forecast',
      dash: s.source === 'forecast' ? null : seriesStyle(i, s).dash })
  }
  // прогноз каждого ряда — от последнего года истории
  for (const { s, i } of ok) {
    if (s.source !== 'forecast' || !hasQ(s.fc_q)) continue
    const { color, dash } = seriesStyle(i, s)
    const y0 = s.years_hist[s.years_hist.length - 1]
    const jq = hasQ(s.join_q) ? s.join_q : s.hist_q.map((q) => q[q.length - 1])
    const fc = (r) => put([[y0, jq[r]], ...s.years_fc.map((y, j) => [y, s.fc_q[r][j]])])
    if (bands) {
      bandsOut.push({ name: `${labels[i]}, 95 %`, lo: fc(0), hi: fc(4), color, op: single ? 0.14 : 0.11 })
      if (single) bandsOut.push({ name: `${labels[i]}, 50 %`, lo: fc(1), hi: fc(3), color, op: 0.26 })
    }
    lines.push({ name: labels[i], values: fc(2), color, bold: true, dash })
  }
  const y1 = ok.map(({ s }) => (s.years_fc || [])[0]).filter((y) => y != null).sort((a, b) => a - b)[0]
  const spec = { kind: 'band', x: years, bands: bandsOut, lines, x_title: t('cmp.year'), y_title: unit,
    vrefs: y1 != null ? [{ x: String(y1), label: t('cmp.forecast_arrow') }] : [] }
  const o = buildChart(spec, log ? 'log' : 'linear')
  return { ...o, legend: { show: false }, grid: { ...o.grid, top: 28 }, tooltip: axisTooltip(unit) }
}

/** ПДУ по годам прогноза (медиана) для рядов прогноза. */
export function pduChart(series, { labels, log = false, t }) {
  const ok = series.map((s, i) => ({ s, i })).filter(({ s }) => !s.error && s.source === 'forecast' && Array.isArray(s.pdu_years))
  if (!ok.length) return null
  const years = [...new Set(ok.flatMap(({ s }) => s.years_fc))].sort((a, b) => a - b)
  const spec = { kind: 'fit', x: years, x_title: t('cmp.year'), y_title: t('cmp.unit_t'),
    series: ok.map(({ s, i }) => {
      const { color, dash } = seriesStyle(i, s)
      const by = new Map(s.years_fc.map((y, j) => [y, s.pdu_years[j]]))
      return { type: 'line', name: labels[i], values: years.map((y) => by.get(y) ?? null), color, dash, bold: false }
    }) }
  const o = buildChart(spec, log ? 'log' : 'linear')
  return { ...o, legend: { show: false }, grid: { ...o.grid, top: 28 }, tooltip: axisTooltip(t('cmp.unit_t')) }
}

/** Вероятность снижения запаса к концу прогноза, % — столбец на ряд. */
export function riskChart(series, { labels, t }) {
  const ok = series.map((s, i) => ({ s, i })).filter(({ s }) => !s.error && s.source === 'forecast' && s.risk != null)
  if (!ok.length) return null
  const names = ok.map(({ i }) => labels[i])
  return {
    grid: { left: 52, right: 16, top: 28, bottom: ok.length > 4 ? 86 : 44 },
    tooltip: { trigger: 'item', formatter: (p) => `${p.name}: <b>${fmt(p.value, 0)} %</b>` },
    xAxis: { type: 'category', data: names, axisLabel: { interval: 0, rotate: ok.length > 4 ? 28 : 0, width: ok.length > 4 ? 130 : 160, overflow: 'truncate' } },
    yAxis: { type: 'value', min: 0, max: 100, name: '%', axisLabel: { formatter: (v) => `${v}` }, splitLine: { lineStyle: { color: CHART.grid } } },
    series: [{ type: 'bar', barMaxWidth: 38, data: ok.map(({ s, i }) => ({ value: s.risk * 100, itemStyle: { color: seriesStyle(i, s).color } })),
      label: { show: true, position: 'top', formatter: (p) => fmt(p.value, 0), color: CHART.label } }],
  }
}

/** Строки таблицы: ПДУ первого года прогноза с интервалом, численность в конце прогноза, риск, F; у истории — последний год. */
export function tableRows(series, labels) {
  return series.map((s, i) => {
    const { color } = seriesStyle(i, s)
    const r = { n: i, color, label: labels[i], source: s.source, error: s.error || null, wb: s.water_body_name, calc: s.calc_title,
      is_main: s.is_main, species: s.species_name || s.species, k: s.source === 'forecast' ? s.k : null, gear: s.gear || null }
    if (s.error || !Array.isArray(s.hist_q)) return r
    const hq = s.hist_q.length === 5 ? s.hist_q[2] : s.hist_q[0]
    r.last_year = s.years_hist[s.years_hist.length - 1]
    r.last = hq[hq.length - 1]
    if (s.source === 'forecast') {
      r.F = s.F
      r.pdu = s.pdu1_q ? s.pdu1_q[2] : null
      r.pdu_lo = s.pdu1_q ? s.pdu1_q[0] : null
      r.pdu_hi = s.pdu1_q ? s.pdu1_q[4] : null
      r.end = hasQ(s.fc_q) ? s.fc_q[2][s.fc_q[2].length - 1] : null
      r.end_lo = hasQ(s.fc_q) ? s.fc_q[0][s.fc_q[0].length - 1] : null
      r.end_hi = hasQ(s.fc_q) ? s.fc_q[4][s.fc_q[4].length - 1] : null
      r.risk = s.risk != null ? s.risk * 100 : null
      r.y1 = s.years_fc[0]
      r.yE = s.years_fc[s.years_fc.length - 1]
    }
    return r
  })
}

/** Годы для заголовков таблицы: первый и последний год прогноза (самые частые среди рядов). */
export function tableYears(rows) {
  const most = (key) => {
    const c = new Map()
    for (const r of rows) if (r[key] != null) c.set(r[key], (c.get(r[key]) || 0) + 1)
    return [...c.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? null
  }
  return { y1: most('y1'), yE: most('yE'), last: most('last_year') }
}
