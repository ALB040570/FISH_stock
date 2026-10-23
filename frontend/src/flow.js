// Состояние водоёма на пути данных — общее для карты и стартовой страницы «Поток» (docs/decisions.md, № 53, 55).
// Только факты из сервисов: наборы данных (data-admin /water-bodies/status), запуски и основной запуск
// (algo-admin /water-bodies/status), очередь (algo-admin /queue). Новых правил и порогов нет.

/** Цвет карты: нет данных / есть данные / есть расчёт / данные новее расчёта. */
export function mapState(d, r, { hideInternal = false } = {}) {
  if (!d) return 'no_data'
  const done = r && (r.main_run || r.last_done)
  if (!done) return 'has_data'
  const stale = !!(d.updated_at && done.finished_at && d.updated_at > done.finished_at)
  // наблюдателю «данные новее расчёта» не показывается: мониторинг показывает готовый расчёт (№ 55)
  return stale && !hideInternal ? 'stale' : 'has_run'
}

/** Активный запуск водоёма (идёт или в очереди) из ответа /queue. */
export function activeRuns(queue) {
  const out = {}
  for (const r of [...(queue?.queued || []), ...(queue?.running || [])]) {
    const cur = out[r.water_body]
    if (!cur || r.status === 'running') out[r.water_body] = r
  }
  return out
}

/** Этап запуска «k из n» (k — шаг, который выполняется). */
export function runProgress(run) {
  const steps = run?.steps || []
  const done = steps.filter((s) => ['done', 'reused', 'skipped'].includes(s.status)).length
  return { k: Math.min(done + 1, steps.length || 1), n: steps.length }
}

/**
 * Этап водоёма на пути данных:
 * no_data — данных нет; wait_calc — данные есть, расчёта нет или данные новее последнего расчёта;
 * running — запуск идёт или в очереди; wait_main — свежий расчёт есть, но основным не отмечен (или основной
 * старше данных); ready — основной расчёт не старше данных.
 */
export function stageOf(d, r, active) {
  if (!d) return { stage: 'no_data' }
  if (active) return { stage: 'running', run: active, queued: active.status === 'queued' }
  const done = r?.last_done
  if (!done || (d.updated_at && done.finished_at && d.updated_at > done.finished_at)) {
    // последний запуск завершился ошибкой — тот же этап, но с пометкой и ссылкой на запуск
    const last = r?.last_run
    const failed = !!last && last.status === 'failed' && (!done || last.created_at > done.created_at)
    return failed ? { stage: 'wait_calc', failed: true, run: last } : { stage: 'wait_calc' }
  }
  const main = r?.main_run
  if (!main || (d.updated_at && main.finished_at && d.updated_at > main.finished_at)) return { stage: 'wait_main', run: done }
  return { stage: 'ready', run: main }
}

export const STAGES = ['wait_calc', 'running', 'wait_main', 'ready']

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
  return {
    byStage, datasets, lastUpload, withData,
    running: (queue?.running || []).length, queued: (queue?.queued || []).length,
    waiting: byStage.wait_calc.length + byStage.wait_main.length,
  }
}

/** Куда ведёт водоём в трубе: следующее действие этапа. */
export function stageLink(item) {
  switch (item.stage) {
    case 'wait_calc': return item.failed ? { path: '/calc/runs/' + item.run.id } : { path: '/calc/calculations', query: { wb: item.code } }
    case 'running': return { path: '/calc/runs/' + item.run.id }
    case 'wait_main': return { path: '/calc/runs/' + item.run.id }
    case 'ready': return { path: '/monitoring/waterbody/' + item.code }
    default: return { path: '/input/datasets', query: { wb: item.code } }
  }
}
