<template>
  <div class="page cmp" data-test="compare-page">
    <header class="chead">
      <h1>{{ $t('cmp.title') }}</h1>
      <span class="muted small sub">{{ $t('cmp.subtitle') }}</span>
      <span class="grow" />
      <router-link :to="helpPath('compare')" class="small">{{ $t('cmp.help') }}</router-link>
      <el-button :disabled="!items.length" @click="copyLink" data-test="cmp-link"><el-icon><Link /></el-icon>{{ $t('cmp.copy_link') }}</el-button>
    </header>

    <StateBlock :loading="loading" :error="error">
      <!-- набор ряда: водоём → источник → расчёт → вид → k / орудие -->
      <section class="card builder" data-test="cmp-builder">
        <div class="brow">
          <el-radio-group v-model="b.source" size="small" class="srcsel">
            <el-radio-button v-for="s in SOURCES" :key="s" :value="s">{{ $t('cmp.src_' + s) }}</el-radio-button>
          </el-radio-group>
        </div>
        <div class="brow">
          <label class="fld"><span>{{ $t('cmp.wb') }}</span>
            <el-select v-model="b.wb" filterable class="w180" data-test="cmp-wb">
              <el-option v-for="w in wbsFor(b.source)" :key="w.code" :label="w.name" :value="w.code" />
            </el-select></label>
          <label class="fld"><span>{{ $t('cmp.calc') }}</span>
            <el-select v-model="b.calc" filterable class="w300" data-test="cmp-calc">
              <el-option v-for="c in calcsFor(b.source, b.wb)" :key="c.id" :label="calcLabel(c)" :value="c.id">
                <span>{{ c.is_main ? '★ ' : '' }}{{ c.title }}</span>
                <span class="muted small opt-r">{{ calcNote(c) }}</span>
              </el-option>
            </el-select></label>
          <label class="fld"><span>{{ $t('cmp.species') }}</span>
            <el-select v-model="b.species" multiple collapse-tags collapse-tags-tooltip filterable class="w220" data-test="cmp-species"
                       :loading="metaLoading" :placeholder="$t('cmp.species_ph')">
              <el-option v-for="s in bMeta?.species || []" :key="s.code" :label="s.name" :value="s.code" />
            </el-select></label>
          <label v-if="b.source === 'forecast'" class="fld"><span>k</span>
            <el-select v-model="b.ks" multiple collapse-tags collapse-tags-tooltip class="w180" data-test="cmp-k" :placeholder="$t('cmp.k_ph')">
              <el-option v-for="k in bMeta?.k || []" :key="k" :label="kLabel(k, bMeta)" :value="k" />
            </el-select></label>
          <label v-if="b.source === 'catch'" class="fld"><span>{{ $t('cmp.gear') }}</span>
            <el-select v-model="b.gear" class="w150">
              <el-option v-for="g in GEARS" :key="g" :label="g" :value="g" />
            </el-select></label>
          <el-button type="primary" :disabled="!canAdd" @click="addSeries" data-test="cmp-add"><el-icon><Plus /></el-icon>{{ $t('cmp.add') }}</el-button>
        </div>
        <div v-if="b.source === 'forecast' && bMeta && !bMeta.k_full" class="small warn-line">{{ $t('cmp.old_version') }}</div>
        <div class="presets">
          <span class="muted small">{{ $t('cmp.presets') }}</span>
          <el-tooltip v-for="p in presets" :key="p.key" :content="p.hint" placement="top" :show-after="300">
            <el-button size="small" :disabled="!p.ok" @click="p.run" :data-test="'cmp-preset-' + p.key">{{ p.title }}</el-button>
          </el-tooltip>
        </div>
      </section>

      <!-- ряды сравнения -->
      <section v-if="items.length" class="serbar">
        <div class="chips">
          <span v-for="(it, i) in items" :key="itemKey(it)" class="chip" :class="{ bad: rowsData[i]?.error }" :data-test="'cmp-chip-' + i">
            <span class="dot" :style="dotStyle(i)" />
            <el-tooltip v-if="rowsData[i]?.error" :content="rowsData[i].error" placement="top"><el-icon class="wicon"><WarningFilled /></el-icon></el-tooltip>
            <span class="clabel" :title="lab.full[i] || ''">{{ labels[i] || pending(it) }}</span>
            <button class="x" :title="$t('cmp.remove')" @click="removeAt(i)">×</button>
          </span>
          <el-button text size="small" @click="clearAll">{{ $t('cmp.clear') }}</el-button>
        </div>
        <div class="ctrls">
          <el-radio-group :model-value="state.measure" size="small" @change="(v) => setState({ measure: v })" data-test="cmp-measure">
            <el-radio-button value="total">{{ $t('cmp.m_total') }}</el-radio-button>
            <el-radio-button value="fishable">{{ $t('cmp.m_fishable') }}</el-radio-button>
          </el-radio-group>
          <el-checkbox :model-value="bandsOn" size="small" @change="(v) => setState({ bands: v })">{{ $t('cmp.bands') }}</el-checkbox>
          <el-checkbox :model-value="state.log" size="small" @change="(v) => setState({ log: v })">{{ $t('cmp.log') }}</el-checkbox>
        </div>
      </section>
      <div v-if="common" class="common small"><span class="muted">{{ $t('cmp.common') }}:</span> {{ common }}</div>

      <div v-if="!items.length" class="card state empty-cmp">
        <div>{{ $t('cmp.empty') }}</div>
        <div class="muted small">{{ $t('cmp.empty_hint') }}</div>
      </div>

      <template v-else>
        <div v-if="dataLoading && !rowsData.length" class="card state">{{ $t('common.loading') }}</div>
        <el-alert v-if="dataError" type="error" :closable="false" show-icon :title="String(dataError.message || dataError)" />
        <section class="card chart" v-if="stockOpt" data-test="cmp-stock">
          <div class="ctitle">{{ state.measure === 'fishable' ? $t('cmp.ch_fishable') : $t('cmp.ch_total') }}</div>
          <EChart :option="stockOpt" height="400px" />
          <div class="muted small note">{{ stockNote }}</div>
        </section>
        <div class="grid2">
          <section class="card chart" v-if="pduOpt" data-test="cmp-pdu">
            <div class="ctitle">{{ $t('cmp.ch_pdu') }}</div>
            <EChart :option="pduOpt" height="300px" />
            <div class="muted small note">{{ $t('cmp.pdu_note') }}</div>
          </section>
          <section class="card chart" v-if="riskOpt" data-test="cmp-risk">
            <div class="ctitle">{{ $t('cmp.ch_risk', { y: years.yE || '' }) }}</div>
            <EChart :option="riskOpt" height="300px" />
            <div class="muted small note">{{ $t('cmp.risk_note') }}</div>
          </section>
        </div>
        <section class="card" v-if="rows.length" data-test="cmp-table">
          <div class="ctitle">{{ $t('cmp.table') }}</div>
          <el-table :data="rows" size="small" border style="width:100%">
            <el-table-column :label="$t('cmp.col_series')" min-width="220">
              <template #default="{ row }"><span :title="lab.full[row.n] || ''"><span class="dot" :style="{ background: row.color }" /> {{ row.label }}</span>
                <div v-if="row.error" class="small err">{{ row.error }}</div></template>
            </el-table-column>
            <el-table-column :label="$t('cmp.col_last', { y: years.last || '' })" align="right" min-width="120">
              <template #default="{ row }">{{ num(row.last) }}</template>
            </el-table-column>
            <el-table-column label="F" align="right" width="80">
              <template #default="{ row }">{{ row.F != null ? fmt(row.F, 3) : '' }}</template>
            </el-table-column>
            <el-table-column :label="$t('cmp.col_pdu', { y: years.y1 || '' })" align="right" min-width="170">
              <template #default="{ row }"><template v-if="row.pdu != null"><b>{{ fmt(row.pdu, 'auto') }}</b>
                <span class="muted small"> ({{ fmt(row.pdu_lo, 'auto') }}–{{ fmt(row.pdu_hi, 'auto') }})</span></template></template>
            </el-table-column>
            <el-table-column :label="(state.measure === 'fishable' ? $t('cmp.col_end_f') : $t('cmp.col_end')) + ' ' + (years.yE || '')" align="right" min-width="170">
              <template #default="{ row }"><template v-if="row.end != null">{{ num(row.end) }}
                <span class="muted small"> ({{ num(row.end_lo) }}–{{ num(row.end_hi) }})</span></template></template>
            </el-table-column>
            <el-table-column :label="$t('cmp.col_risk')" align="right" width="130">
              <template #default="{ row }">{{ row.risk != null ? fmt(row.risk, 0) + ' %' : '' }}</template>
            </el-table-column>
          </el-table>
          <div class="muted small note">{{ $t('cmp.table_note') }}</div>
        </section>
      </template>
    </StateBlock>
  </div>
