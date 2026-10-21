// Справочник «Области»: коды → названия на текущем языке (кэш на сеанс)
import { ref } from 'vue'
import { api } from './api'
import i18n from './i18n'

const byCode = ref({})
let loading = null

export function loadRegions() {
  if (!loading) {
    loading = api.get('data-model', '/entities/regions/records')
      .then((rs) => { byCode.value = Object.fromEntries(rs.filter((r) => !r.deleted).map((r) => [r.values.code, r.values])) })
      .catch(() => { loading = null })
  }
  return loading
}

export function regionName(code) {
  const r = byCode.value[code]
  if (!r) return code
  return (i18n.global.locale.value === 'kk' && r.name_kk) || r.name_ru || code
}

export function regionNames(codes) {
  return (codes || []).map(regionName).join(', ')
}
