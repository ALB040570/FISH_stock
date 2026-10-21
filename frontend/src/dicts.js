// Записи справочников: код → название на текущем языке (кэш на сеанс)
import { reactive } from 'vue'
import { api } from './api'
import i18n from './i18n'

const cache = reactive({})
const loading = {}

export function loadDict(entity, force = false) {
  if (force || !loading[entity]) {
    loading[entity] = api.get('data-model', `/entities/${entity}/records`)
      .then((rs) => {
        cache[entity] = Object.fromEntries(rs.filter((r) => !r.deleted).map((r) => [r.values.code || r.id, r.values]))
        return cache[entity]
      })
      .catch(() => { loading[entity] = null; return {} })
  }
  return loading[entity]
}

export function dictName(entity, code) {
  if (code === null || code === undefined || code === '') return ''
  const r = (cache[entity] || {})[code]
  if (!r) return String(code)
  return (i18n.global.locale.value === 'kk' && r.name_kk) || r.name_ru || String(code)
}

export function dictNames(entity, codes) {
  return (codes || []).map((c) => dictName(entity, c)).join(', ')
}

export function dictOptions(entity) {
  return Object.entries(cache[entity] || {}).map(([code, v]) => ({ code, label: dictName(entity, code), v }))
}
