<template>
  <div class="widget card" :style="{ gridColumn: 'span ' + (widget.w || 6) }">
    <div class="wh">
      <div class="wtt">
        <div class="wt"><span v-if="spTitle" class="spt">{{ spTitle }} · </span>{{ tr(widget, 'title') }}</div>
        <div v-if="subtitle" class="ws">{{ subtitle }}</div>
      </div>
      <div class="tools">
        <el-select v-if="data?.year_choices?.length && !data.calc_year" :model-value="yearSel ?? data.year" size="small" style="width:84px; margin-right:4px"
                   @update:model-value="(v) => (yearSel = v)">
          <el-option v-for="y in [...data.year_choices].reverse()" :key="y" :label="y" :value="y" />
        </el-select>
        <el-radio-group v-if="modes.length > 1" v-model="mode" size="small">
          <el-radio-button v-for="m in modes" :key="m" :value="m" :title="$t('wv.mode_' + m)">
            <el-icon><component :is="MODE_ICON[m]" /></el-icon>
          </el-radio-button>
        </el-radio-group>
        <el-dropdown v-if="mode === 'chart' && ctypes.length > 1 && !isScale" trigger="click" @command="(c) => (ctype = c)">
          <el-button size="small" text :title="$t('wv.chart_type')"><el-icon><Histogram /></el-icon></el-button>
          <template #dropdown><el-dropdown-menu>
            <el-dropdown-item v-for="c in ctypes" :key="c" :command="c" :class="{ on: c === curCtype }">{{ $t('wv.ct_' + c) }}</el-dropdown-item>
          </el-dropdown-menu></template>
        </el-dropdown>
        <template v-if="!big && board?.boardId">
          <el-button v-if="data?.explain" size="small" text :title="$t('mon.explain')" @click="openSide('explain')"><el-icon><InfoFilled /></el-icon></el-button>
          <el-button size="small" text :title="$t('mon.comments')" class="cmb" @click="openSide('comments')">
            <el-icon><ChatDotRound /></el-icon><span v-if="ccount" class="cmn">{{ ccount }}</span></el-button>
        </template>
        <el-button size="small" text :title="$t('wv.fullscreen')" @click="full = true"><el-icon><FullScreen /></el-icon></el-button>
        <el-dropdown v-if="canExport" trigger="click" @command="exportAs">
          <el-button size="small" text :title="$t('wv.download')"><el-icon><Download /></el-icon></el-button>
          <template #dropdown><el-dropdown-menu>
            <el-dropdown-item v-if="hasTable" command="xlsx">Excel</el-dropdown-item>
            <el-dropdown-item command="pdf">PDF</el-dropdown-item>
            <el-dropdown-item v-if="mode === 'chart' && hasChart" command="png">PNG</el-dropdown-item>
          </el-dropdown-menu></template>
        </el-dropdown>
        <slot name="tools" />
      </div>
    </div>
    <!-- варианты расчёта и шкала — отдельной строкой, чтобы не теснить заголовок -->
    <div v-if="data?.toggles?.length || (mode === 'chart' && isScale)" class="wctl">
        <el-radio-group v-for="tg in data?.toggles || []" :key="tg.key" :model-value="tg.value" size="small" 
                        :title="tg.title" @update:model-value="(v) => (board?.setCalcOpt ? board.setCalcOpt(tg.key, v) : (optSel[tg.key] = v))">
          <el-radio-button v-for="o in tg.options" :key="o.value" :value="o.value">{{ o.label }}</el-radio-button>
        </el-radio-group>
        <el-radio-group v-if="mode === 'chart' && isScale" v-model="ctype" size="small" >
          <el-radio-button v-for="c in ctypes" :key="c" :value="c">{{ $t('wv.ct_' + c) }}</el-radio-button>
        </el-radio-group>
    </div>
    <StateBlock :loading="loading" :error="error" :empty="!!data?.empty" :empty-text="emptyText" :retry="load">
      <template v-if="data">
        <WidgetBody ref="body" :widget="widget" :data="data" :mode="mode" :ctype="curCtype" :height="height" :filters="filters"
                    :species="species" :title="fullTitle" @pick="onPick" @section="goSection" @row="onRow" @species="(c) => board?.setSpecies(c)" />
        <div class="foot">
          <div v-if="sel" class="selbar">
            <span>{{ $t('wv.selected') }}: <b>{{ selLabel }}</b></span>
            <el-button v-if="canDrill" size="small" type="primary" link @click="drill">{{ $t('wv.show_rows') }}</el-button>
            <el-button size="small" link @click="clearSel">×</el-button>
          </div>
          <div v-for="(n, i) in data.notes || []" :key="i" class="note">{{ n }}</div>
          <div v-if="srcLine.length || data.filter_label" class="src">
            <span v-if="data.filter_label">{{ data.filter_label }}<template v-if="srcLine.length"> · </template></span>
            <template v-for="(s, i) in srcLine" :key="i"><router-link v-if="canGo('/input/')" :to="'/input/datasets/' + s.dataset_id">{{ s.title }} v{{ s.version }}</router-link><span v-else>{{ s.title }} v{{ s.version }}</span><span v-if="i < srcLine.length - 1">, </span></template>
          </div>
          <div v-if="data.meta?.calc_id || data.help" class="src">
            <template v-if="data.meta?.calc_id">
              {{ $t('wv.by_run') }} <router-link v-if="canGo('/calc/')" :to="'/calc/calculations/' + data.meta.calc_id">«{{ data.meta.calculation_title }}»</router-link><span v-else>«{{ data.meta.calculation_title }}»</span>
              <span v-if="data.meta.run_finished_at">&nbsp;{{ $t('wv.from') }} {{ new Date(data.meta.run_finished_at).toLocaleDateString('ru-RU') }}</span>
              <span v-if="data.meta.is_main === false"> · {{ $t('calcs.alternative') }}</span>
              <span v-if="data.meta.stale?.length" class="stale" :title="data.meta.stale.join('; ')"> · {{ $t('wv.stale') }}</span>
            </template>
            <template v-if="data.help"> · <router-link :to="helpPath(data.help)">{{ $t('wv.how') }}</router-link></template>
          </div>
        </div>
      </template>
    </StateBlock>
    <el-dialog v-model="full" fullscreen :title="fullTitle" append-to-body destroy-on-close>
      <div v-if="subtitle" class="ws" style="margin:-10px 0 10px">{{ subtitle }}</div>
      <div class="row" style="gap:8px; margin-bottom:10px">
        <el-radio-group v-if="modes.length > 1" v-model="mode" size="small">
          <el-radio-button v-for="m in modes" :key="m" :value="m">{{ $t('wv.mode_' + m) }}</el-radio-button>
        </el-radio-group>
        <el-radio-group v-if="mode === 'chart' && ctypes.length > 1" v-model="ctype" size="small">
          <el-radio-button v-for="c in ctypes" :key="c" :value="c">{{ $t('wv.ct_' + c) }}</el-radio-button>
        </el-radio-group>
      </div>
      <WidgetBody v-if="data && !data.empty" :widget="widget" :data="data" :mode="mode" :ctype="curCtype" :height="fullHeight" :filters="filters"
                  :species="species" :title="fullTitle" @pick="onPick" @section="(s) => { full = false; goSection(s) }" @row="onRow"
                  @species="(c) => { full = false; board?.setSpecies(c) }" />
      <div v-if="sel" class="selbar" style="margin-top:8px">
        <span>{{ $t('wv.selected') }}: <b>{{ selLabel }}</b></span>
        <el-button v-if="canDrill" size="small" type="primary" link @click="drill">{{ $t('wv.show_rows') }}</el-button>
      </div>
    </el-dialog>
    <el-drawer v-model="sideOpen" :title="fullTitle" size="440px" append-to-body>
      <ExplainPanel v-if="data?.explain" :explain="data.explain" @go="(w) => { sideOpen = false; board?.goWidget(w) }" />
      <div ref="cmAnchor" />
      <CommentsPanel :board-id="board?.boardId" :widget-id="widget.id" :water-body="filters?.water_body" :species="cmSpecies"
                     :years="board?.yearList?.value || []" @changed="board?.reloadCounts()" />
    </el-drawer>
    <el-drawer v-model="drillOpen" :title="drillTitle" size="70%" append-to-body>
      <StateBlock :loading="drillLoading" :error="drillErr">
        <template v-if="drillData">
          <div v-if="drillData.formula" class="formula">{{ drillData.formula }}
            <router-link v-if="drillData.help" :to="helpPath(drillData.help)" style="margin-left:6px">{{ $t('wv.how') }}</router-link></div>
          <div class="row" style="justify-content:space-between; margin-bottom:8px">
            <span class="muted small">{{ $t('wv.rows_found', { n: drillData.total }) }}</span>
            <router-link v-if="drillData.dataset_id && canGo('/input/')" :to="'/input/datasets/' + drillData.dataset_id">{{ $t('wv.open_dataset') }} →</router-link>
          </div>
          <el-table :data="drillData.rows" size="small" border max-height="78vh">
            <el-table-column v-for="c in drillData.columns" :key="c.code" :prop="c.code" :label="c.title" :min-width="c.code === 'place' ? 150 : 90"
                             :align="['number', 'integer'].includes(c.type) ? 'right' : 'left'">
              <template #default="{ row }">{{ dcell(row[c.code], c) }}</template>
            </el-table-column>
          </el-table>
        </template>
      </StateBlock>
    </el-drawer>
  </div>