</template>
<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { api } from '../api'
import { helpPath } from '../cabinets'
import { compact, fmt } from '../components/charts'
import EChart from '../components/EChart.vue'
import StateBlock from '../components/StateBlock.vue'
import { GEARS, MAX_SERIES, SOURCES, fromQuery, itemKey, kf, pduChart, riskChart, seriesLabels, seriesStyle, stockChart,
  tableRows, tableYears, toQuery, uniqItems } from '../compare'

const route = useRoute()
const router = useRouter()
const { t, locale } = useI18n()

const loading = ref(true)
const error = ref(null)
const opts = ref({ water_bodies: [], calcs: { forecast: [], model: [], catch: [] } })

// ---------------------------------------------------------------- состояние — в ссылке
const state = computed(() => fromQuery(route.query))
const items = computed(() => state.value.items)
function setState(patch, push = false) {
  const q = toQuery({ ...state.value, ...patch })
  router[push ? 'push' : 'replace']({ query: q })
}
function setItems(list, push = false) {
  const all = uniqItems(list)
  if (list.filter(Boolean).length > MAX_SERIES) ElMessage.warning(t('cmp.too_many', { n: MAX_SERIES }))
  setState({ items: all }, push)
}
const removeAt = (i) => setItems(items.value.filter((_, j) => j !== i))
const clearAll = () => setItems([], true)

