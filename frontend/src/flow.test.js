import { describe, expect, it } from 'vitest'
import { buildFlow, mapState, resultLink, runProgress, stageLink, stageOf } from './flow'

const D = (at) => ({ updated_at: at, datasets: { catches: {}, ages: {} } })
const R = (id, at, extra = {}) => ({ id, created_at: at, finished_at: at, ...extra })

describe('состояние водоёма', () => {
  it('карта', () => {
    expect(mapState(null, null)).toBe('no_data')
    expect(mapState(D('2026-10-20'), null)).toBe('has_data')
    expect(mapState(D('2026-10-20'), { last_done: R('a', '2026-10-21') })).toBe('has_run')
    expect(mapState(D('2026-10-23'), { last_done: R('a', '2026-10-21') })).toBe('stale')
    expect(mapState(D('2026-10-23'), { last_done: R('a', '2026-10-21') }, { hideInternal: true })).toBe('has_run')
  })
  it('этапы', () => {
    expect(stageOf(null).stage).toBe('no_data')
    expect(stageOf(D('2026-10-20'), null).stage).toBe('wait_calc')
    expect(stageOf(D('2026-10-23'), { last_done: R('a', '2026-10-21'), main_run: R('a', '2026-10-21') }).stage).toBe('wait_calc')
    expect(stageOf(D('2026-10-20'), { last_done: R('a', '2026-10-21') }).stage).toBe('wait_main')
    expect(stageOf(D('2026-10-20'), { last_done: R('b', '2026-10-22'), main_run: R('a', '2026-10-21') }).stage).toBe('ready')
    expect(stageOf(D('2026-10-21T12'), { last_done: R('b', '2026-10-22'), main_run: R('a', '2026-10-21') }).stage).toBe('wait_main')
    expect(stageOf(D('2026-10-20'), null, { id: 'q', status: 'queued' })).toMatchObject({ stage: 'running', queued: true })
    const f = stageOf(D('2026-10-20'), { last_run: { id: 'x', status: 'failed', created_at: '2026-10-22' } })
    expect(f).toMatchObject({ stage: 'wait_calc', failed: true })
    expect(stageLink({ code: 'z', ...f }).path).toBe('/calc/runs/x')
  })
  it('поток', () => {
    const fl = buildFlow({
      names: { z: 'Зайсан', b: 'Балхаш', k: 'Капчагай', s: 'Самаркандское', e: 'Пустой' },
      data: { z: D('2026-10-20'), b: D('2026-10-23'), k: D('2026-10-20'), s: D('2026-10-20') },
      runs: { z: { last_done: R('z1', '2026-10-21'), main_run: R('z1', '2026-10-21'),
        pdu: { source: 'forecast', rows: [{ species: 'судак', pdu_t: 1394, year: 2025 }, { species: 'лещ', pdu_t: 4488, year: 2025 }, { species: 'х', pdu_t: null }] } },
        b: { last_done: R('b1', '2026-10-21') },
        s: { last_done: R('s1', '2026-10-21') } },
      queue: { queued: [], running: [{ id: 'k1', water_body: 'k', status: 'running', steps: [{ status: 'done' }, { status: 'done' }, { status: 'running' }, {}, {}] }] },
    })
    expect(fl.byStage.wait_calc.map((x) => x.code)).toEqual(['b'])
    expect(fl.byStage.running.map((x) => x.code)).toEqual(['k'])
    expect(fl.byStage.wait_main.map((x) => x.code)).toEqual(['s'])
    expect(fl.byStage.ready.map((x) => x.code)).toEqual(['z'])
    expect(fl.byStage.no_data.map((x) => x.code)).toEqual(['e'])
    expect(fl).toMatchObject({ datasets: 8, withData: 4, running: 1, queued: 0, waiting: 2 })
    expect(fl.lastUpload.code).toBe('b')
    expect(runProgress(fl.byStage.running[0].run)).toEqual({ k: 3, n: 5 })
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
