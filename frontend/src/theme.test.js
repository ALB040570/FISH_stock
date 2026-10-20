// Тема «Глубокая вода»: совпадение цветов CSS и JS, отсутствие жёстко прописанных цветов, контраст текста (WCAG AA).
import { describe, expect, it } from 'vitest'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { CSS, CHART_PALETTE, MAP_STATE } from './theme'

const SRC = join(process.cwd(), 'src') // тесты запускаются из каталога frontend (npm test)
const appCss = readFileSync(join(SRC, 'assets/app.css'), 'utf8')

function lum(hex) {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4))
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
}
const contrast = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05) }

function files(dir) {
  return readdirSync(dir).flatMap((n) => {
    const p = join(dir, n)
    return statSync(p).isDirectory() ? files(p) : [p]
  })
}

describe('тема', () => {
  it('переменные --fs-* в app.css совпадают с theme.js', () => {
    for (const [k, v] of Object.entries(CSS)) {
      const m = appCss.match(new RegExp(`--fs-${k}:\\s*(#[0-9A-Fa-f]{6})`))
      expect(m, `--fs-${k} нет в app.css`).not.toBeNull()
      expect(m[1].toUpperCase(), `--fs-${k}`).toBe(v.toUpperCase())
    }
  })

  it('в компонентах нет цветов, кроме белого: только переменные темы', () => {
    const bad = []
    for (const f of files(SRC).filter((p) => /\.(vue|js)$/.test(p) && !/theme(\.test)?\.js$/.test(p))) {
      const s = readFileSync(f, 'utf8')
      for (const m of s.matchAll(/#[0-9a-fA-F]{3,6}\b/g)) if (!/^#fff(fff)?$/i.test(m[0])) bad.push(`${f}: ${m[0]}`)
    }
    expect(bad).toEqual([])
  })

  it('контраст текста не ниже 4,5:1 (WCAG AA)', () => {
    const pairs = [
      ['text', 'bg'], ['text', 'card'], ['muted', 'bg'], ['muted', 'card'], ['muted', 'card-soft'],
      ['primary', 'card'], ['primary', 'selected'], ['primary-hover', 'selected'], ['accent-text', 'card'],
      ['nav-text', 'nav'], ['nav-muted', 'nav'], ['nav-text', 'nav-active'], ['success', 'card'], ['warning', 'card'],
      ['danger', 'card'],
    ]
    for (const [fg, bg] of pairs) expect(contrast(CSS[fg], CSS[bg]), `${fg} на ${bg}`).toBeGreaterThanOrEqual(4.5)
    expect(contrast('#FFFFFF', CSS.primary), 'белый на основной кнопке').toBeGreaterThanOrEqual(4.5)
  })

  it('палитра графиков: 10 разных цветов; статусы карты — 4 разных цвета', () => {
    expect(new Set(CHART_PALETTE).size).toBe(10)
    expect(new Set(Object.values(MAP_STATE)).size).toBe(4)
  })
})
