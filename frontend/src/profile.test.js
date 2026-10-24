import { describe, expect, it } from 'vitest'
import { checkProfile } from './profile'
import { orgName, orgOptions } from './orgs'
import { centerSquare, initialsOf } from './avatar'

describe('профиль пользователя (решение № 58)', () => {
  it('проверка имени и почты', () => {
    expect(checkProfile({ name: '  ', email: '' })).toEqual({ name: 'profile.err_name', email: '' })
    expect(checkProfile({ name: 'Пётр', email: 'p@ex' })).toEqual({ name: '', email: 'profile.err_email' })
    expect(checkProfile({ name: 'Пётр', email: ' p@ex.kz ' })).toEqual({ name: '', email: '' })
  })
  it('инициалы', () => {
    expect(initialsOf('Пётр  Иванов Сидорович')).toBe('ПИ')
    expect(initialsOf('')).toBe('?')
  })
  it('квадрат по центру', () => {
    expect(centerSquare(400, 300)).toEqual({ sx: 50, sy: 0, side: 300 })
    expect(centerSquare(300, 500)).toEqual({ sx: 0, sy: 100, side: 300 })
  })
  it('справочник организаций', () => {
    // синтетические записи для теста
    const rec = [
      { values: { code: 'b', name_ru: 'Бета', name_kk: 'Бета-kk', short_name: 'Б' } },
      { values: { code: 'a', name_ru: 'Альфа' } },
      { deleted: true, values: { code: 'x', name_ru: 'Удалённая' } },
    ]
    const ru = orgOptions(rec, 'ru')
    expect(ru.map((o) => o.code)).toEqual(['a', 'b'])
    expect(orgOptions(rec, 'kk')[1].name).toBe('Бета-kk')
    expect(orgName(ru, 'b')).toBe('Б')
    expect(orgName(ru, 'a')).toBe('Альфа')
    expect(orgName(ru, 'gone')).toBe('gone')
    expect(orgName(ru, '')).toBe('')
  })
})
