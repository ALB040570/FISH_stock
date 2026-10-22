// Общий вид графиков: палитра темы (src/theme.js), читаемые оси, числа с пробелами.
import { CHART, CHART_PALETTE, HEAT } from '../theme'

// PALETTE — реактивный массив текущей схемы; в параметры графика передаётся копия pal()
export const PALETTE = CHART_PALETTE
export const pal = () => [...CHART_PALETTE]

export function fmt(v, d = 0) {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  const a = Math.abs(v)
  if (d === 'auto') d = a >= 100 ? 0 : a >= 1 ? 2 : 3
  return Number(v).toLocaleString('ru-RU', { maximumFractionDigits: d, minimumFractionDigits: 0 })
}

const UNITS = { ru: [' млрд', ' млн', ' тыс'], kk: [' млрд', ' млн', ' мың'] }
function lang() { try { return localStorage.getItem('fishstock.lang') || 'ru' } catch (e) { return 'ru' } }
export function compact(v) {
  if (v === null || v === undefined) return ''
  const a = Math.abs(v)
  const u = UNITS[lang()] || UNITS.ru
  if (a >= 1e9) return (v / 1e9).toLocaleString('ru-RU', { maximumFractionDigits: 1 }) + u[0]
  if (a >= 1e6) return (v / 1e6).toLocaleString('ru-RU', { maximumFractionDigits: 1 }) + u[1]
  if (a >= 1e3) return (v / 1e3).toLocaleString('ru-RU', { maximumFractionDigits: 1 }) + u[2]
  return v.toLocaleString('ru-RU', { maximumFractionDigits: 3 })
}

export function base({ x, series, yName = '', type = 'line', stack = false, legend = true, xName = '' }) {
  return {
    color: pal(),
    grid: { left: 64, right: 18, top: legend ? 36 : 16, bottom: 34, containLabel: false },
    tooltip: { trigger: 'axis', valueFormatter: (v) => fmt(v, 'auto') },
    legend: legend ? { top: 0, type: 'scroll', icon: 'roundRect', itemWidth: 12, itemHeight: 8 } : undefined,
    xAxis: { type: 'category', data: x, name: xName, nameLocation: 'middle', nameGap: 24, axisTick: { alignWithLabel: true } },
    yAxis: { type: 'value', name: yName, nameTextStyle: { align: 'left' }, axisLabel: { formatter: compact }, splitLine: { lineStyle: { color: CHART.grid } } },
    series: series.map((s) => ({ type, name: s.name ?? '', data: s.values, stack: stack ? 'a' : undefined, smooth: false,
      showSymbol: type === 'line' && (x?.length || 0) < 25, connectNulls: false, barMaxWidth: 28, ...(s.extra || {}) })),
  }
}

// Полоса интервала (2,5–97,5 %, 25–75 %) + медиана + точки наблюдений
export function band({ x, q, name = 'медиана', obs = [], yName = '', color = CHART.main }) {
  const lo = q[0], hi = q[4], lo2 = q[1], hi2 = q[3]
  const series = [
    { type: 'line', data: lo, stack: 'b95', lineStyle: { opacity: 0 }, symbol: 'none', name: '95 %', tooltip: { show: false } },
    { type: 'line', data: hi.map((v, i) => (v == null || lo[i] == null ? null : v - lo[i])), stack: 'b95', lineStyle: { opacity: 0 },
      symbol: 'none', areaStyle: { color, opacity: 0.12 }, name: '95 %', tooltip: { show: false } },
    { type: 'line', data: lo2, stack: 'b50', lineStyle: { opacity: 0 }, symbol: 'none', name: '50 %', tooltip: { show: false } },
    { type: 'line', data: hi2.map((v, i) => (v == null || lo2[i] == null ? null : v - lo2[i])), stack: 'b50', lineStyle: { opacity: 0 },
      symbol: 'none', areaStyle: { color, opacity: 0.22 }, name: '50 %', tooltip: { show: false } },
    { type: 'line', data: q[2], name, lineStyle: { width: 2.5, color }, itemStyle: { color }, symbolSize: 5 },
    ...obs.map((o, i) => ({ type: o.type || 'scatter', data: o.values, name: o.name, symbolSize: 7,
      itemStyle: { color: PALETTE[(i + 2) % PALETTE.length] }, lineStyle: { type: 'dashed' } })),
  ]
  return {
    color: [color],
    grid: { left: 70, right: 18, top: 36, bottom: 30 },
    tooltip: { trigger: 'axis', valueFormatter: (v) => fmt(v, 0) },
    legend: { top: 0, data: [name, '95 %', '50 %', ...obs.map((o) => o.name)] },
    xAxis: { type: 'category', data: x },
    yAxis: { type: 'value', name: yName, axisLabel: { formatter: compact }, splitLine: { lineStyle: { color: CHART.grid } } },
    series,
  }
}