// ---------------------------------------------------------------- расчёты и их виды / k
const wbName = (c) => opts.value.water_bodies.find((w) => w.code === c)?.name || c
const wbsFor = (src) => opts.value.water_bodies.filter((w) => (opts.value.calcs[src] || []).some((c) => c.water_body === w.code))
const calcsFor = (src, wb) => (opts.value.calcs[src] || []).filter((c) => c.water_body === wb)
const mainOf = (src, wb) => calcsFor(src, wb).find((c) => c.is_main) || calcsFor(src, wb)[0] || null
const calcLabel = (c) => `${c.is_main ? '★ ' : ''}${c.title}`
const calcNote = (c) => [c.version ? 'v' + c.version : '', c.finished_at ? new Date(c.finished_at).toLocaleDateString('ru-RU') : ''].filter(Boolean).join(' · ')
const kLabel = (k, m) => (k === 0 ? t('cmp.k0') : `k = ${kf(k)}`) + (m && k === m.base_k ? ' · ' + t('cmp.k_calc') : '')

const meta = reactive({})
const metaLoading = ref(false)
async function loadMeta(src, ids) {
  const need = [...new Set(ids)].filter((id) => id && !meta[`${src}:${id}`])
  if (need.length) {
    const d = await api.get('dashboards', '/compare/meta', { ids: need.join(','), source: src, lang: locale.value })
    for (const [id, m] of Object.entries(d || {})) meta[`${src}:${id}`] = m
  }
  return ids.map((id) => meta[`${src}:${id}`]).filter(Boolean)
}

