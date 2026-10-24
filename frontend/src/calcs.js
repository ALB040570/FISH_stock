// Расчёты алгоритмов каталога (решение № 70): общие функции экранов кабинета «Расчёт запасов рыб».
import { api } from './api'

export const ACTIVE = ['queued', 'running']
export const isActive = (c) => ACTIVE.includes(c?.state)

/** «b. Уловистость невода…» — буква и название алгоритма. */
export const algoLabel = (a, tr) => (a?.letter ? a.letter + '. ' : '') + (tr ? tr(a, 'title') : a?.title_ru || a?.code || '')

/** Каталог: { код: алгоритм }, по порядку a–k. */
export async function loadCatalog() {
  const cat = await api.get('algo-admin', '/catalog')
  return { list: cat, byCode: Object.fromEntries(cat.map((a) => [a.code, a])) }
}

/** Входы алгоритма (коды) по манифесту последней версии. */
export const inputsOf = (a) => a?.manifest?.requires?.steps || a?.inputs || []

/** Параметры, задаваемые в расчёте (категория calc), — виды модели и прогноза. */
export const calcParamsOf = (a) => (a?.manifest?.parameters || []).filter((p) => p.category === 'calc')

export const dt = (s) => (s ? new Date(s).toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—')
export const dur = (s) => (s == null ? '—' : s >= 3600 ? `${Math.floor(s / 3600)} ч ${Math.round((s % 3600) / 60)} мин`
  : s >= 60 ? `${Math.floor(s / 60)} мин ${Math.round(s % 60)} с` : `${Math.round(s)} с`)

/** Специальное представление результата алгоритма (виджеты мониторинга). */
export const VIEWS = { seine_catchability: 'seine_curves', net_catchability: 'net_curves', net_likelihood: 'net_curves',
  pdu_by_age: 'pdu_breakdown', bayes_cohort: 'bayes_band', forecast_pdu: 'forecast_scenarios' }

/** Нагрузка результата в виде, который ждёт представление (кривые сети — в поле net). */
export function viewPayload(code, payload) {
  if (code === 'net_catchability') return { net: payload }
  return payload
}

/** Статья справки «методика этого алгоритма». */
export const METHOD = { seine_catchability: 'method-seine', net_catchability: 'method-net', seine_likelihood: 'method-stock',
  net_likelihood: 'method-stock', seine_stock: 'method-stock', net_stock: 'method-stock', combined_stock: 'method-stock',
  pdu_by_age: 'method-pdu-age', bayes_cohort: 'method-bayes', forecast_pdu: 'method-forecast' }