// ------------------------------------------------------------------ представления исходных данных

const axisY = (name, extra = {}) => ({ type: 'value', name, nameTextStyle: { align: 'left' }, axisLabel: { formatter: compact },
  splitLine: { lineStyle: { color: CHART.grid } }, ...extra })
const hiLabel = (hl) => (v) => (hl != null && String(v) === String(hl) ? `{hl|${v}}` : String(v))
const hlRich = () => ({ hl: { fontWeight: 'bold', color: CHART.highlight } })

// Ряды: line | bar | stack | stack100; полоса lo–hi (95 % интервал) у линий; подсветка года
export function seriesChart(spec, ctype, { highlight = null } = {}) {
  const x = (spec.x || []).map(String)
  let series = spec.series || []
  if (ctype === 'stack100') {
    const tot = x.map((_, i) => series.reduce((a, s) => a + (s.values[i] || 0), 0))
    series = series.map((s) => ({ ...s, values: s.values.map((v, i) => (v == null || !tot[i] ? null : (v / tot[i]) * 100)) }))
  }
  const type = ctype === 'line' ? 'line' : 'bar'
  const stack = ctype === 'stack' || ctype === 'stack100'
  const out = []
  series.forEach((s, k) => {
    const color = PALETTE[k % PALETTE.length]
    if (type === 'line' && s.lo && s.hi) {
      out.push({ type: 'line', name: `${s.name}: 95 %`, data: s.lo, stack: 'band' + k, symbol: 'none', lineStyle: { opacity: 0 },
        tooltip: { show: false }, silent: true })
      out.push({ type: 'line', name: `${s.name}: 95 %`, data: s.hi.map((v, i) => (v == null || s.lo[i] == null ? null : v - s.lo[i])),
        stack: 'band' + k, symbol: 'none', lineStyle: { opacity: 0 }, areaStyle: { color, opacity: 0.16 }, tooltip: { show: false }, silent: true })
    }
    out.push({ type, name: s.name ?? '', data: s.values, stack: stack ? 'a' : undefined, barMaxWidth: 26,
      showSymbol: type === 'line' && x.length < 30, connectNulls: false, itemStyle: { color },
      lineStyle: { width: 2.2, color },
      ...(spec.signed ? { itemStyle: { color: (p) => (p.value < 0 ? CHART.limit : CHART.main) } } : {}) })
  })
  if (spec.extra_line) {
    out.push({ type: 'line', name: spec.extra_line.name, data: spec.extra_line.values, yAxisIndex: spec.extra_line.same_axis || ctype === 'stack100' ? 0 : 0,
      lineStyle: { type: 'dashed', width: 2, color: CHART.highlight }, itemStyle: { color: CHART.highlight }, symbolSize: 5, z: 5 })
  }
  if (highlight != null && spec.x_is_year && x.includes(String(highlight)) && out.length) {
    out[out.length - 1].markLine = { silent: true, symbol: 'none', label: { show: false },
      lineStyle: { color: CHART.highlight, width: 2, type: 'solid' }, data: [{ xAxis: String(highlight) }] }
  }
  const legend = out.filter((s) => !String(s.name).endsWith(': 95 %')).length > 1
  return {
    color: pal(),
    grid: { left: 62, right: 16, top: legend ? 58 : 32, bottom: spec.x_title ? 42 : 30 },
    tooltip: { trigger: 'axis', valueFormatter: (v) => fmt(v, 'auto') },
    legend: legend ? { top: 0, type: 'scroll', icon: 'roundRect', itemWidth: 12, itemHeight: 8,
      data: out.filter((s) => !String(s.name).endsWith(': 95 %')).map((s) => s.name) } : undefined,
    xAxis: { type: 'category', data: x, name: spec.x_title || '', nameLocation: 'middle', nameGap: 26,
      axisLabel: { formatter: spec.x_is_year ? hiLabel(highlight) : undefined, rich: hlRich(), interval: x.length > 30 ? 'auto' : 0,
        rotate: !spec.x_is_year && x.length > 8 ? 30 : 0 }, axisTick: { alignWithLabel: true } },
    yAxis: axisY(ctype === 'stack100' ? '%' : spec.y_title || '', ctype === 'stack100' ? { max: 100 } : {}),
    series: out,
  }
}

