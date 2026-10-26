// Страница «Сравнение расчётов» (№ 77): ссылка с набором рядов, подписи, графики и таблица.
import { describe, expect, it } from 'vitest'
import { decodeItem, fromQuery, itemKey, kf, pduChart, riskChart, seriesLabels, seriesStyle, stockChart, tableRows, tableYears,
  toQuery, uniqItems } from './compare'
import { legacyToNew } from './cabinets'

const t = (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k)
const YH = [2020, 2021, 2022, 2023, 2024]
const YF = [2025, 2026, 2027, 2028, 2029]
const Q = (base) => [0.6, 0.8, 1, 1.2, 1.5].map((f) => YH.map((_, j) => base * (j + 1) * f))
const FQ = (base) => [0.6, 0.8, 1, 1.2, 1.5].map((f) => YF.map((_, j) => base * (5 - j) * f))

function fc(k, extra = {}) {
  return { source: 'forecast', calc: 'C1', species: 'lesh', k, water_body: 'zhaysan', water_body_name: 'Жайсан', calc_title: 'Прогноз', is_main: true,
    species_name: 'лещ', years_hist: YH, years_fc: YF, hist_q: Q(100), fc_q: FQ(100 * (2 - k)), join_q: [300, 400, 500, 600, 750],
    pdu_years: YF.map(() => 30 * k), pdu1_q: [20 * k, 25 * k, 30 * k, 35 * k, 40 * k], end_q: [1, 2, 3, 4, 5], risk: 0.1 * k, F: 0.2 * k, ...extra }
}

describe('ссылка', () => {
  it('ряды кодируются и читаются обратно', () => {
    const items = [{ source: 'forecast', calc: '01ABC', species: 'lesh', k: 0.25 }, { source: 'model', calc: '01M', species: 'sazan' },
      { source: 'catch', calc: '01G', species: 'sudak', gear: 'невод' }]
    expect(items.map(itemKey)).toEqual(['f~01ABC~lesh~0.25', 'm~01M~sazan', 'c~01G~sudak~s'])
    const q = toQuery({ items, measure: 'fishable', log: true, bands: false })
    expect(q).toEqual({ s: ['f~01ABC~lesh~0.25', 'm~01M~sazan', 'c~01G~sudak~s'], m: 'f', log: '1', b: '0' })
    expect(fromQuery(q)).toEqual({ items, measure: 'fishable', log: true, bands: false })
    expect(fromQuery({})).toEqual({ items: [], measure: 'total', log: false, bands: null })
    expect(fromQuery({ s: 'f~X~lesh~1' }).items).toEqual([{ source: 'forecast', calc: 'X', species: 'lesh', k: 1 }])   // один ряд — строка
  })
  it('испорченные ряды и повторы отбрасываются, не больше 12', () => {
    expect(decodeItem('z~1~2')).toBeNull()
    expect(decodeItem('f~1')).toBeNull()
    expect(decodeItem('f~1~lesh~-1')).toBeNull()
    expect(decodeItem('f~1~lesh~0,5').k).toBe(0.5)
    expect(decodeItem('c~1~lesh~q').gear).toBe('сеть+невод')
    const many = Array.from({ length: 15 }, (_, i) => ({ source: 'forecast', calc: 'C', species: 'lesh', k: i / 10 }))
    expect(uniqItems([...many.slice(0, 2), many[0], null]).length).toBe(2)
    expect(uniqItems(many).length).toBe(12)
  })
  it('адрес страницы не считается старым адресом мониторинга водоёма', () => {
    expect(legacyToNew('/monitoring/compare?s=f~1~lesh~1')).toBeNull()
    expect(legacyToNew('/monitoring/zhaysan')).toBe('/monitoring/waterbody/zhaysan')
  })
})

describe('подписи рядов', () => {
  it('показывают только различия, общее — отдельно', () => {
    const s = [fc(0), fc(1), fc(2)]
    const { labels, common } = seriesLabels(s, t)
    expect(labels).toEqual(['k = 0', 'k = 1', 'k = 2'])
    expect(common).toBe('Жайсан · лещ · Прогноз ★ · cmp.src_forecast_short')
    const w = seriesLabels([fc(1), fc(1, { water_body_name: 'Капчагай', calc_title: 'Прогноз К', is_main: true })], t)
    expect(w.labels).toEqual(['Жайсан · Прогноз ★', 'Капчагай · Прогноз К ★'])
    expect(seriesLabels([fc(0.25)], t).labels[0]).toBe('Жайсан · лещ · Прогноз ★ · cmp.src_forecast_short · k = 0,25')
    expect(kf(0.25)).toBe('0,25')
  })
  it('k = 0 — пунктир, после десятого ряда — точки', () => {
    expect(seriesStyle(0, fc(0)).dash).toBe('dashed')
    expect(seriesStyle(1, fc(1)).dash).toBeNull()
    expect(seriesStyle(10, fc(1)).dash).toBe('dotted')
  })
})