// ---------------------------------------------------------------- конструктор ряда
const b = reactive({ source: 'forecast', wb: null, calc: null, species: [], ks: [], gear: 'сеть+невод' })
const bMeta = computed(() => (b.calc ? meta[`${b.source}:${b.calc}`] : null))
let syncing = false
watch(() => b.source, (src) => {
  if (syncing) return
  if (!wbsFor(src).some((w) => w.code === b.wb)) b.wb = wbsFor(src)[0]?.code || null
  b.calc = mainOf(src, b.wb)?.id || null
})
watch(() => b.wb, (wb) => { if (!syncing && !calcsFor(b.source, wb).some((c) => c.id === b.calc)) b.calc = mainOf(b.source, wb)?.id || null })
watch(() => [b.source, b.calc], async ([src, id]) => {
  if (!id) return
  metaLoading.value = true
  try {
    const [m] = await loadMeta(src, [id])
    if (!m || b.calc !== id) return
    const codes = m.species.map((s) => s.code)
    const keep = b.species.filter((c) => codes.includes(c))
    b.species = keep.length ? keep : codes.slice(0, 1)
    if (src === 'forecast') {
      const ks = b.ks.filter((k) => m.k.includes(k))
      b.ks = ks.length ? ks : [m.base_k]
    }
  } catch (e) { ElMessage.error(e.message) } finally { metaLoading.value = false }
})
const canAdd = computed(() => b.calc && b.species.length && (b.source !== 'forecast' || b.ks.length))
const mk = (src, calc, species, k, gear) => ({ source: src, calc, species, ...(src === 'forecast' ? { k } : {}), ...(src === 'catch' ? { gear } : {}) })
function addSeries() {
  const add = []
  for (const sp of b.species) {
    for (const k of b.source === 'forecast' ? b.ks : [null]) add.push(mk(b.source, b.calc, sp, k, b.gear))
  }
  setItems([...items.value, ...add])
}

// быстрые наборы (заменяют текущие ряды)
const firstK = () => (b.ks.length ? b.ks[0] : bMeta.value?.base_k ?? 1)
const presets = computed(() => {
  const f = b.source === 'forecast'
  const sp = b.species[0]
  const spName = bMeta.value?.species.find((s) => s.code === sp)?.name || ''
  return [
    { key: 'all_k', title: t('cmp.p_all_k'), hint: t('cmp.p_all_k_h'), ok: f && !!b.calc && !!sp && !!bMeta.value,
      run: () => setItems(bMeta.value.k.map((k) => mk('forecast', b.calc, sp, k)), true) },
    { key: 'all_species', title: f ? t('cmp.p_all_sp_k', { k: kf(firstK()) }) : t('cmp.p_all_sp'), hint: t('cmp.p_all_sp_h'), ok: !!b.calc && !!bMeta.value,
      run: () => setItems(bMeta.value.species.map((s) => mk(b.source, b.calc, s.code, firstK(), b.gear)), true) },
    { key: 'all_wb', title: t('cmp.p_all_wb', { sp: spName }), hint: t('cmp.p_all_wb_h'), ok: !!sp,
      run: () => presetAllWb(sp) },
    { key: 'calcs', title: t('cmp.p_calcs'), hint: t('cmp.p_calcs_h'), ok: !!sp && calcsFor(b.source, b.wb).length > 1,
      run: () => presetCalcs(sp) },
  ]
})
async function presetAllWb(sp) {
  const mains = wbsFor(b.source).map((w) => mainOf(b.source, w.code)).filter(Boolean)
  try {
    const ms = await loadMeta(b.source, mains.map((c) => c.id))
    const list = ms.filter((m) => m.species.some((s) => s.code === sp)).map((m) => mk(b.source, m.id, sp, firstK(), b.gear))
    if (!list.length) return ElMessage.warning(t('cmp.no_matches'))
    setItems(list, true)
  } catch (e) { ElMessage.error(e.message) }
}
async function presetCalcs(sp) {
  const cs = calcsFor(b.source, b.wb)
  try {
    const ms = await loadMeta(b.source, cs.map((c) => c.id))
    // у каждого расчёта — его собственное k (альтернативный расчёт часто отличается именно k)
    const list = ms.filter((m) => m.species.some((s) => s.code === sp)).map((m) => mk(b.source, m.id, sp, m.base_k ?? firstK(), b.gear))
    if (!list.length) return ElMessage.warning(t('cmp.no_matches'))
    setItems(list, true)
  } catch (e) { ElMessage.error(e.message) }
}

