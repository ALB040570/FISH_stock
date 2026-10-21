// Тема интерфейса «Глубокая вода» (утверждена 20.10.2026, см. docs/ui_theme.md).
// Единственный источник цветов для JavaScript (графики ECharts, карта Leaflet), где CSS-переменные недоступны.
// Значения CSS обязаны совпадать с переменными --fs-* в assets/app.css — это проверяет тест theme.test.js.

export const CSS = {
  primary: '#0E5E6F', // основной: кнопки, ссылки, активные элементы
  'primary-hover': '#0B4B59',
  'primary-2': '#14919B', // вторичный бирюзовый (линии, иконки)
  'primary-soft': '#A9D3D6', // светлая бирюза: фоновые ряды графиков
  selected: '#E7EFF1', // выделенная строка / пункт
  hover: '#F0F5F6',
  accent: '#F2A541', // янтарь: только ПДУ, прогноз, ключевые акценты
  'accent-text': '#9A5B0A', // янтарь для текста (контраст AA)
  nav: '#0E5E6F', // боковое меню
  'nav-active': '#0B4B59',
  'nav-text': '#E4F1F2',
  'nav-muted': '#B7DCE0',
  bg: '#F4F7F8',
  card: '#FFFFFF',
  'card-soft': '#F9FBFB',
  line: '#DCE5E8',
  'line-soft': '#EBF0F2',
  text: '#1C2B33',
  muted: '#5B6F78',
  faint: '#74858D',
  code: '#F2F6F7',
  success: '#1B7A4B',
  warning: '#A9650F',
  danger: '#C0392B',
  info: '#6B7C85',
}

// Палитра рядов графиков (виды рыб, сценарии). Проверена на различимость, в т. ч. при нарушениях
// цветового зрения: минимальное ΔE (CIECAM02-UCS) ≥ 13 при обычном зрении, ≥ 7 при полной дейтер-/протан-/тританопии.
export const CHART_PALETTE = ['#0E5E6F', '#E07B39', '#3E7CC9', '#8E5BA8', '#5BA05B', '#C8486A', '#6FC2C6', '#8C6D46', '#3F4A52', '#E6C440']

// Роли цветов на графиках
export const CHART = {
  main: CSS.primary, // основная величина
  fit: CSS['primary-2'], // модельная кривая
  background: CSS['primary-soft'], // фоновый/сопоставляемый ряд (биомасса запаса, исторический ПДУ)
  highlight: '#E89A2C', // ПДУ и прогноз
  limit: CSS.danger, // границы допустимого
  grid: CSS['line-soft'],
  axis: CSS.line,
  label: CSS.muted,
}

// Состояние водоёма на карте (смысл цветов утверждён в плане, раздел 5)
export const MAP_STATE = { no_data: '#9AA3AB', has_data: '#2F6FD1', has_run: '#2E9E5B', stale: '#E8862A' }
// mask — заливка за пределами Казахстана (= фон страницы), land — страна в режиме «без подложки», region — границы областей
export const MAP = { border: CSS.primary, shape: CSS.primary, markerStroke: '#FFFFFF', mask: CSS.bg, land: '#FFFFFF',
  region: '#8FB3BA' }

// Состояние шага запуска
export const RUN_STEP = { done: '#2E9E5B', reused: '#8FCDAA', running: '#2F6FD1', failed: '#C0392B', cancelled: '#E8862A',
  skipped: '#C9D3D7', pending: '#C9D3D7' }

export const FONT = 'Inter, "Segoe UI", "Helvetica Neue", Roboto, Arial, "Noto Sans", sans-serif'

// Тема ECharts: регистрируется в EChart.vue
export const ECHARTS_THEME = {
  color: CHART_PALETTE,
  backgroundColor: 'transparent',
  textStyle: { fontFamily: FONT, color: CSS.text },
  legend: { textStyle: { color: CSS.text } },
  tooltip: { backgroundColor: '#FFFFFF', borderColor: CSS.line, borderWidth: 1, textStyle: { color: CSS.text },
    extraCssText: 'box-shadow: 0 4px 14px rgba(28,43,51,.10); border-radius: 6px;' },
  categoryAxis: { axisLine: { lineStyle: { color: CHART.axis } }, axisTick: { lineStyle: { color: CHART.axis } },
    axisLabel: { color: CHART.label }, nameTextStyle: { color: CHART.label }, splitLine: { lineStyle: { color: CHART.grid } } },
  valueAxis: { axisLine: { lineStyle: { color: CHART.axis } }, axisLabel: { color: CHART.label },
    nameTextStyle: { color: CHART.label }, splitLine: { lineStyle: { color: CHART.grid } } },
  dataZoom: { borderColor: CSS.line, fillerColor: 'rgba(14,94,111,.12)', handleStyle: { color: CSS.primary } },
}

// Тепловые карты: последовательная шкала (число ловов, доли) и расходящаяся (отклонения ±, синий — ниже, оранжевый — выше)
export const HEAT = {
  seq: ['#F2F8F8', '#BFE0E2', '#6FC2C6', '#14919B', '#0E5E6F', '#073A45'],
  div: ['#2B5FA8', '#8DB2E0', '#F5F6F4', '#F2B27E', '#C25420'],
  label: CSS.text, labelOnDark: '#FFFFFF',
}
// Замечания «На что обратить внимание»
export const SIGNAL = { error: CSS.danger, warning: CSS.warning, info: CSS.info }
