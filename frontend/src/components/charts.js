// Общий вид графиков: спокойная палитра, читаемые оси, числа с пробелами.
export const PALETTE = ['#1d5c7a', '#2a9d8f', '#e08a1e', '#7b5ea7', '#c44536', '#6c8a2e', '#3b82c4', '#b5651d', '#8a8f98', '#d4a017', '#4f6d7a', '#a23b72']

export function fmt(v, d = 0) {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  const a = Math.abs(v)
  if (d === 'auto') d = a >= 100 ? 0 : a >= 1 ? 2 : 3
  return Number(v).toLocaleString('ru-RU', { maximumFractionDigits: d, minimumFractionDigits: 0 })
}

export function compact(v) {
  if (v === null || v === undefined) return ''
  const a = Math.abs(v)
  if (a >= 1e9) return (v / 1e9).toLocaleString('ru-RU', { maximumFractionDigits: 1 }) + ' млрд'
  if (a >= 1e6) return (v / 1e6).toLocaleString('ru-RU', { maximumFractionDigits: 1 }) + ' млн'
  if (a >= 1e3) return (v / 1e3).toLocaleString('ru-RU', { maximumFractionDigits: 1 }) + ' тыс'
  return v.toLocaleString('ru-RU', { maximumFractionDigits: 3 })
}

export function base({ x, series, yName = '', type = 'line', stack = false, legend = true, xName = '' }) {
  return {
    color: PALETTE,
    grid: { left: 64, right: 18, top: legend ? 36 : 16, bottom: 34, containLabel: false },
    tooltip: { trigger: 'axis', valueFormatter: (v) => fmt(v, 'auto') },
    legend: legend ? { top: 0, type: 'scroll', icon: 'roundRect', itemWidth: 12, itemHeight: 8 } : undefined,
    xAxis: { type: 'category', data: x, name: xName, nameLocation: 'middle', nameGap: 24, axisTick: { alignWithLabel: true } },
    yAxis: { type: 'value', name: yName, nameTextStyle: { align: 'left' }, axisLabel: { formatter: compact }, splitLine: { lineStyle: { color: '#edf1f5' } } },
    series: series.map((s) => ({ type, name: s.name ?? '', data: s.values, stack: stack ? 'a' : undefined, smooth: false,
      showSymbol: type === 'line' && (x?.length || 0) < 25, connectNulls: false, barMaxWidth: 28, ...(s.extra || {}) })),
  }
}

// Полоса интервала (2,5–97,5 %, 25–75 %) + медиана + точки наблюдений
export function band({ x, q, name = 'медиана', obs = [], yName = '', color = '#1d5c7a' }) {
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
    yAxis: { type: 'value', name: yName, axisLabel: { formatter: compact }, splitLine: { lineStyle: { color: '#edf1f5' } } },
    series,
  }
}