// ---------------------------------------------------------------- данные рядов
// данные кешируются по ряду, показателю и языку: убрать ряд — без запроса, добавить — запрашивается только новый
const cache = reactive(new Map())
const ck = (it) => `${state.value.measure}|${locale.value}|${itemKey(it)}`
const dataLoading = ref(false)
const dataError = ref(null)
let reqN = 0
async function loadSeries() {
  const n = ++reqN
  dataError.value = null
  const need = items.value.filter((it) => !cache.has(ck(it)))
  if (!need.length) return
  const keys = need.map(ck)
  dataLoading.value = true
  try {
    const d = await api.post('dashboards', '/compare/series', { series: need, measure: state.value.measure, lang: locale.value })
    ;(d.series || []).forEach((x, j) => cache.set(keys[j], x))
  } catch (e) { if (n === reqN) dataError.value = e } finally { if (n === reqN) dataLoading.value = false }
}
watch(() => [JSON.stringify(items.value), state.value.measure, locale.value], loadSeries)

// данные — в порядке рядов ссылки (пока не пришли все — пусто)
const rowsData = computed(() => {
  const a = items.value.map((it) => cache.get(ck(it)))
  return a.every(Boolean) ? a : []
})
const lab = computed(() => seriesLabels(rowsData.value, t))
const labels = computed(() => lab.value.labels)
const common = computed(() => lab.value.common)
const pending = (it) => [wbName(opts.value.calcs[it.source]?.find((c) => c.id === it.calc)?.water_body), it.species,
  it.source === 'forecast' ? `k = ${kf(it.k)}` : ''].filter(Boolean).join(' · ')
const dotStyle = (i) => {
  const st = seriesStyle(i, items.value[i])
  return { background: st.color, ...(st.dash ? { outline: `1px dashed ${st.color}`, outlineOffset: '2px' } : {}) }
}
const okN = computed(() => rowsData.value.filter((s) => !s.error).length)
const bandsOn = computed(() => (state.value.bands === null ? okN.value <= 3 : state.value.bands))
const stockOpt = computed(() => stockChart(rowsData.value, { labels: labels.value, bands: bandsOn.value, log: state.value.log, t, measure: state.value.measure }))
const pduOpt = computed(() => pduChart(rowsData.value, { labels: labels.value, log: state.value.log, t }))
const riskOpt = computed(() => riskChart(rowsData.value, { labels: labels.value, t }))
const rows = computed(() => tableRows(rowsData.value, labels.value))
const years = computed(() => tableYears(rows.value))
// численность — в тыс./млн, тонны — целиком
const num = (v) => (v == null ? '' : state.value.measure === 'total' && Math.abs(v) >= 1e5 ? compact(v) : fmt(v, 'auto'))
const stockNote = computed(() => {
  const srcs = new Set(rowsData.value.filter((s) => !s.error).map((s) => s.source))
  return [srcs.has('forecast') ? t('cmp.note_forecast') : '', srcs.has('model') ? t('cmp.note_model') : '', srcs.has('catch') ? t('cmp.note_catch') : '',
    bandsOn.value ? t('cmp.note_bands') : ''].filter(Boolean).join(' ')
})

