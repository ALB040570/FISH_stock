// Тема «Степь и небо», светлая и тёмная схемы: совпадение цветов CSS и JS, отсутствие жёстко прописанных цветов,
// контраст текста (WCAG AA), различимость палитры и статусов, переключение схемы.
import { describe, expect, it } from 'vitest'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { CHART, CHART_PALETTE, CSS, MAP_STATE, THEMES, setTheme, themeMode } from './theme'

const SRC = join(process.cwd(), 'src') // тесты запускаются из каталога frontend (npm test)
const appCss = readFileSync(join(SRC, 'assets/app.css'), 'utf8')
// блоки переменных: :root — светлая схема, html.dark — тёмная
const block = (sel) => { const i = appCss.indexOf(sel + ' {'); return appCss.slice(i, appCss.indexOf('\n}', i)) }
const CSS_BLOCK = { light: block(':root'), dark: block('html.dark') }

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

describe.each(['light', 'dark'])('схема %s', (mode) => {
  const T = THEMES[mode]

  it('переменные --fs-* в app.css совпадают с theme.js', () => {
    for (const [k, v] of Object.entries(T.css)) {
      const m = CSS_BLOCK[mode].match(new RegExp(`--fs-${k}:\\s*(#[0-9A-Fa-f]{6})`))
      expect(m, `--fs-${k} нет в блоке ${mode}`).not.toBeNull()
      expect(m[1].toUpperCase(), `--fs-${k}`).toBe(v.toUpperCase())
    }
  })

  it('контраст текста не ниже 4,5:1 (WCAG AA)', () => {
    const c = T.css
    const pairs = [
      ['text', 'bg'], ['text', 'card'], ['muted', 'bg'], ['muted', 'card'], ['muted', 'card-soft'],
      ['primary', 'card'], ['primary', 'selected'], ['primary-hover', 'selected'], ['accent-text', 'card'],
      ['nav-text', 'nav'], ['nav-muted', 'nav'], ['nav-text', 'nav-active'], ['success', 'card'], ['warning', 'card'],
      ['danger', 'card'], ['on-primary', 'primary'], ['link', 'card'], ['link', 'bg'], ['link', 'selected'],
    ]
    for (const [fg, bg] of pairs) expect(contrast(c[fg], c[bg]), `${mode}: ${fg} на ${bg}`).toBeGreaterThanOrEqual(4.5)
  })

  it('палитра: 10 разных цветов, линии заметны на карточке; статусы карты — 4 разных цвета', () => {
    expect(new Set(T.palette).size).toBe(10)
    const min = mode === 'dark' ? 4 : 2
    for (const p of T.palette) expect(contrast(p, T.css.card), `${mode}: ${p}`).toBeGreaterThanOrEqual(min)
    expect(new Set(Object.values(T.mapState)).size).toBe(4)
  })
})

describe('тема', () => {
  it('тёмная схема без чистого чёрного и чистого белого', () => {
    const d = THEMES.dark.css
    for (const k of ['bg', 'card', 'nav']) expect(d[k].toUpperCase()).not.toBe('#000000')
    expect(d.text.toUpperCase()).not.toBe('#FFFFFF')
  })

  it('в компонентах нет цветов, кроме белого: только переменные темы', () => {
    const bad = []
    for (const f of files(SRC).filter((p) => /\.(vue|js)$/.test(p) && !/theme(\.test)?\.js$/.test(p))) {
      const s = readFileSync(f, 'utf8')
      for (const m of s.matchAll(/#[0-9a-fA-F]{3,6}\b/g)) if (!/^#fff(fff)?$/i.test(m[0])) bad.push(`${f}: ${m[0]}`)
    }
    expect(bad).toEqual([])
  })

  it('переключение схемы меняет реактивные цвета и класс страницы', () => {
    setTheme('dark', { remember: false })
    expect(themeMode.value).toBe('dark')
    expect(CSS.bg).toBe(THEMES.dark.css.bg)
    expect([...CHART_PALETTE]).toEqual(THEMES.dark.palette)
    expect(CHART.highlight).toBe(THEMES.dark.chart.highlight)
    expect(MAP_STATE.has_data).toBe(THEMES.dark.mapState.has_data)
    expect(document.documentElement.classList.contains('dark')).toBe(true)
    setTheme('light', { remember: false })
    expect(CSS.bg).toBe(THEMES.light.css.bg)
    expect(document.documentElement.classList.contains('dark')).toBe(false)
  })
})
