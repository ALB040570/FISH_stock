// Состояние водоёма на пути данных — общее для карты и стартовой страницы «Поток» (docs/decisions.md, № 53, 55, 70).
// Только факты из сервисов: наборы данных (data-admin /water-bodies/status), основные расчёты алгоритмов водоёма и их
// устаревание (algo-admin /water-bodies/status), очередь расчётов (algo-admin /queue). Новых правил и порогов нет.

const hasMain = (r) => !!r && Object.keys(r.main || {}).length > 0

/** Цвет карты: нет данных / есть данные / есть основные расчёты / основные расчёты устарели. */
export function mapState(d, r, { hideInternal = false } = {}) {
  if (!d) return 'no_data'
  if (!hasMain(r)) return 'has_data'
  // наблюдателю «устарел» не показывается: мониторинг показывает готовые основные расчёты (№ 55)
  return (r.stale || []).length && !hideInternal ? 'stale' : 'has_run'
}

/** Активный расчёт водоёма (идёт или в очереди) из ответа /queue. */
export function activeRuns(queue) {
  const out = {}
  for (const c of [...(queue?.queued || []), ...(queue?.running || [])]) {
    const cur = out[c.water_body]
    if (!cur || c.state === 'running') out[c.water_body] = c
  }
  return out
}

/** Подпись идущего расчёта: буква алгоритма и ход выполнения, %. */
export function runProgress(calc) {
  const f = calc?.progress?.fraction
  return { letter: calc?.letter || '', pct: typeof f === 'number' ? Math.round(f * 100) : 0 }
}

/**
 * Этап водоёма на пути данных:
 * no_data — данных нет; wait_calc — данные есть, основных расчётов нет (или последний расчёт с ошибкой);
 * running — расчёт идёт или в очереди; stale — основные расчёты устарели (новые данные или пересчитан вход);
 * ready — основные расчёты актуальны.
 */
export function stageOf(d, r, active) {
  if (!d) return { stage: 'no_data' }
  if (active) return { stage: 'running', run: active, queued: active.state === 'queued' }
  if (!hasMain(r)) {
    const f = r?.last_failed
    return f ? { stage: 'wait_calc', failed: true, run: f } : { stage: 'wait_calc' }
  }
  if ((r.stale || []).length) return { stage: 'stale', n: r.stale.length }
  return { stage: 'ready' }
}

export const STAGES = ['wait_calc', 'running', 'stale', 'ready']

/** Водоёмы по этапам + числа для плиток. names — { код: название }. */
export function buildFlow({ names = {}, data = {}, runs = {}, queue = null }) {
  const active = activeRuns(queue)
  const byStage = Object.fromEntries([...STAGES, 'no_data'].map((s) => [s, []]))
  let datasets = 0
  let lastUpload = null
  for (const code of Object.keys({ ...names, ...data })) {
    const d = data[code]
    const st = stageOf(d, runs[code], active[code])
    byStage[st.stage].push({ code, name: names[code] || code, ...st, updated_at: d?.updated_at || null })
    if (d) {
      datasets += Object.keys(d.datasets || {}).length
      if (d.updated_at && (!lastUpload || d.updated_at > lastUpload.at)) lastUpload = { at: d.updated_at, code, name: names[code] || code }
    }
  }
  for (const s of Object.keys(byStage)) byStage[s].sort((a, b) => a.name.localeCompare(b.name, 'ru'))
  const withData = STAGES.reduce((n, s) => n + byStage[s].length, 0)
  // итог для первого взгляда: ПДУ по основным расчётам (этап «готово»); числа — из результата расчёта, без пересчёта,
  // виды не складываются (№ 45); ПДУ приложения (F = k·M) подписан как таковой и не смешивается с ПДУ НПЦ (№ 44)
  const results = byStage.ready.map((w) => {
    const pdu = runs[w.code]?.pdu
    const rows = (pdu?.rows || []).filter((r) => r.pdu_t !== null && r.pdu_t !== undefined).sort((a, b) => b.pdu_t - a.pdu_t)
    return { code: w.code, name: w.name, year: rows[0]?.year || null, rows, source: pdu?.source || null }
  })
  return {
    byStage, datasets, lastUpload, withData, total: Object.keys({ ...names, ...data }).length, results,
    running: (queue?.running || []).length, queued: (queue?.queued || []).length,
    waiting: byStage.wait_calc.length + byStage.stale.length,
  }
}

/** ПДУ водоёма в мониторинге: рассчитанный в приложении (если есть прогноз и он доступен роли) или официальный НПЦ. */
export const resultLink = (r, full = true) => `/monitoring/waterbody/${r.code}?tab=pdu&s=${full && r.rows.length && r.source !== 'npc' ? 'app' : 'npc'}`

/** Куда ведёт водоём в трубе: следующее действие этапа. */
export function stageLink(item) {
  switch (item.stage) {
    case 'wait_calc': return item.failed ? { path: '/calc/calculations/' + item.run.id } : { path: '/calc/calculations', query: { wb: item.code } }
    case 'running': return { path: '/calc/calculations/' + item.run.id }
    case 'stale': return { path: '/calc/calculations', query: { wb: item.code, stale: '1' } }
    case 'ready': return { path: '/monitoring/waterbody/' + item.code }
    default: return { path: '/input/datasets', query: { wb: item.code } }
  }
}