</template>
<script setup>
import { computed, inject, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { api, downloadDataUrl, downloadPost } from '../api'
import i18n, { tr } from '../i18n'
import StateBlock from '../components/StateBlock.vue'
import { fmt } from '../components/charts'
import WidgetBody from './WidgetBody.vue'
import { canGo as canGoRole, helpPath } from '../cabinets'
import { useAuth } from '../store/auth'
import ExplainPanel from './ExplainPanel.vue'
import CommentsPanel from './CommentsPanel.vue'
import { tableOf } from './views'
// ссылки в кабинет, куда роль не входит, показываются текстом (docs/decisions.md, № 52)
const canGo = (p) => canGoRole(p, useAuth().role)
// ссылки в кабинет, куда роль не входит, показываются текстом (docs/decisions.md, № 52)

const MODE_ICON = { chart: 'TrendCharts', table: 'Grid', tiles: 'Menu', cards: 'Postcard', signals: 'Bell', traffic: 'Odometer', journal: 'Notebook', trust: 'CircleCheck', stock_trust: 'CircleCheck' }
const p = defineProps({ widget: Object, filters: Object, species: Object, big: Boolean })
const board = inject('board', null)
const { t, te } = useI18n()
const data = ref(null)
const loading = ref(false)
const error = ref(null)
const body = ref(null)
const sel = ref(null)
const yearSel = ref(null)
const optSel = reactive({})  // переключатели расчёта (уловистость по возрастам / средняя, по запасам / по улову)
const full = ref(false)
const fullHeight = computed(() => Math.max(380, window.innerHeight - 220) + 'px')
const height = computed(() => (p.big && board?.slideHeight ? board.slideHeight.value : (p.widget.h || 4) * 62 + 'px'))
// вид в названии: в режиме «Все данные по виду» у видовых виджетов
const spTitle = computed(() => (p.filters?.species && ['species', 'both'].includes(p.widget.scope || '')
  ? (p.species?.[p.filters.species] || p.filters.species) : ''))
const fullTitle = computed(() => (spTitle.value ? spTitle.value + ' · ' : '') + tr(p.widget, 'title'))
const cmSpecies = computed(() => (['species', 'both'].includes(p.widget.scope || '') ? p.filters?.species || null : null))
const ccount = computed(() => board?.counts?.value?.[p.widget.id] || 0)
const sideOpen = ref(false)
const cmAnchor = ref(null)
function openSide(what) {
  sideOpen.value = true
  if (what === 'comments') setTimeout(() => cmAnchor.value?.scrollIntoView({ behavior: 'smooth' }), 350)
}
const subtitle = computed(() => tr(p.widget, 'subtitle'))
const emptyText = computed(() => (data.value?.reason && te('w.reason_' + data.value.reason) ? t('w.reason_' + data.value.reason) : data.value?.message))

async function load() {
  if (p.widget.type === 'text') { data.value = {}; return }
  loading.value = true; error.value = null; sel.value = null
  try {
    data.value = await api.post('dashboards', '/widgets/data', {
      source: p.widget.source, filters: { ...p.filters, lang: i18n.global.locale.value },
      options: { ...(p.widget.options || {}), ...optSel, raw: p.widget.type === 'table', ...(yearSel.value ? { year: yearSel.value } : {}) },
    })
    if (board && data.value?.chart?.x_is_year) board.addYears(data.value.chart.x)
    if (board && data.value?.chart?.y_is_year) board.addYears(data.value.chart.y)
    if (board && data.value?.years) board.addYears(data.value.years)
    if (board?.setData) board.setData(p.widget.id, data.value)
  } catch (e) { error.value = e } finally { loading.value = false }
}
watch(() => [p.filters, p.widget, i18n.global.locale.value, yearSel.value, { ...optSel }], load, { deep: true, immediate: true })

// ---- виды отображения
const hasChart = computed(() => (p.widget.type === 'view' ? !!data.value?.chart : ['line', 'bar', 'kpi', 'special', 'text'].includes(p.widget.type)))
const hasTable = computed(() => tableOf(p.widget, data.value).columns.length > 0)
const modes = computed(() => {
  const d = data.value
  if (!d || d.empty) return []
  const m = []
  if (d.default_view === 'trust') m.push('trust')
  if (d.default_view === 'stock_trust') m.push('stock_trust')
  if (d.default_view === 'traffic') m.push('traffic')
  if (d.journal) m.push('journal')
  if (d.signals) m.push('signals')
  if (hasChart.value && p.widget.type !== 'table') m.push('chart')
  if (d.cards) m.push('cards')
  if ((d.tiles && d.tiles.length) || ['line', 'bar', 'kpi'].includes(p.widget.type)) m.push('tiles')
  if (hasTable.value && p.widget.type !== 'special') m.push('table')
  return m
})
const userMode = ref(null)
const mode = computed({
  get() {
    if (userMode.value && modes.value.includes(userMode.value)) return userMode.value
    const d = data.value || {}
    const def = d.default_view || (p.widget.type === 'kpi' ? 'tiles' : p.widget.type === 'table' ? 'table' : 'chart')
    return modes.value.includes(def) ? def : modes.value[0] || 'chart'
  },
  set(v) { userMode.value = v },
})
const ctypes = computed(() => (p.widget.type === 'view' ? data.value?.chart?.allowed || [] : ['line', 'bar'].includes(p.widget.type) ? ['line', 'bar'] : []))
const ctype = ref(null)
const isScale = computed(() => ['fit', 'dots', 'band'].includes(data.value?.chart?.kind) && ctypes.value.length > 1)
const curCtype = computed(() => (ctype.value && ctypes.value.includes(ctype.value) ? ctype.value
  : p.widget.type === 'view' ? data.value?.chart?.default : p.widget.type))
const canExport = computed(() => data.value && !data.value.empty && p.widget.type !== 'text')

// ---- источник
const srcLine = computed(() => data.value?.sources || (data.value?.meta?.dataset_id
  ? [{ dataset_id: data.value.meta.dataset_id, version: data.value.meta.version, title: t('wv.dataset') }] : []))

// ---- выбор точки и строки
const selLabel = computed(() => {
  const s = sel.value
  if (!s) return ''
  return [s.x, s.y, s.seriesName && !String(s.seriesName).endsWith('95 %') ? s.seriesName : null].filter((v) => v != null && v !== '').join(' · ')
})
const drillSpec = computed(() => data.value?.drill || (p.widget.source?.kind === 'dataset' && /year/.test(p.widget.options?.x || '')
  ? { dataset_type: p.widget.source.dataset_type, x: 'year' } : null))
const canDrill = computed(() => !!drillSpec.value && !drillSpec.value.by_row && (drillSpec.value.x || drillSpec.value.y))
function onPick(s) { sel.value = s }
function clearSel() { sel.value = null; board?.setHighlight(null) }
const num = (v) => (v !== null && v !== '' && !Number.isNaN(Number(v)) ? Number(v) : v)
function whereOf(s) {
  const d = drillSpec.value
  const w = { ...(d.fixed || {}), ...(data.value?.species_shown ? { _species: data.value.species_shown } : {}) }
  if (d.x && s.x != null) w[d.x] = num(s.x)
  if (d.y && s.y != null) w[d.y] = d.y_values ? d.y_values[s.yi] : num(s.y)
  if (d.series && s.series && !String(s.series).startsWith('v')) {
    if (d.series === 'species') w.species = s.series
    else w[d.series] = d.series === 'year' ? num(s.series) : s.series
  }
  return w
}
const drillOpen = ref(false)
const drillLoading = ref(false)
const drillErr = ref(null)
const drillData = ref(null)
const drillTitle = ref('')
async function runDrill(where, dtype, title) {
  drillOpen.value = true; drillLoading.value = true; drillErr.value = null; drillData.value = null; drillTitle.value = title
  try {
    drillData.value = await api.post('dashboards', '/widgets/drill', { source: p.widget.source, filters: { ...p.filters, lang: i18n.global.locale.value },
      options: { ...(p.widget.options || {}), ...(yearSel.value ? { year: yearSel.value } : {}) }, where, dataset_type: dtype })
    if (drillData.value?.title) drillTitle.value = drillData.value.title
  } catch (e) { drillErr.value = e } finally { drillLoading.value = false }
}
function drill() {
  const w = whereOf(sel.value)
  if (drillSpec.value.dataset_type === 'catches' && board?.openJournal) {
    board.openJournal({ ...w, catch_type: w.catch_type || p.widget.options?.catch_type })
    return
  }
  runDrill(w, drillSpec.value.dataset_type, `${fullTitle.value}: ${selLabel.value}`)
}
function onRow(row) { if (row.where) runDrill({ ...row.where, _all_types: true }, row.dataset_type, `${row.issue} · ${row.year}`) }
function dcell(v, c) {
  if (typeof v === 'boolean') return v ? '+1' : '—'
  if (v === null || v === undefined || v === '') return '—'
  if (c.type === 'date') { const [y, m, d] = String(v).split('-'); return `${d}.${m}.${y}` }
  if (typeof v === 'number') return c.type === 'integer' || c.code === 'year' ? v : fmt(v, 'auto')
  return v
}
function goSection(s) { if (s && board) board.setSection(s) }

// ---- выгрузка
function context() {
  const f = p.filters || {}
  const parts = [board?.wbName?.value, f.species ? (p.species?.[f.species] || f.species) : null,
    f.compare?.length === 2 ? `${t('wv.compare')}: ${f.compare[0]} и ${f.compare[1]}` : null].filter(Boolean)
  return parts.join(' · ')
}
async function snapshot() {
  const tb = tableOf(p.widget, data.value, (c) => p.species?.[c] || c)
  return { title: fullTitle.value, subtitle: subtitle.value || '', context: context(), columns: tb.columns,
    rows: tb.rows, sources: data.value?.sources || [], notes: [...(data.value?.explain?.now || []), ...(data.value?.notes || [])],
    filter_label: data.value?.filter_label || '',
    image: mode.value === 'chart' ? body.value?.image() || null : null }
}
async function exportAs(kind) {
  const snap = await snapshot()
  const name = (snap.title || 'widget').replace(/[^\p{L}\p{N}]+/gu, '_')
  try {
    if (kind === 'png') { const img = body.value?.image(); if (img) downloadDataUrl(img, name + '.png'); return }
    await downloadPost('dashboards', kind === 'xlsx' ? '/widgets/export.xlsx' : '/widgets/export.pdf', snap, `${name}.${kind}`)
  } catch (e) { ElMessage.error(e.message || String(e)) }
}
let unreg = null
onMounted(() => { if (board) unreg = board.register(p.widget.id, snapshot, () => !!data.value && !data.value.empty) })
onBeforeUnmount(() => unreg && unreg())
</script>
<style scoped>
.widget { min-width: 0; }
.wh { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 8px; gap: 8px; }
.wtt { min-width: 0; }
.wctl { display: flex; flex-wrap: wrap; gap: 8px; margin: -2px 0 10px; }
.wt { font-weight: 600; }
.spt { color: var(--fs-primary-2); }
.cmb { position: relative; }
.cmn { margin-left: 3px; font-size: 11.5px; font-weight: 600; color: var(--fs-primary); }
.ws { font-size: 12.5px; color: var(--fs-muted); line-height: 1.35; margin-top: 2px; }
.tools { display: flex; align-items: center; gap: 2px; flex: none; }
@media (max-width: 640px) { .wh { flex-wrap: wrap; } .wtt { flex: 1 1 100%; } .tools { flex-wrap: wrap; } }
.tools :deep(.el-radio-button__inner) { padding: 5px 8px; }
.foot { margin-top: 6px; font-size: 12px; color: var(--fs-muted); }
.note { margin-top: 2px; }
.src { margin-top: 3px; text-align: right; }
.formula { background: var(--fs-code); border-radius: 6px; padding: 8px 10px; margin-bottom: 10px; font-size: 13px; line-height: 1.5; }
.selbar { display: flex; align-items: center; gap: 8px; padding: 4px 8px; background: var(--fs-selected); border-radius: 6px; color: var(--fs-text); }
:deep(.on) { font-weight: 600; color: var(--fs-primary); }
.src .stale { color: var(--fs-warning); }
</style>
