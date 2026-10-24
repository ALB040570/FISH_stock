// Справочник «Организации» (сервис моделирования данных) — для профиля пользователя (решение № 58).
import { api } from './api'

export const ORG_ENTITY = 'organizations'
export const ORG_DICT_PATH = '/design/dictionaries/entities/' + ORG_ENTITY

/** Записи справочника → [{ code, name, short }] по алфавиту; название — на языке интерфейса, если есть. */
export function orgOptions(records, lang = 'ru') {
  return (records || []).filter((r) => !r.deleted && r.values?.code)
    .map((r) => {
      const v = r.values
      const name = (lang === 'kk' && v.name_kk) || v.name_ru || v.code
      return { code: v.code, name, short: v.short_name || '' }
    })
    .sort((a, b) => a.name.localeCompare(b.name, 'ru'))
}

/** Название организации по коду; код, которого нет в справочнике (удалена), показывается как есть. */
export function orgName(options, code) {
  if (!code) return ''
  const o = (options || []).find((x) => x.code === code)
  return o ? (o.short || o.name) : code
}

export async function loadOrgs(lang) {
  try { return orgOptions(await api.get('data-model', `/entities/${ORG_ENTITY}/records`), lang) } catch (e) { return [] }
}