// Тепловая карта: cells [[x, y, значение]]; fmt int | pct | dev (расходящаяся шкала вокруг нуля)
export function heatmapChart(spec, { highlight = null } = {}) {
  const vals = (spec.cells || []).map((c) => c[2]).filter((v) => v != null)
  const dev = spec.fmt === 'dev'
  // шкала отклонений: по 90-му процентилю модуля, чтобы один выброс не «съедал» цвета остальных клеток
  const abs = vals.map((v) => Math.abs(v)).sort((a, b) => a - b)
  const m = dev ? Math.max(10, Math.min(abs[abs.length - 1] || 1, (abs[Math.floor(abs.length * 0.9)] || 1) * 1.2)) : Math.max(1, ...abs)
  const ylen = (spec.y || []).length
  const lab = (v) => (v == null ? '' : dev ? (v > 0 ? '+' : '') + fmt(v, 0) : spec.fmt === 'pct' ? fmt(v, v >= 10 ? 0 : 1)
    : spec.fmt === 'coef' ? fmt(v, 2) : fmt(v, 0))
  if (spec.selected_y != null) highlight = spec.selected_y
  const longY = Math.max(0, ...(spec.y || []).map((s) => String(s).length))
  return {
    grid: { left: Math.min(200, 16 + longY * 6.6), right: 16, top: 8, bottom: 62 },
    tooltip: { formatter: (p) => `${spec.x_title}: <b>${spec.x[p.value[0]]}</b><br>${spec.y_title}: <b>${spec.y[p.value[1]]}</b><br>${spec.value_title}: <b>${lab(p.value[2])}</b>` },
    xAxis: { type: 'category', data: spec.x.map(String), name: spec.x_title, nameLocation: 'middle', nameGap: 24, splitArea: { show: true },
      axisLabel: { formatter: spec.x_is_year ? hiLabel(highlight) : undefined, rich: hlRich() } },
    yAxis: { type: 'category', data: spec.y.map(String), inverse: !spec.y_is_year && ylen > 0, splitArea: { show: true },
      axisLabel: { interval: 0, formatter: spec.y_is_year ? hiLabel(highlight) : (v) => (v.length > 32 ? v.slice(0, 31) + '…' : v), rich: hlRich() } },
    visualMap: { min: dev ? -m : 0, max: dev ? m : spec.max != null ? spec.max : Math.max(1, ...vals), calculable: false, orient: 'horizontal', left: 'center', bottom: 0,
      itemHeight: 160, itemWidth: 10, inRange: { color: dev ? [...HEAT.div] : [...HEAT.seq] },
      text: [lab(dev ? m : spec.max != null ? spec.max : Math.max(1, ...vals)), lab(dev ? -m : 0)],
      textStyle: { fontSize: 10 } },
    series: [{ type: 'heatmap', data: spec.cells, label: { show: spec.cells.length <= 400, fontSize: 9.5, color: HEAT.label, textBorderColor: HEAT.outline, textBorderWidth: 2,
        formatter: (p) => lab(p.value[2]) },
      emphasis: { itemStyle: { borderColor: CHART.highlight, borderWidth: 2 } } }],
  }
}

// Диаграмма размаха по годам
export function boxChart(spec, { highlight = null } = {}) {
  const x = spec.x.map(String)
  return {
    grid: { left: 62, right: 16, top: 32, bottom: 30 },
    tooltip: { trigger: 'item', formatter: (p) => (p.seriesType === 'boxplot'
      ? `${x[p.dataIndex]}<br>мин. ${fmt(p.value[1], 0)} · 25 % ${fmt(p.value[2], 1)}<br>медиана <b>${fmt(p.value[3], 1)}</b><br>75 % ${fmt(p.value[4], 1)} · макс. ${fmt(p.value[5], 0)}`
      : `${x[p.value[0]]}: выброс ${fmt(p.value[1], 0)}`) },
    xAxis: { type: 'category', data: x, axisLabel: { formatter: hiLabel(highlight), rich: hlRich() } },
    yAxis: axisY(spec.y_title || ''),
    series: [
      { type: 'boxplot', data: spec.boxes.map((b) => b || [null, null, null, null, null]), itemStyle: { color: CSS_SOFT(), borderColor: CHART.main } },
      { type: 'scatter', data: spec.outliers, symbolSize: 6, itemStyle: { color: CHART.highlight } },
    ],
  }
}
function CSS_SOFT() { return CHART.background }

