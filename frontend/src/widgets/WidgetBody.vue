<template>
  <div class="wbody">
    <!-- графики -->
    <template v-if="mode === 'chart'">
      <EChart v-if="chartOption" ref="ec" :option="chartOption" :height="chartHeight" @pick="onPick" />
      <div v-else-if="widget.type === 'text'" class="txt">{{ widget.options?.text }}</div>
      <component :is="special" v-else-if="widget.type === 'special' && special" :data="data" :filters="filters" :options="widget.options" />
      <div v-else class="state muted small">{{ $t('wv.no_chart') }}</div>
    </template>
    <!-- плитки -->
    <div v-else-if="mode === 'tiles' && data.warnings?.length" class="warns">
      <div v-for="(w, i) in data.warnings" :key="i" class="sig lv-warning"><el-icon class="si"><WarningFilled /></el-icon><span>{{ w.text }}</span></div>
    </div>
    <div v-if="mode === 'tiles'" class="tiles">
      <div v-for="(t, i) in tiles" :key="i" class="tile" :class="{ link: t.section, warn: t.level === 'warning' }" @click="t.section && $emit('section', t.section)">
        <div class="tv" :class="signCls(t)">{{ tileValue(t) }}<span v-if="t.unit" class="tu">{{ t.unit === '%' ? ' %' : ' ' + shortUnit(t.unit) }}</span></div>
        <div class="tl">{{ t.label }}</div>
        <div v-if="t.hint" class="th">{{ t.hint }}</div>
      </div>
      <div v-if="!tiles.length" class="state muted small">{{ $t('common.empty') }}</div>
    </div>
    <!-- карточки видов -->
    <div v-else-if="mode === 'cards'" class="cards">
      <div v-for="c in data.cards" :key="c.title" class="sp-card">
        <div class="sp-t">{{ c.title }}</div>
        <div v-for="it in c.items" :key="it.label" class="sp-i"><span class="muted">{{ it.label }}</span><b>{{ cardValue(it) }}</b></div>
      </div>
    </div>
    <!-- замечания -->
    <div v-else-if="mode === 'signals'" class="signals" :style="{ maxHeight: height }">
      <div v-for="(s, i) in data.signals" :key="i" class="sig" :class="'lv-' + s.level" @click="$emit('section', s.section)">
        <el-icon class="si"><WarningFilled v-if="s.level !== 'info'" /><InfoFilled v-else /></el-icon>
        <span>{{ s.text }}</span>
      </div>
      <div v-if="!data.signals?.length" class="state muted small">{{ $t('wv.no_signals') }}</div>
    </div>
    <!-- светофор видов -->
    <!-- можно ли верить запасу -->
    <TrustTable v-else-if="mode === 'trust'" :data="data" :height="height" @species="(c) => $emit('species', c)"
                @open="(c, w) => board?.openSpeciesAt ? board.openSpeciesAt(c, w) : $emit('species', c)" />
    <StockTrustTable v-else-if="mode === 'stock_trust'" :data="data" :height="height" @species="(c) => $emit('species', c)"
                     @open="(c, w) => board?.openSpeciesAt ? board.openSpeciesAt(c, w) : $emit('species', c)" />
    <TrafficTable v-else-if="mode === 'traffic'" :data="data" :height="height" @species="(c) => $emit('species', c)" />
    <!-- журнал ловов -->
    <JournalTable v-else-if="mode === 'journal'" :data="data" :height="height" :title="title" />
    <!-- таблица -->
    <div v-else-if="mode === 'table'">
      <el-table :data="table.rows" size="small" :max-height="height" border :row-class-name="rowCls" @row-click="onRow">
        <el-table-column v-for="c in table.columns" :key="c.code" :prop="c.code" :label="colTitle(c)"
                         :min-width="c.code === 'issue' || c.code === 'text' ? 360 : c.code === 'place' || c.code === 'species' ? 160 : Math.min(190, Math.max(100, String(c.title).length * 6.5))"
                         :align="isNum(c) ? 'right' : 'left'" :fixed="c === table.columns[0] && table.columns.length > 8 ? 'left' : false">
          <template #default="{ row }"><span :class="cellCls(row, c)">{{ cell(row[c.code], c) }}</span></template>
        </el-table-column>
      </el-table>
      <div v-if="data.total > (data.rows || []).length" class="muted small" style="margin-top:4px">{{ data.rows.length }} / {{ data.total }}</div>
    </div>
  </div>
