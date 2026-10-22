// Тема интерфейса «Степь и небо» (утверждена 22.10.2026): тёмно-синий, небесный, золото — мотив флага РК.
// Две схемы: светлая и тёмная (тёмная — для пользователей, которым тяжело смотреть на белое: без чистого чёрного
// и чистого белого, приглушённые цвета). Подробности — docs/ui_theme.md.
//
// Единственный источник цветов для JavaScript (графики ECharts, карта Leaflet), где CSS-переменные недоступны.
// Значения THEMES.<схема>.css обязаны совпадать с --fs-* в assets/app.css (:root — светлая, html.dark — тёмная);
// это проверяет theme.test.js. Экспортируемые CSS, CHART, MAP … — реактивные: графики и карта перекрашиваются
// при переключении схемы без перезагрузки страницы.
import { reactive, ref } from 'vue'

const LIGHT_CSS = {
  primary: '#16324F', // основной: тёмно-синий — кнопки, ссылки, активные элементы
  'primary-hover': '#0F2540',
  'primary-2': '#00A3C4', // небесный: линии, значки
  'primary-soft': '#B9D9E6', // светло-небесный: фоновые ряды графиков
  'on-primary': '#FFFFFF', // текст на основном цвете
  selected: '#E6EEF6', // выделенная строка / пункт
  hover: '#F0F4F8',
  accent: '#E8B40C', // золото: только ПДУ, прогноз, логотип, метка активного пункта меню
  'accent-text': '#8A6A00', // золото для текста (контраст AA)
  nav: '#16324F', // боковое меню
  'nav-active': '#0F2540',
  'nav-text': '#E3EAF2',
  'nav-muted': '#A9BCD0',
  bg: '#F6F7F9',
  card: '#FFFFFF',
  'card-soft': '#FAFBFC',
  line: '#DDE2EA',
  'line-soft': '#ECEFF3',
  text: '#1A2230',
  muted: '#566275',
  faint: '#737F8F',
  code: '#F2F4F7',
  success: '#1B7A4B',
  warning: '#A9650F',
  danger: '#C0392B',
  info: '#66717F',
}

const DARK_CSS = {
  primary: '#5BBCD8', // на тёмном фоне основной — небесный (тёмно-синий неразличим)
  'primary-hover': '#7CCBE2',
  'primary-2': '#7CCBE2',
  'primary-soft': '#2E4A63',
  'on-primary': '#0B1620', // тёмный текст на небесном
  selected: '#233649',
  hover: '#1F2C3A',
  accent: '#F0C548',
  'accent-text': '#F0C548',
  nav: '#0D141C',
  'nav-active': '#1D2C3C',
  'nav-text': '#D8E0E9',
  'nav-muted': '#93A3B5',
  bg: '#121A24', // не чистый чёрный
  card: '#18222E',
  'card-soft': '#1D2834',
  line: '#2C3A49',
  'line-soft': '#243140',
  text: '#DDE4EC', // не чистый белый — меньше засветки
  muted: '#A3AFBD',
  faint: '#8693A2',
  code: '#1D2834',
  success: '#55C893',
  warning: '#E5A94A',
  danger: '#F08174',
  info: '#9AA6B2',
}

// Палитры рядов (виды рыб, сценарии). Проверены на различимость при нарушениях цветового зрения
// (ΔE CIECAM02-UCS, полная дейтер-/протан-/тританопия): светлая — основа Окабе–Ито, мин. ΔE 11,0;
// тёмная — мин. ΔE 6,9, контраст с фоном карточки ≥ 4:1. Расчёт — docs/ui_theme.md.
const LIGHT_PALETTE = ['#16324F', '#E69F00', '#56B4E9', '#009E73', '#D55E00', '#CC79A7', '#0072B2', '#8C6D46', '#595960', '#732E2E']
const DARK_PALETTE = ['#D3DAE2', '#F0A23C', '#62BEEE', '#2DB78A', '#F07A3A', '#DE8DB8', '#7A9CF0', '#B26B8F', '#E0D187', '#657AE0']

function build(css, palette, dark) {
  return {
    css,
    palette,
    // роли цветов на графиках
    chart: {
      main: dark ? '#62BEEE' : css.primary, // основная величина
      fit: dark ? '#9ADDEB' : css['primary-2'], // модельная кривая
      background: dark ? '#4F7A9C' : css['primary-soft'], // фоновый/сопоставляемый ряд (биомасса запаса, исторический ПДУ); в тёмной — светлее, чтобы был виден
      highlight: dark ? '#F0C548' : '#E0A800', // ПДУ и прогноз — золото
      limit: css.danger, // границы допустимого
      grid: css['line-soft'],
      axis: css.line,
      label: css.muted,
    },
    // состояние водоёма на карте (смысл цветов утверждён в плане, раздел 5; «есть данные» — сине-фиолетовый,
    // чтобы не сливаться с небесным цветом интерфейса — решение 22.10.2026)
    mapState: dark ? { no_data: '#7D8894', has_data: '#8C8CF0', has_run: '#4CC38A', stale: '#F0A050' }
      : { no_data: '#9AA3AB', has_data: '#5B5BD6', has_run: '#2E9E5B', stale: '#E8862A' },
    // mask — заливка за пределами Казахстана (= фон страницы), land — страна в режиме «без подложки», region — границы областей
    map: dark ? { border: '#7CCBE2', shape: '#7CCBE2', markerStroke: css.bg, mask: css.bg, land: '#1A2633', region: '#3E556C' }
      : { border: css.primary, shape: css.primary, markerStroke: '#FFFFFF', mask: css.bg, land: '#FFFFFF', region: '#9DB0C6' },
    // состояние шага запуска
    runStep: dark ? { done: '#4CC38A', reused: '#2F6B52', running: '#62BEEE', failed: '#F08174', cancelled: '#F0A050', skipped: '#3A4757', pending: '#3A4757' }
      : { done: '#2E9E5B', reused: '#8FCDAA', running: '#00A3C4', failed: '#C0392B', cancelled: '#E8862A', skipped: '#C9D3DC', pending: '#C9D3DC' },
    // тепловые карты: последовательная шкала (число ловов, доли) и расходящаяся (отклонения ±: синий — ниже, оранжевый — выше);
    // подписи ячеек — цветом текста с обводкой цветом карточки (читаются на любой ячейке)
    heat: dark ? { seq: ['#1B2733', '#1F3D52', '#245E78', '#2F86A3', '#4FB0CC', '#8FD3E6'], div: ['#6B9BE0', '#35507A', '#26303C', '#7A4E33', '#E0874A'],
      label: css.text, outline: css.card }
      : { seq: ['#F3F8FB', '#C6E3EE', '#7FC8DD', '#2A8FB5', '#16324F', '#0B1A2B'], div: ['#2B5FA8', '#8DB2E0', '#F5F6F4', '#F2B27E', '#C25420'],
        label: css.text, outline: css.card },
    // замечания «На что обратить внимание»
    signal: { error: css.danger, warning: css.warning, info: css.info },
  }
}