// Жизненный цикл: молодь 0–m0, половозрелые m0–m1, отметка m2
export function lifecycleChart(spec) {
  const L = spec.labels
  return {
    grid: { left: 110, right: 24, top: 30, bottom: 36 },
    legend: { top: 0, data: [L.young, L.adult, L.m2] },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' },
      formatter: (ps) => { const i = ps[0].dataIndex; return `<b>${spec.species[i]}</b>${spec.predator[i] ? ' · хищник' : ''}<br>m0 = ${spec.m0[i]}, m1 = ${spec.m1[i]}, m2 = ${spec.m2[i]}` } },
    xAxis: { type: 'value', name: L.axis, nameLocation: 'middle', nameGap: 22, min: 0, splitLine: { lineStyle: { color: CHART.grid } } },
    yAxis: { type: 'category', data: spec.species },
    series: [
      { type: 'bar', name: L.young, stack: 'l', data: spec.m0, itemStyle: { color: CHART.background }, barMaxWidth: 18 },
      { type: 'bar', name: L.adult, stack: 'l', data: spec.m1.map((v, i) => v - spec.m0[i]), itemStyle: { color: CHART.main }, barMaxWidth: 18 },
      { type: 'scatter', name: L.m2, data: spec.m2.map((v, i) => [v, i]), symbol: 'diamond', symbolSize: 12, itemStyle: { color: CHART.highlight }, z: 5 },
    ],
  }
}

// Две оси: слева и справа разные единицы
export function dualChart(spec, { highlight = null } = {}) {
  const x = spec.x.map(String)
  const mk = (s, i) => ({ type: s.type || 'line', name: s.name, data: s.values, yAxisIndex: i, barMaxWidth: 26,
    itemStyle: { color: i ? CHART.highlight : CHART.main }, lineStyle: { width: 2.2, color: i ? CHART.highlight : CHART.main } })
  const series = [mk(spec.left, 0), mk(spec.right, 1)]
  if (highlight != null && x.includes(String(highlight))) {
    series[0].markLine = { silent: true, symbol: 'none', label: { show: false }, lineStyle: { color: CHART.highlight, width: 2, type: 'solid' }, data: [{ xAxis: String(highlight) }] }
  }
  return {
    grid: { left: 62, right: 62, top: 44, bottom: 30 },
    tooltip: { trigger: 'axis', valueFormatter: (v) => fmt(v, 'auto') },
    legend: { top: 0 },
    xAxis: { type: 'category', data: x, axisLabel: { formatter: hiLabel(highlight), rich: hlRich() } },
    yAxis: [axisY(''), axisY('', { splitLine: { show: false } })],
    series,
  }
}

// Ряды по категориям (возрасты, годы): столбцы и линии; ctype linear | log. Цвет ряда — s.c (номер в палитре)
// или фон для одиночного ряда факта; в логарифмах одиночный факт — точки (как в прежнем приложении)
export function fitChart(spec, ctype) {
  const x = spec.x.map(String)
  const log = ctype === 'log'
  const pos = (v) => (v == null || (log && v <= 0) ? null : v)
  const bars = spec.series.filter((s) => s.type === 'bar').length
  const series = spec.series.map((s) => {
    const color = s.c != null ? PALETTE[s.c % PALETTE.length] : null
    if (s.type === 'bar' && color == null) {           // одиночный ряд факта (улов по возрастам)
      if (!log) return { type: 'bar', name: s.name, data: s.values, barMaxWidth: 34, itemStyle: { color: CHART.background } }
      return { type: 'scatter', name: s.name, data: s.values.map(pos), symbolSize: 9, itemStyle: { color: CHART.highlight } }
    }
    if (s.type === 'bar') return { type: 'bar', name: s.name, data: s.values.map(pos), barMaxWidth: bars > 1 ? 18 : 34, itemStyle: { color } }
    const c = color || CHART.main
    return { type: 'line', name: s.name, data: s.values.map(pos), symbol: 'circle', symbolSize: s.bold ? 7 : 5, z: s.bold ? 5 : 3,
      lineStyle: { width: s.bold ? 3 : 2.2, color: c, type: s.dash ? 'dashed' : 'solid' }, itemStyle: { color: c } }
  })
  if (spec.vrefs?.length && series.length) {
    series[0].markLine = { silent: true, symbol: 'none', lineStyle: { type: 'dashed', color: CHART.limit },
      label: { formatter: (p) => p.name, position: 'insideEndTop', color: CHART.label, textBorderWidth: 0 }, data: spec.vrefs.map((r) => ({ xAxis: String(r.x), name: r.label })) }
  }
  return {
    grid: { left: 70, right: 24, top: 44, bottom: 42 },
    tooltip: { trigger: 'axis', valueFormatter: (v) => fmt(v, 'auto') },
    legend: { top: 0, type: 'scroll' },
    xAxis: { type: 'category', data: x, name: spec.x_title || '', nameLocation: 'middle', nameGap: 26 },
    yAxis: axisY(spec.y_title || '', log ? { type: 'log', logBase: 10 } : {}),
    series,
  }
}