</template>
<script setup>
import { computed, inject, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import EChart from '../components/EChart.vue'
import { base, buildChart, fmt } from '../components/charts'
import specials from './specials'
import { tableOf } from './views'
import TrafficTable from './TrafficTable.vue'
import TrustTable from './TrustTable.vue'
import StockTrustTable from './StockTrustTable.vue'
import JournalTable from './JournalTable.vue'

const p = defineProps({ widget: Object, data: Object, mode: String, ctype: String, height: String, filters: Object, species: Object, title: String })
const emit = defineEmits(['pick', 'section', 'row', 'species'])
const { t } = useI18n()
const board = inject('board', null)
const ec = ref(null)
const special = computed(() => specials[p.widget.options?.kind])
const spName = (c) => p.species?.[c] || c
const table = computed(() => tableOf(p.widget, p.data, spName))
const highlight = computed(() => board?.highlight.value ?? null)
// тепловая карта с множеством строк (ловы) — выше, чтобы подписи строк не пропадали
const chartHeight = computed(() => {
  const ch = p.widget.type === 'view' ? p.data?.chart : null
  if (ch?.kind === 'heatmap') return Math.max(parseInt(p.height), ch.y.length * 19 + 100) + 'px'
  if (ch?.kind === 'lifecycle') return Math.max(parseInt(p.height), ch.species.length * 34 + 80) + 'px'
  return p.height
})

const chartOption = computed(() => {
  const d = p.data
  if (!d) return null
  if (p.widget.type === 'view') return buildChart(d.chart, p.ctype, { highlight: highlight.value })
  if ((p.widget.type === 'line' || p.widget.type === 'bar' || p.widget.type === 'kpi') && d.series) {
    const series = d.series.map((s, i) => ({ key: s.name ?? 'v' + i, name: s.name == null ? d.y_title : spName(s.name), values: s.values }))
    const isYear = /year/.test(p.widget.options?.x || '')
    const ct = p.ctype || (p.widget.type === 'kpi' ? 'bar' : p.widget.type)
    return buildChart({ kind: 'series', x: d.x, series, x_is_year: isYear, y_title: p.widget.options?.unit || '' }, ct, { highlight: highlight.value })
  }
  return null
})
void base

const tiles = computed(() => {
  if (p.data?.tiles?.length) return p.data.tiles
  if (p.data?.series) return p.data.series.map((s) => ({ label: s.name == null ? p.data.y_title : spName(s.name), value: [...s.values].reverse().find((v) => v != null) }))
  return []
})
const shortUnit = (u) => (String(u).length > 18 ? '' : u)
const tileValue = (t2) => (typeof t2.value === 'number' ? (t2.signed && t2.value > 0 ? '+' : '') + fmt(t2.value, 'auto') : (t2.value ?? '—'))
const signCls = (t2) => (t2.signed && typeof t2.value === 'number' ? (t2.value < 0 ? 'neg' : t2.value > 0 ? 'pos' : '') : '')
function cardValue(it) {
  if (it.value === null || it.value === undefined) return '—'
  if (it.type === 'boolean') return it.value ? t('common.yes') : t('common.no')
  return fmt(it.value, 'auto') + (it.unit ? ' ' + it.unit : '')
}
const isNum = (c) => ['number', 'integer'].includes(c.type)
const colTitle = (c) => c.title + (c.unit && !String(c.title).includes(c.unit) && c.unit !== '%' ? ', ' + c.unit : c.unit === '%' && !String(c.title).includes('%') ? ', %' : '')
function cell(v, c) {
  if (v === null || v === undefined || v === '') return '—'
  if (typeof v === 'boolean') return v ? t('common.yes') : t('common.no')
  if (c.code === 'level') return t('wv.level_' + v)
  if (typeof v === 'number') return c.code === 'year' ? v : c.type === 'integer' ? fmt(v, 0) : fmt(v, 'auto')
  return v
}
const cellCls = (row, c) => (c.code === 'level' ? 'lv-' + row.level : row._current ? 'cur' : '')
const rowCls = ({ row }) => [row._current ? 'cur-row' : '', row._level === 'warning' ? 'warn-row' : '', p.data?.drill?.by_row || p.data?.row_action ? 'clickable' : ''].join(' ')
function onRow(row) {
  // результаты расчёта: строка вида — все данные по виду; строка года — выбрать год для всех слайдов раздела
  if (p.data?.row_action === 'species' && row._code) { emit('species', row._code); return }
  if (p.data?.row_action === 'year' && row.year && board?.setYear) { board.setYear(row.year); return }
  if (p.data?.drill?.by_row) emit('row', row)
}

function onPick(e) {
  const d = p.data
  const spec = p.widget.type === 'view' ? d?.chart : { kind: 'series', x: d?.x, x_is_year: /year/.test(p.widget.options?.x || '') }
  if (!spec) return
  let x = null, y = null, series = null, xi = null, yi = null
  if (spec.kind === 'heatmap') {
    [xi, yi] = e.value; x = spec.x[xi]; y = spec.y[yi]
  } else if (spec.kind === 'box') {
    xi = e.seriesType === 'boxplot' ? e.dataIndex : e.value[0]; x = spec.x[xi]
  } else if (spec.kind === 'lifecycle' || spec.kind === 'dots' || spec.kind === 'curve') {
    return
  } else if (spec.kind === 'band') {
    xi = Array.isArray(e.value) ? e.value[0] : e.dataIndex; x = spec.x?.[xi]
    if (spec.pick_year && board?.setYear && /^\d{4}$/.test(String(x))) board.setYear(Number(x))
    return
  } else {
    xi = e.dataIndex; x = spec.x?.[xi]
    const s = (spec.series || []).find((q) => q.name === e.seriesName)
    series = s ? s.key : null
  }
  if (spec.kind === 'heatmap' && spec.y_codes) {        // паспорт: клетка «вид × год» — все данные по виду за этот год
    if (board?.setYear && /^\d{4}$/.test(String(x))) board.setYear(Number(x))
    if (spec.y_codes[yi]) emit('species', spec.y_codes[yi])
    return
  }
  if (spec.pick_year && board?.setYear) {
    const yy = spec.kind === 'heatmap' ? y : x
    if (yy != null && /^\d{4}$/.test(String(yy))) { board.setYear(Number(yy)); return }
  }
  const yearAxis = spec.x_is_year ? x : spec.y_is_year ? y : null
  if (yearAxis != null && board) board.setHighlight(yearAxis)
  emit('pick', { x, y, xi, yi, series, seriesName: e.seriesName })
}
function image() { return ec.value?.image() || null }
defineExpose({ image })
</script>
<style scoped>
.txt { white-space: pre-wrap; line-height: 1.5; }
.warns { display: flex; flex-direction: column; gap: 6px; margin-bottom: 10px; }
.warns .sig { cursor: default; }
:deep(.clickable) { cursor: pointer; }
:deep(.warn-row) td:first-child { box-shadow: inset 3px 0 0 var(--fs-warning); }
.tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; }
.tile { border: 1px solid var(--fs-line); border-radius: 8px; padding: 10px 12px; background: var(--fs-card-soft); }
.tile.link { cursor: pointer; }
.tile.link:hover { background: var(--fs-hover); border-color: var(--fs-primary-2); }
.tile.warn .tv { color: var(--fs-warning); }
.tv { font-size: 22px; font-weight: 600; color: var(--fs-primary); line-height: 1.2; }
.tv.neg { color: var(--fs-danger); }
.tv.pos { color: var(--fs-success); }
.tu { font-size: 12px; font-weight: 400; color: var(--fs-muted); }
.tl { font-size: 12.5px; color: var(--fs-text); margin-top: 2px; }
.th { font-size: 11.5px; color: var(--fs-muted); }
.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 10px; }
.sp-card { border: 1px solid var(--fs-line); border-radius: 8px; padding: 10px 12px; }
.sp-t { font-weight: 600; margin-bottom: 6px; }
.sp-i { display: flex; justify-content: space-between; gap: 8px; font-size: 12.5px; padding: 2px 0; border-bottom: 1px dashed var(--fs-line-soft); }
.signals { overflow-y: auto; display: flex; flex-direction: column; gap: 6px; }
.sig { display: flex; gap: 8px; align-items: flex-start; padding: 7px 10px; border-radius: 6px; background: var(--fs-card-soft);
  border-left: 3px solid var(--fs-info); cursor: pointer; line-height: 1.4; }
.sig:hover { background: var(--fs-hover); }
.sig.lv-warning { border-left-color: var(--fs-warning); }
.sig.lv-error { border-left-color: var(--fs-danger); }
.si { margin-top: 2px; color: var(--fs-info); flex: none; }
.lv-warning .si, span.lv-warning { color: var(--fs-warning); }
.lv-error .si, span.lv-error { color: var(--fs-danger); }
span.lv-info { color: var(--fs-info); }
.cur { font-weight: 600; }
:deep(.cur-row) td { background: var(--fs-selected) !important; }
:deep(.clickable) { cursor: pointer; }
</style>