export const THEMES = { light: build(LIGHT_CSS, LIGHT_PALETTE, false), dark: build(DARK_CSS, DARK_PALETTE, true) }

export const FONT = 'Inter, "Segoe UI", "Helvetica Neue", Roboto, Arial, "Noto Sans", sans-serif'

// Тема ECharts для схемы (регистрируются обе — EChart.vue)
export function echartsTheme(mode) {
  const t = THEMES[mode]; const c = t.css; const ch = t.chart
  return {
    color: t.palette,
    backgroundColor: 'transparent',
    textStyle: { fontFamily: FONT, color: c.text },
    title: { textStyle: { color: c.text } },
    legend: { textStyle: { color: c.text }, pageTextStyle: { color: c.muted }, pageIconColor: c.primary, pageIconInactiveColor: c.faint },
    tooltip: { backgroundColor: c.card, borderColor: c.line, borderWidth: 1, textStyle: { color: c.text },
      extraCssText: `box-shadow: 0 4px 14px rgba(0,0,0,${mode === 'dark' ? '.45' : '.10'}); border-radius: 6px;` },
    categoryAxis: { axisLine: { lineStyle: { color: ch.axis } }, axisTick: { lineStyle: { color: ch.axis } },
      axisLabel: { color: ch.label }, nameTextStyle: { color: ch.label }, splitLine: { lineStyle: { color: ch.grid } },
      splitArea: { areaStyle: { color: ['rgba(0,0,0,0)', mode === 'dark' ? 'rgba(255,255,255,0.025)' : 'rgba(0,0,0,0.02)'] } } },
    valueAxis: { axisLine: { lineStyle: { color: ch.axis } }, axisLabel: { color: ch.label },
      nameTextStyle: { color: ch.label }, splitLine: { lineStyle: { color: ch.grid } } },
    visualMap: { textStyle: { color: c.muted } },
    dataZoom: { borderColor: c.line, fillerColor: mode === 'dark' ? 'rgba(91,188,216,.15)' : 'rgba(22,50,79,.10)', handleStyle: { color: c.primary },
      textStyle: { color: c.muted } },
  }
}

// ------------------------------------------------------------------ текущая схема (реактивно)
const KEY = 'fishstock.theme'
function initialMode() {
  try { const m = localStorage.getItem(KEY); if (m === 'light' || m === 'dark') return m } catch (e) { /* приватный режим */ }
  try { return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light' } catch (e) { return 'light' }
}

export const themeMode = ref('light')
const copy = (o) => JSON.parse(JSON.stringify(o))
export const CSS = reactive(copy(LIGHT_CSS))
export const CHART_PALETTE = reactive([...LIGHT_PALETTE])
export const CHART = reactive(copy(THEMES.light.chart))
export const MAP_STATE = reactive(copy(THEMES.light.mapState))
export const MAP = reactive(copy(THEMES.light.map))
export const RUN_STEP = reactive(copy(THEMES.light.runStep))
export const HEAT = reactive(copy(THEMES.light.heat))
export const SIGNAL = reactive(copy(THEMES.light.signal))

export function setTheme(mode, { remember = true } = {}) {
  const m = mode === 'dark' ? 'dark' : 'light'
  const t = THEMES[m]
  Object.assign(CSS, copy(t.css))
  CHART_PALETTE.splice(0, CHART_PALETTE.length, ...t.palette)
  Object.assign(CHART, copy(t.chart)); Object.assign(MAP_STATE, copy(t.mapState)); Object.assign(MAP, copy(t.map))
  Object.assign(RUN_STEP, copy(t.runStep)); Object.assign(HEAT, copy(t.heat)); Object.assign(SIGNAL, copy(t.signal))
  themeMode.value = m
  if (typeof document !== 'undefined') {
    document.documentElement.classList.toggle('dark', m === 'dark')
    document.documentElement.style.colorScheme = m
  }
  if (remember) { try { localStorage.setItem(KEY, m) } catch (e) { /* приватный режим */ } }
}
export function toggleTheme() { setTheme(themeMode.value === 'dark' ? 'light' : 'dark') }
export function initTheme() { setTheme(initialMode(), { remember: false }) }
