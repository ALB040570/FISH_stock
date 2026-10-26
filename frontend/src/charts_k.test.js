// Слайды «Сценарии k» (алгоритм j 3.1.0): графики строятся из спецификаций представлений fc_k и fc_k_risk.
import { describe, expect, it } from 'vitest'
import { buildChart } from './components/charts'

const x = ['0,5', '0,75', '1', '1,25', '1,5']

describe('сценарии k', () => {
  it('ПДУ от k: полосы, медиана, ПДУ НПЦ и отметка k = 1', () => {
    const spec = { kind: 'band', x, default: 'linear', vrefs: [{ x: '1', label: 'F = M' }], x_title: 'k', y_title: 'тонн',
      bands: [{ name: 'ПДУ, 95 %', lo: [10, 15, 20, 25, 30], hi: [25, 37, 50, 62, 75], op: 0.16, c: 1 }],
      lines: [{ name: 'ПДУ 2025, медиана', values: [17, 26, 34, 42, 50], c: 1, bold: true },
              { name: 'ПДУ НПЦ 2024', values: [51, 51, 51, 51, 51], c: 3, dash: true }] }
    const o = buildChart(spec)
    expect(o.xAxis.data || o.xAxis[0]?.data).toEqual(x)
    const names = o.series.map((s) => s.name)
    expect(names).toContain('ПДУ 2025, медиана')
    expect(o.series.find((s) => s.name === 'ПДУ НПЦ 2024').lineStyle.type).toBe('dashed')
  })
  it('риск снижения: проценты от 0 до 100', () => {
    const spec = { kind: 'fit', x, default: 'linear', allowed: ['linear'], y_max: 100, x_title: 'k', y_title: '%',
      series: [{ name: 'F = k·M', values: [0, 14, 56, 88, 97], type: 'line', c: 1, bold: true },
               { name: 'без промысла', values: [2, 2, 2, 2, 2], type: 'line', c: 2, dash: true }] }
    const o = buildChart(spec)
    const y = Array.isArray(o.yAxis) ? o.yAxis[0] : o.yAxis
    expect(y.max).toBe(100)
    expect(o.series.map((s) => s.name)).toEqual(['F = k·M', 'без промысла'])
  })
})