// Точки по годам (оценки по отдельным ловам) и линии годовых значений; ctype linear | log
export function dotsChart(spec, ctype) {
  const x = spec.x.map(String)
  const log = ctype === 'log'
  const ok = (v) => v != null && (!log || v > 0)
  const series = [
    ...spec.dots.map((d) => ({ type: 'scatter', name: d.name, symbolSize: 6,
      data: d.points.filter((q) => ok(q[1])).map((q) => ({ value: [q[0] + (d.c ? 0.12 : -0.12), q[1]], label: q[2] })),
      itemStyle: { color: PALETTE[(d.c || 0) % PALETTE.length], opacity: 0.55 } })),
    ...spec.lines.map((l) => ({ type: 'line', name: l.name, data: l.values.map((v, i) => [i, ok(v) ? v : null]), symbol: 'circle', symbolSize: 6, z: 5,
      lineStyle: { width: 2.6, color: PALETTE[(l.c || 0) % PALETTE.length] }, itemStyle: { color: PALETTE[(l.c || 0) % PALETTE.length] } })),
  ]
  return {
    grid: { left: 70, right: 24, top: 44, bottom: 42 },
    tooltip: { trigger: 'item', formatter: (p) => (p.seriesType === 'scatter'
      ? `${p.seriesName}<br>${p.data.label}<br><b>${fmt(p.value[1], 0)}</b>` : `${p.seriesName}, ${x[p.value[0]]}: <b>${fmt(p.value[1], 0)}</b>`) },
    legend: { top: 0, type: 'scroll' },
    xAxis: { type: 'value', min: -0.5, max: x.length - 0.5, interval: 1, name: spec.x_title || '', nameLocation: 'middle', nameGap: 26,
      axisLabel: { formatter: (v) => x[v] ?? '' }, splitLine: { show: false } },
    yAxis: axisY(spec.y_title || '', log ? { type: 'log', logBase: 10 } : {}),
    series,
  }
}