async function copyLink() {
  try { await navigator.clipboard.writeText(window.location.href); ElMessage.success(t('cmp.link_copied')) } catch (e) { ElMessage.info(window.location.href) }
}

async function loadOptions() {
  opts.value = await api.get('dashboards', '/compare/options', { lang: locale.value })
}
onMounted(async () => {
  try {
    await loadOptions()
    // конструктор — по первому ряду ссылки, иначе основной прогноз первого водоёма
    const first = items.value[0]
    const c = first && opts.value.calcs[first.source]?.find((x) => x.id === first.calc)
    syncing = true
    if (c) {
      Object.assign(b, { source: first.source, wb: c.water_body, calc: c.id, species: [first.species],
        ks: first.source === 'forecast' ? [first.k] : [], gear: first.gear || 'сеть+невод' })
    } else {
      const src = SOURCES.find((s) => wbsFor(s).length) || 'forecast'
      b.source = src
      b.wb = wbsFor(src)[0]?.code || null
      b.calc = mainOf(src, b.wb)?.id || null
    }
    setTimeout(() => { syncing = false }, 0)
    loadSeries()
  } catch (e) { error.value = e } finally { loading.value = false }
})
watch(locale, async () => {
  try {
    for (const k of Object.keys(meta)) delete meta[k]
    await loadOptions()
    if (b.calc) await loadMeta(b.source, [b.calc])
  } catch (e) { /* остаётся прежний язык подписей */ }
})
</script>
<style scoped>
.cmp { padding-bottom: 16px; }
.chead { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin: 4px 0 10px; }
.chead h1 { margin: 0; font-size: 20px; }
.grow { flex: 1; }
.builder { padding: 12px 14px; margin-bottom: 10px; }
.brow { display: flex; gap: 10px; align-items: flex-end; flex-wrap: wrap; margin-bottom: 8px; }
.fld { display: flex; flex-direction: column; gap: 3px; font-size: 12px; color: var(--fs-muted); }
.w150 { width: 150px; } .w180 { width: 180px; } .w220 { width: 220px; } .w300 { width: 300px; }
.opt-r { float: right; margin-left: 12px; }
.presets { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; border-top: 1px dashed var(--fs-line); padding-top: 8px; }
.presets .el-button + .el-button { margin-left: 0; }
.warn-line { color: var(--fs-warning); margin: -2px 0 6px; }
.serbar { display: flex; gap: 10px; align-items: flex-start; justify-content: space-between; flex-wrap: wrap; margin-bottom: 6px; }
.chips { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; flex: 1; min-width: 0; }
.chip { display: inline-flex; align-items: center; gap: 6px; border: 1px solid var(--fs-line); background: var(--fs-card); border-radius: 16px;
  padding: 2px 4px 2px 10px; font-size: 13px; max-width: 100%; }
.chip.bad { border-color: var(--fs-warning); }
.clabel { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 360px; }
.dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; flex: none; vertical-align: middle; }
.wicon { color: var(--fs-warning); }
.x { border: none; background: none; color: var(--fs-muted); cursor: pointer; font-size: 16px; line-height: 1; padding: 0 6px; font-family: inherit; }
.x:hover { color: var(--fs-danger); }
.ctrls { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.common { margin: 0 0 8px; }
.chart { padding: 10px 12px; margin-bottom: 10px; }
.ctitle { font-weight: 600; margin-bottom: 4px; }
.note { margin-top: 4px; }
.grid2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(380px, 1fr)); gap: 10px; }
.card.state { padding: 24px; text-align: center; }
.empty-cmp div + div { margin-top: 6px; }
.err { color: var(--fs-warning); }
@media (max-width: 700px) { .w300, .w220, .w180 { width: 100%; } .fld { width: 100%; } .grid2 { grid-template-columns: 1fr; } }
</style>