describe('графики и таблица', () => {
  it('численность: общая история один раз, прогноз от последнего года истории, интервалы по выбору', () => {
    const s = [fc(0), fc(1)]
    const { labels } = seriesLabels(s, t)
    const o = stockChart(s, { labels, bands: false, t })
    const lines = o.series.filter((x) => x.type === 'line' && x.name !== '_')
    expect(lines.map((l) => l.name)).toEqual(['cmp.history', 'k = 0', 'k = 1'])
    expect(o.xAxis.data).toEqual([...YH, ...YF].map(String))
    expect(lines[0].data.slice(0, 5)).toEqual(Q(100)[2])
    expect(lines[1].data.slice(4)).toEqual([500, ...FQ(200)[2]])               // от последнего года истории
    expect(lines[1].lineStyle.type).toBe('dashed')
    expect(o.series.filter((x) => x.type === 'custom').length).toBe(0)
    const b = stockChart(s, { labels, bands: true, t })
    expect(b.series.filter((x) => x.type === 'custom').length).toBe(3)          // история + 2 прогноза, по 95 %
    const one = stockChart([fc(1)], { labels: ['k = 1'], bands: true, t, log: true })
    expect(one.series.filter((x) => x.type === 'custom').length).toBe(4)        // один ряд — 95 % и 50 %
    expect(one.yAxis.type).toBe('log')
    expect(one.tooltip.trigger).toBe('axis')
  })
  it('модель и запас по уловам — линии истории в цвете ряда; ошибочные ряды пропускаются', () => {
    const m = { source: 'model', calc: 'B', species: 'lesh', years_hist: YH, years_fc: [], hist_q: Q(90), fc_q: null, water_body_name: 'Жайсан' }
    const c = { source: 'catch', calc: 'G', species: 'lesh', gear: 'невод', years_hist: YH, years_fc: [], hist_q: [YH.map(() => 7)], fc_q: null }
    const bad = { source: 'forecast', calc: 'C', species: 'x', k: 3, error: 'нет k' }
    const o = stockChart([m, c, bad], { labels: ['модель', 'по уловам', 'плохой'], bands: true, t })
    const lines = o.series.filter((x) => x.type === 'line' && x.name !== '_')
    expect(lines.map((l) => l.name)).toEqual(['модель', 'по уловам'])
    expect(lines[1].data).toEqual(YH.map(() => 7).concat(YF.map(() => null)).slice(0, 5))
    expect(o.series.filter((x) => x.type === 'custom').length).toBe(1)          // у оценки по уловам нет интервала
    expect(pduChart([m, c], { labels: ['a', 'b'], t })).toBeNull()
    expect(riskChart([m, c], { labels: ['a', 'b'], t })).toBeNull()
  })
  it('ПДУ по годам, риск и итоги', () => {
    const s = [fc(0), fc(1), fc(2)]
    const labels = ['k = 0', 'k = 1', 'k = 2']
    const p = pduChart(s, { labels, t })
    expect(p.series.map((x) => x.data)).toEqual([YF.map(() => 0), YF.map(() => 30), YF.map(() => 60)])
    const r = riskChart(s, { labels, t })
    expect(r.series[0].data.map((d) => Math.round(d.value))).toEqual([0, 10, 20])
    expect(r.yAxis.max).toBe(100)
    const rows = tableRows(s, labels)
    expect(rows[2]).toMatchObject({ label: 'k = 2', pdu: 60, pdu_lo: 40, pdu_hi: 80, F: 0.4, last_year: 2024, last: 500, y1: 2025, yE: 2029 })
    expect(rows[1].end).toBe(FQ(100)[2][4])
    expect(rows[1].risk).toBeCloseTo(10)
    expect(tableYears(rows)).toEqual({ y1: 2025, yE: 2029, last: 2024 })
    expect(tableRows([{ source: 'forecast', error: 'нет' }], ['x'])[0]).toMatchObject({ error: 'нет', label: 'x' })
  })
})