// Полосы интервалов (модель: 95 % и 50 %), медиана, точки оценок и вертикальные интервалы; x — категории (годы или возрасты).
// Полосы и интервалы рисуются своими фигурами, поэтому работают и в логарифмической шкале. ctype linear | log
export function bandChart(spec, ctype) {
  const x = spec.x.map(String)
  const log = ctype === 'log'
  const ok = (v) => (v == null || (log && v <= 0) ? null : v)
  const col = (c) => PALETTE[(c || 0) % PALETTE.length]
  const series = []
  for (const b of spec.bands || []) {
    const lo = b.lo.map(ok), hi = b.hi.map(ok)
    // данные с границами полосы: по ним ось (в том числе логарифмическая) считает свой диапазон
    series.push({ type: 'custom', name: b.name, silent: true, z: 1, itemStyle: { color: b.c != null ? col(b.c) : CHART.main, opacity: 0.5 },
      data: x.slice(0, -1).map((_, i) => [i, lo[i] ?? lo[i + 1] ?? null, hi[i] ?? hi[i + 1] ?? null]),
      renderItem: (params, api) => {
        const i = api.value(0)
        if (lo[i] == null || hi[i] == null || lo[i + 1] == null || hi[i + 1] == null) return null
        const pts = [api.coord([i, lo[i]]), api.coord([i + 1, lo[i + 1]]), api.coord([i + 1, hi[i + 1]]), api.coord([i, hi[i]])]
        return { type: 'polygon', shape: { points: pts }, style: { fill: b.c != null ? col(b.c) : CHART.main, opacity: b.op || 0.2 } }
      }, encode: { x: 0, y: [1, 2] }, tooltip: { show: false } })
  }
  for (const it of spec.intervals || []) {
    const lo = it.lo.map(ok), hi = it.hi.map(ok), mid = it.mid.map(ok)
    const c = col(it.c), dx = it.dx || 0
    series.push({ type: 'custom', name: it.name, z: 4, data: x.map((_, i) => [i, lo[i], hi[i], mid[i]]),
      renderItem: (params, api) => {
        const i = api.value(0), l = api.value(1), h = api.value(2), m = api.value(3)
        if (l == null || h == null || Number.isNaN(l) || Number.isNaN(h)) return null
        const bw = api.size([1, 0])[0] * 0.18
        const p1 = api.coord([i, l]), p2 = api.coord([i, h]), pm = m == null || Number.isNaN(m) ? null : api.coord([i, m])
        const sh = api.size([1, 0])[0] * dx
        const kids = [
          { type: 'line', shape: { x1: p1[0] + sh, y1: p1[1], x2: p2[0] + sh, y2: p2[1] }, style: { stroke: c, lineWidth: 2 } },
          { type: 'line', shape: { x1: p1[0] + sh - bw / 2, y1: p1[1], x2: p1[0] + sh + bw / 2, y2: p1[1] }, style: { stroke: c, lineWidth: 2 } },
          { type: 'line', shape: { x1: p2[0] + sh - bw / 2, y1: p2[1], x2: p2[0] + sh + bw / 2, y2: p2[1] }, style: { stroke: c, lineWidth: 2 } },
        ]
        if (pm) kids.push({ type: 'circle', shape: { cx: pm[0] + sh, cy: pm[1], r: 4 }, style: { fill: c } })
        return { type: 'group', children: kids }
      }, encode: { x: 0, y: [1, 2] },
      tooltip: { formatter: (p) => `${p.seriesName}, ${x[p.value[0]]}<br>${fmt(p.value[3], 'auto')} (${fmt(p.value[1], 'auto')} – ${fmt(p.value[2], 'auto')})` } })
  }
  for (const l of spec.lines || []) {
    series.push({ type: 'line', name: l.name, data: l.values.map(ok), symbol: 'circle', symbolSize: l.bold ? 6 : 4, z: 5,
      lineStyle: { width: l.bold ? 2.8 : 2, color: col(l.c), type: l.dash ? 'dashed' : 'solid' }, itemStyle: { color: col(l.c) } })
  }
  for (const pt of spec.points || []) {
    series.push({ type: 'custom', name: pt.name, z: 6, data: x.map((_, i) => [i, ok(pt.values[i])]),
      renderItem: (params, api) => {
        const v = api.value(1)
        if (v == null || Number.isNaN(v)) return null
        const c = api.coord([api.value(0), v]), sh = api.size([1, 0])[0] * (pt.dx || 0)
        return pt.symbol === 'diamond'
          ? { type: 'polygon', shape: { points: [[c[0] + sh, c[1] - 6], [c[0] + sh + 6, c[1]], [c[0] + sh, c[1] + 6], [c[0] + sh - 6, c[1]]] }, style: { fill: col(pt.c) } }
          : { type: 'circle', shape: { cx: c[0] + sh, cy: c[1], r: 5 }, style: { fill: col(pt.c), stroke: CHART.label, lineWidth: 0.5 } }
      }, encode: { x: 0, y: 1 }, itemStyle: { color: col(pt.c) },
      tooltip: { formatter: (p) => `${p.seriesName}, ${x[p.value[0]]}: <b>${fmt(p.value[1], 'auto')}</b>` } })
  }
  const ml = [
    ...(spec.hrefs || []).map((r) => ({ yAxis: r.y, name: r.label, lineStyle: { type: 'dashed', color: CHART.limit }, label: { formatter: r.label, position: 'insideEndTop', color: CHART.label, textBorderWidth: 0 } })),
    ...(spec.vrefs || []).map((r) => ({ xAxis: String(r.x), name: r.label, lineStyle: { type: 'dashed', color: CHART.highlight }, label: { formatter: r.label, position: 'insideEndTop', color: CHART.label, textBorderWidth: 0 } })),
  ]
  // опорная невидимая линия: даёт оси данные и несёт отметки
  series.push({ type: 'line', name: '_', data: x.map(() => null), silent: true, legendHoverLink: false, tooltip: { show: false },
    markLine: ml.length ? { silent: true, symbol: 'none', data: ml } : undefined })
  return {
    grid: { left: 70, right: 24, top: 44, bottom: 42 },
    tooltip: { trigger: 'item' },
    legend: { top: 0, type: 'scroll', data: series.filter((q) => q.name && q.name !== '_').map((q) => q.name) },
    xAxis: { type: 'category', data: x, name: spec.x_title || '', nameLocation: 'middle', nameGap: 26 },
    yAxis: axisY(spec.y_title || '', log ? { type: 'log', logBase: 10 } : spec.y_max ? { max: spec.y_max, min: 0 } : {}),
    series,
  }
}

