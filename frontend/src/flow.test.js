import { describe, expect, it } from 'vitest'
import { buildFlow, mapState, resultLink, runProgress, stageLink, stageOf } from './flow'

const D = (at) => ({ updated_at: at, datasets: { catches: {}, ages: {} } })
const M = (extra = {}) => ({ main: { seine_catchability: { id: 'b1' }, pdu_by_age: { id: 'h1' } }, stale: [], active: [], ...extra })

describe('состояние водоёма (решение № 66)', () => {
  it('карта', () => {
    expect(mapState(null, null)).toBe('no_data')
    expect(mapState(D('2026-10-20'), null)).toBe('has_data')
    expect(mapState(D('2026-10-20'), { main: {}, stale: [] })).toBe('has_data')
    expect(mapState(D('2026-10-20'), M())).toBe('has_run')
    expect(mapState(D('2026-10-23'), M({ stale: ['h1'] }))).toBe('stale')
    expect(mapState(D('2026-10-23'), M({ stale: ['h1'] }), { hideInternal: true })).toBe('has_run')
  })
  it('этапы', () => {
    expect(stageOf(null).stage).toBe('no_data')
    expect(stageOf(D('2026-10-20'), null).stage).toBe('wait_calc')
    expect(stageOf(D('2026-10-20'), M()).stage).toBe('ready')
    expect(stageOf(D('2026-10-20'), M({ stale: ['b1', 'h1'] }))).toMatchObject({ stage: 'stale', n: 2 })
    expect(stageOf(D('2026-10-20'), null, { id: 'q', state: 'queued' })).toMatchObject({ stage: 'running', queued: true })
    const f = stageOf(D('2026-10-20'), { main: {}, last_failed: { id: 'x', state: 'failed' } })
    expect(f).toMatchObject({ stage: 'wait_calc', failed: true })
    expect(stageLink({ code: 'z', ...f }).path).toBe('/calc/calculations/x')
    expect(stageLink({ code: 'z', stage: 'stale' })).toEqual({ path: '/calc/calculations', query: { wb: 'z', stale: '1' } })
  })
  it('поток', () => {
    const fl = buildFlow({
      names: { z: 'Зайсан', b: 'Балхаш', k: 'Капчагай', s: 'Самаркандское', e: 'Пустой' },
      data: { z: D('2026-10-20'), b: D('2026-10-23'), k: D('2026-10-20'), s: D('2026-10-20') },
      runs: { z: M({ pdu: { source: 'forecast', rows: [{ species: 'судак', pdu_t: 1394, year: 2025 }, { species: 'лещ', pdu_t: 4488, year: 2025 }, { species: 'х', pdu_t: null }] } }),
        s: M({ stale: ['h1'] }) },
      queue: { queued: [], running: [{ id: 'k1', water_body: 'k', state: 'running', letter: 'd', progress: { fraction: 0.42 } }] },
    })
    expect(fl.byStage.wait_calc.map((x) => x.code)).toEqual(['b'])
    expect(fl.byStage.running.map((x) => x.code)).toEqual(['k'])
    expect(fl.byStage.stale.map((x) => x.code)).toEqual(['s'])
    expect(fl.byStage.ready.map((x) => x.code)).toEqual(['z'])
    expect(fl.byStage.no_data.map((x) => x.code)).toEqual(['e'])
    expect(fl).toMatchObject({ datasets: 8, withData: 4, running: 1, queued: 0, waiting: 2 })
    expect(fl.lastUpload.code).toBe('b')
    expect(runProgress(fl.byStage.running[0].run)).toEqual({ letter: 'd', pct: 42 })
    expect(stageLink(fl.byStage.running[0]).path).toBe('/calc/calculations/k1')
    expect(stageLink(fl.byStage.wait_calc[0])).toEqual({ path: '/calc/calculations', query: { wb: 'b' } })
    expect(stageLink(fl.byStage.ready[0]).path).toBe('/monitoring/waterbody/z')
    // итог ПДУ: только основные расчёты, по убыванию, без пустых, виды не складываются
    expect(fl.total).toBe(5)
    expect(fl.results.map((r) => r.code)).toEqual(['z'])
    expect(fl.results[0].rows.map((r) => r.species)).toEqual(['лещ', 'судак'])
    expect(fl.results[0].year).toBe(2025)
    expect(resultLink(fl.results[0])).toBe('/monitoring/waterbody/z?tab=pdu&s=app')
    expect(resultLink({ code: 'q', rows: [] })).toBe('/monitoring/waterbody/q?tab=pdu&s=npc')
    expect(resultLink(fl.results[0], false)).toBe('/monitoring/waterbody/z?tab=pdu&s=npc')   // без права на результаты (№ 62)
  })
})