// Кривая по возрастам (коэффициент уловистости): горизонтальные границы и вертикальные отметки на дробном возрасте
export function curveChart(spec) {
  const xs = spec.x_num || spec.x
  const lab = new Map(xs.map((v, i) => [v, spec.x[i]]))
  const series = spec.series.map((s, k) => ({ type: 'line', name: s.name, data: s.values.map((v, i) => [xs[i], v]),
    symbol: 'circle', symbolSize: k === 0 ? 7 : 5, lineStyle: { width: k === 0 ? 2.6 : 2, type: s.dash ? 'dashed' : 'solid', color: k === 0 ? CHART.main : CHART.fit },
    itemStyle: { color: k === 0 ? CHART.main : CHART.fit } }))
  const ml = [
    ...(spec.hrefs || []).map((r) => ({ yAxis: r.y, name: r.label, lineStyle: { type: 'dashed', color: CHART.limit }, label: { formatter: r.label, position: 'insideEndTop', color: CHART.label, textBorderWidth: 0 } })),
    ...(spec.vrefs || []).filter((r) => r.x != null).map((r, i) => ({ xAxis: r.x, name: r.label,
      lineStyle: { type: r.dash ? 'dotted' : 'solid', color: CHART.highlight, width: 1.6 },
      label: { formatter: r.label, position: i % 2 ? 'insideMiddleTop' : 'insideEndTop', color: CHART.highlight, textBorderWidth: 0 } })),
  ]
  if (series.length) series[0].markLine = { silent: true, symbol: 'none', data: ml }
  const lo = Math.min(...xs), hi = Math.max(...xs)
  return {
    grid: { left: 62, right: 24, top: 44, bottom: 42 },
    tooltip: { trigger: 'axis', formatter: (ps) => `${spec.x_title}: <b>${lab.get(ps[0].value[0]) ?? ps[0].value[0]}</b><br>`
      + ps.map((q) => `${q.marker}${q.seriesName}: <b>${fmt(q.value[1], 3)}</b>`).join('<br>') },
    legend: { top: 0 },
    xAxis: { type: 'value', min: lo, max: hi, interval: 1, name: spec.x_title || '', nameLocation: 'middle', nameGap: 26,
      axisLabel: { formatter: (v) => lab.get(v) ?? '' }, splitLine: { show: false } },
    yAxis: axisY(spec.y_title || '', { min: 0, max: spec.y_max || null, axisLabel: { formatter: (v) => fmt(v, 1) } }),
    series,
  }
}

export function buildChart(spec, ctype, opts) {
  if (!spec) return null
  if (spec.kind === 'fit') return fitChart(spec, ctype || spec.default)
  if (spec.kind === 'curve') return curveChart(spec)
  if (spec.kind === 'dots') return dotsChart(spec, ctype || spec.default)
  if (spec.kind === 'band') return bandChart(spec, ctype || spec.default)
  if (spec.kind === 'series') return seriesChart(spec, ctype || spec.default || 'line', opts)
  if (spec.kind === 'heatmap') return heatmapChart(spec, opts)
  if (spec.kind === 'box') return boxChart(spec, opts)
  if (spec.kind === 'lifecycle') return lifecycleChart(spec)
  if (spec.kind === 'dual') return dualChart(spec, opts)
  return null
}
