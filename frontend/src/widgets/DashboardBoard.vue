<template>
  <div>
    <el-tabs v-if="tabs.length > 1 || editing" v-model="tab" class="dtabs">
      <el-tab-pane v-for="t in tabs" :key="t.code" :name="t.code" :label="tr(t, 'title')" />
    </el-tabs>
    <!-- строка раздела: разделы · вид отображения · ещё -->
    <div class="secline">
      <el-radio-group v-if="sections.length" v-model="section" size="small" class="secs">
        <el-radio-button v-for="s in sections" :key="s.code" :value="s.code">{{ tr(s, 'title') }}</el-radio-button>
      </el-radio-group>
      <!-- год результатов расчёта: стрелками, как в прежнем приложении; общий для всех слайдов раздела -->
      <div v-if="curTab?.year_picker && calcYears.length && showYear" class="ystep" :aria-label="$t('mon.year')">
        <span class="muted small">{{ $t('mon.year') }}</span>
        <el-button size="small" :disabled="yIdx <= 0" :title="$t('mon.prev_year')" @click="stepYear(-1)"><el-icon><ArrowLeft /></el-icon></el-button>
        <el-select :model-value="shownYear" size="small" style="width:88px" @update:model-value="setYear">
          <el-option v-for="y in [...calcYears].reverse()" :key="y" :label="y" :value="y" />
        </el-select>
        <el-button size="small" :disabled="yIdx >= calcYears.length - 1" :title="$t('mon.next_year')" @click="stepYear(1)"><el-icon><ArrowRight /></el-icon></el-button>
      </div>
      <span class="grow" />
      <el-tag v-if="compare" size="small" closable type="warning" @close="cmpA = cmpB = null">{{ $t('mon.compare_on') }}: {{ compare[0] }} · {{ compare[1] }}</el-tag>
      <el-tag v-if="highlight != null" size="small" closable type="warning" @close="highlight = null">{{ $t('wv.highlighted') }}: {{ highlight }}</el-tag>
      <el-radio-group v-if="slidesAllowed" v-model="viewMode" size="small">
        <el-radio-button value="slides" :title="$t('mon.slides')"><el-icon><Postcard /></el-icon>&nbsp;{{ $t('mon.slides') }}</el-radio-button>
        <el-radio-button value="feed" :title="$t('mon.feed')"><el-icon><Grid /></el-icon>&nbsp;{{ $t('mon.feed') }}</el-radio-button>
      </el-radio-group>
      <el-dropdown trigger="click" @command="onMore">
        <el-button size="small" :loading="reporting"><el-icon><MoreFilled /></el-icon></el-button>
        <template #dropdown><el-dropdown-menu>
          <el-dropdown-item command="compare"><el-icon><Switch /></el-icon>{{ $t('mon.compare') }}</el-dropdown-item>
          <el-dropdown-item command="report"><el-icon><Document /></el-icon>{{ $t('wv.report') }}</el-dropdown-item>
          <slot name="more-items" />
        </el-dropdown-menu></template>
      </el-dropdown>
    </div>

    <!-- слайды: один виджет крупно + пояснение и комментарии справа -->
    <template v-if="slidesOn && visible.length">
      <div class="slide">
        <button class="nav prev" :disabled="idx === 0" :title="$t('mon.prev')" @click="go(-1)"><el-icon><ArrowLeft /></el-icon></button>
        <div class="slide-main">
          <Widget :key="cur.id + JSON.stringify(cur.source) + JSON.stringify(cur.options) + (filters?.species || '')" :widget="cur"
                  :filters="wfilters" :species="species" big />
        </div>
        <aside class="slide-side card">
          <ExplainPanel :explain="dataById[cur.id]?.explain" @go="goWidget" />
          <CommentsPanel :board-id="board?.id" :widget-id="cur.id" :water-body="filters?.water_body"
                         :species="['species', 'both'].includes(cur.scope || '') ? filters?.species || null : null"
                         :years="yearList" @changed="reloadCounts" />
        </aside>
        <button class="nav next" :disabled="idx >= visible.length - 1" :title="$t('mon.next')" @click="go(1)"><el-icon><ArrowRight /></el-icon></button>
      </div>
      <div class="dots">
        <button v-for="(w, i) in visible" :key="w.id" class="dot" :class="{ on: i === idx }" @click="idx = i">
          <span class="dn">{{ i + 1 }}</span>{{ tr(w, 'title') }}<span v-if="counts[w.id]" class="dc">💬 {{ counts[w.id] }}</span>
        </button>
        <span class="muted small counter">{{ idx + 1 }} {{ $t('mon.of') }} {{ visible.length }} · {{ $t('mon.keys_hint') }}</span>
      </div>
    </template>

    <!-- лента -->
    <div v-else class="grid12">
      <Widget v-for="w in visible" :id="'w-' + w.id" :key="w.id + JSON.stringify(w.source) + JSON.stringify(w.options) + (filters?.species || '')"
              :widget="w" :filters="wfilters" :species="species">
        <template v-if="editing" #tools>
          <span>
            <el-button size="small" text @click="$emit('edit-widget', w)"><el-icon><Edit /></el-icon></el-button>
            <el-button size="small" text @click="$emit('move', w, -1)"><el-icon><Top /></el-icon></el-button>
            <el-button size="small" text @click="$emit('move', w, 1)"><el-icon><Bottom /></el-icon></el-button>
            <el-button size="small" text type="danger" @click="$emit('remove', w)"><el-icon><Delete /></el-icon></el-button>
          </span>
        </template>
      </Widget>
      <div v-if="!visible.length" class="card state" style="grid-column: span 12">{{ $t('common.empty') }}</div>
    </div>

    <el-dialog v-model="cmpOpen" :title="$t('mon.compare_title')" width="380px" append-to-body>
      <div class="row" style="gap:8px; align-items:center">
        <el-select v-model="cmpA" clearable :placeholder="$t('common.year')" style="width:120px">
          <el-option v-for="y in yearList" :key="y" :label="y" :value="y" />
        </el-select>
        <span class="muted">{{ $t('wv.and') }}</span>
        <el-select v-model="cmpB" clearable :placeholder="$t('common.year')" style="width:120px">
          <el-option v-for="y in yearList" :key="y" :label="y" :value="y" />
        </el-select>
      </div>
      <template #footer>
        <el-button @click="cmpA = cmpB = null; cmpOpen = false">{{ $t('mon.reset') }}</el-button>
        <el-button type="primary" @click="cmpOpen = false">{{ $t('mon.apply') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>
<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, provide, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { api, downloadPost } from '../api'
import { tr } from '../i18n'
import Widget from './Widget.vue'
import ExplainPanel from './ExplainPanel.vue'
import CommentsPanel from './CommentsPanel.vue'
const p = defineProps({ board: Object, filters: Object, species: Object, editing: Boolean, modelValue: String, wbName: String,
  slides: Boolean })
const emit = defineEmits(['edit-widget', 'move', 'remove', 'update:modelValue', 'species', 'state'])
const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const tabs = computed(() => (p.board?.tabs?.length ? p.board.tabs : [{ code: 'main', title_ru: 'Главная' }]))
const tab = ref(p.modelValue || route.query.tab || tabs.value[0]?.code)
watch(tab, (v) => emit('update:modelValue', v))
watch(tabs, (tt) => { if (!tt.find((x) => x.code === tab.value)) tab.value = tt[0]?.code })
const curTab = computed(() => tabs.value.find((x) => x.code === tab.value) || tabs.value[0])
// год результатов расчёта (вкладки с year_picker): выбранный пользователем, иначе последний (решает сервер)
const calcYear = ref(route.query.y ? Number(route.query.y) : null)
const calcYears = ref([])
const reportedYear = ref(null)
const shownYear = computed(() => calcYear.value ?? reportedYear.value)
const yIdx = computed(() => calcYears.value.indexOf(shownYear.value))
// стрелки года — только если слайд (или лента раздела) зависит от года; у прогноза года свои
const showYear = computed(() => (slidesOn.value ? !!dataById[cur.value?.id]?.calc_year : visible.value.some((w) => dataById[w.id]?.calc_year)))
function setYear(y) { calcYear.value = y ? Number(y) : null }
function stepYear(d) { const i = yIdx.value + d; if (i >= 0 && i < calcYears.value.length) setYear(calcYears.value[i]) }

// режим: «Все виды» — водоём целиком; выбран вид — «Все данные по виду» (у виджета scope: wb | species | both)
const spMode = computed(() => !!p.filters?.species)
const inMode = (w) => { const s = w.scope || 'both'; return s === 'both' || (spMode.value ? s === 'species' : s === 'wb') }
const tabWidgets = computed(() => (p.board?.widgets || []).filter((w) => (w.tab || tabs.value[0].code) === tab.value && (p.editing || inMode(w))))
const sections = computed(() => (curTab.value?.sections || []).filter((s) => tabWidgets.value.some((w) => (w.section || curTab.value.sections[0].code) === s.code)))
const section = ref(route.query.s || null)
watch(sections, (s) => { if (s.length && !s.find((x) => x.code === section.value)) section.value = s[0].code }, { immediate: true })
const visible = computed(() => tabWidgets.value.filter((w) => !sections.value.length || (w.section || sections.value[0].code) === section.value))

// слайды / лента (выбор запоминается в браузере)
const VIEW_KEY = 'fishstock.monitoring.view'
function savedView() { try { return localStorage.getItem(VIEW_KEY) || 'slides' } catch (e) { return 'slides' } }
const slidesAllowed = computed(() => p.slides && !p.editing)
const viewMode = ref(savedView())
watch(viewMode, (v) => { try { localStorage.setItem(VIEW_KEY, v) } catch (e) { /* приватный режим */ } })
const slidesOn = computed(() => slidesAllowed.value && viewMode.value === 'slides')
const idx = ref(0)
const cur = computed(() => visible.value[Math.min(idx.value, visible.value.length - 1)] || visible.value[0])
// при смене вида остаёмся на том же виджете (удобно сравнивать виды), при смене раздела — первый слайд
watch(visible, (v, old) => {
  const prevId = old ? old[idx.value]?.id : route.query.w
  const i = prevId ? v.findIndex((w) => w.id === prevId) : -1
  idx.value = i > -1 ? i : 0
}, { immediate: true })
function go(d) { idx.value = Math.max(0, Math.min(visible.value.length - 1, idx.value + d)) }
function onKey(e) {
  if (!slidesOn.value || e.target.closest('input, textarea, .el-select')) return
  if (e.key === 'ArrowRight') go(1)
  if (e.key === 'ArrowLeft') go(-1)
}
onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
// адрес помнит вкладку, раздел и слайд — ссылкой можно поделиться
watch([tab, section, cur, slidesOn, () => p.filters?.species, calcYear], () => {
  if (!p.slides) return
  const q = { ...route.query, tab: tab.value, sp: p.filters?.species || undefined, s: section.value || undefined, w: slidesOn.value ? cur.value?.id : undefined,
    y: curTab.value?.year_picker && calcYear.value ? calcYear.value : undefined }
  router.replace({ query: q })
  emit('state', { section: tr(sections.value.find((s) => s.code === section.value) || {}, 'title'), index: idx.value + 1,
    count: visible.value.length, slides: slidesOn.value })
}, { immediate: true })
const slideHeight = computed(() => Math.max(360, window.innerHeight - 380) + 'px')

// ---- связь виджетов: подсветка года, сравнение двух лет, данные виджетов, комментарии
const highlight = ref(null)
const years = ref(new Set())
const yearList = computed(() => [...years.value].sort((a, b) => b - a))
const cmpA = ref(null)
const cmpB = ref(null)
const cmpOpen = ref(false)
const compare = computed(() => (cmpA.value && cmpB.value && cmpA.value !== cmpB.value
  ? [Math.min(cmpA.value, cmpB.value), Math.max(cmpA.value, cmpB.value)] : null))
// варианты расчёта (уловистость по возрастам / средняя по виду, годовой запас по запасам / по улову) — общие для слайдов вкладки
const calcOpts = reactive({})
const wfilters = computed(() => ({ ...p.filters, ...(compare.value ? { compare: compare.value } : {}),
  ...(curTab.value?.year_picker && calcYear.value ? { year: calcYear.value } : {}),
  ...(curTab.value?.year_picker ? { ...calcOpts } : {}) }))
watch(() => p.filters?.water_body, () => { years.value = new Set(); highlight.value = null; cmpA.value = null; cmpB.value = null; calcYear.value = null; calcYears.value = [] })
const dataById = reactive({})
const counts = ref({})
async function reloadCounts() {
  if (!p.board?.id || !p.filters?.water_body) return
  try {
    const all = await api.get('dashboards', '/comments/counts', { board: p.board.id, water_body: p.filters.water_body })
    const sp = p.filters.species ? await api.get('dashboards', '/comments/counts',
      { board: p.board.id, water_body: p.filters.water_body, species: p.filters.species }) : {}
    // у видовых виджетов — комментарии этого вида, у общих — водоёма
    const out = {}
    for (const w of p.board.widgets || []) {
      const s = w.scope || 'both'
      out[w.id] = (p.filters.species && s !== 'wb' ? sp[w.id] : all[w.id]) || 0
    }
    counts.value = out
  } catch (e) { counts.value = {} }
}
watch(() => [p.board?.id, p.filters?.water_body, p.filters?.species], reloadCounts, { immediate: true })
const journalPreset = ref(null)
const reg = new Map()
function goWidget(id) {
  const w = (p.board?.widgets || []).find((x) => x.id === id && inMode(x))
  if (!w) return
  if (w.section) section.value = w.section
  nextTick(() => {
    const i = visible.value.findIndex((x) => x.id === id)
    if (i > -1) idx.value = i
    if (!slidesOn.value) nextTick(() => document.getElementById('w-' + id)?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
  })
}
function openSpeciesAll(c) {
  if (!c) return
  emit('species', c)
  // «Все данные по виду» открываются на первом разделе вкладки (Обзор), первым слайдом
  const go = () => {
    const first = sections.value[0]
    if (first) section.value = first.code
    nextTick(() => { idx.value = 0; if (!slidesOn.value) document.querySelector('.main')?.scrollTo({ top: 0, behavior: 'smooth' }) })
  }
  if (p.filters?.species === c) { go(); return }
  const stop = watch(() => p.filters?.species, (v) => { if (v === c) { stop(); nextTick(go) } })
}
provide('board', {
  highlight,
  boardId: p.board?.id,
  counts,
  yearList,
  slideHeight,
  journalPreset,
  wbName: computed(() => p.wbName || ''),
  setHighlight: (y) => { highlight.value = y == null || highlight.value === y ? null : y },
  setSection: (s) => { const tb = tabs.value.find((x) => (x.sections || []).some((q) => q.code === s)); if (tb) { tab.value = tb.code; section.value = s } },
  setSpecies: openSpeciesAll,
  setData: (id, d) => {
    dataById[id] = d
    if (d?.calc_year && d.year_choices?.length) {
      if (calcYears.value.join() !== d.year_choices.join()) calcYears.value = [...d.year_choices]
      reportedYear.value = d.year
    }
  },
  setYear,
  setCalcOpt: (k, v) => { calcOpts[k] = v },
  reloadCounts,
  goWidget,
  openJournal: (where) => { journalPreset.value = { ...where }; goWidget('d_journal') },
  addYears: (ys) => { const n = new Set(years.value); for (const y of ys || []) if (Number.isInteger(+y) && +y > 1900) n.add(+y); if (n.size !== years.value.size) years.value = n },
  register: (id, fn, ready) => { reg.set(id, { fn, ready }); return () => reg.delete(id) },
})
const reporting = ref(false)
function onMore(c) {
  if (c === 'compare') cmpOpen.value = true
  if (c === 'report') report()
}
let wasView = null
async function report() {
  reporting.value = true
  try {
    // отчёт строится по ленте: в режиме слайдов виджеты раздела загружаются по одному — переключаемся на время отчёта
    const was = viewMode.value
    wasView = was
    if (slidesOn.value) {
      viewMode.value = 'feed'
      // ждём, пока все виджеты раздела загрузятся (не дольше 30 с), и даём графикам дорисоваться
      const need = visible.value.filter((w) => w.type !== 'text').map((w) => w.id)
      const t0 = Date.now()
      while (Date.now() - t0 < 30000 && !need.every((id) => reg.has(id) && reg.get(id).ready())) await new Promise((r) => setTimeout(r, 250))
      await new Promise((r) => setTimeout(r, 1200))
    }
    const ids = visible.value.map((w) => w.id).filter((id) => reg.has(id) && reg.get(id).ready())
    const widgets = await Promise.all(ids.map((id) => reg.get(id).fn()))
    viewMode.value = was
    const sec = sections.value.find((s) => s.code === section.value)
    const title = [tr(curTab.value, 'title'), sec ? tr(sec, 'title') : null].filter(Boolean).join(' — ')
    const ctx = [p.wbName, p.filters?.species ? p.species?.[p.filters.species] : t('mon.all_species'),
      compare.value ? `${t('wv.compare')}: ${compare.value[0]} ${t('wv.and')} ${compare.value[1]}` : null].filter(Boolean).join(' · ')
    await downloadPost('dashboards', '/reports/section.pdf', { title, context: ctx, widgets },
      `${(p.wbName || 'FishStock').replace(/[^\p{L}\p{N}]+/gu, '_')}_${(sec?.code || tab.value)}.pdf`)
  } catch (e) { ElMessage.error(e.message || String(e)) } finally { reporting.value = false; if (wasView) viewMode.value = wasView }
}
</script>
<style scoped>
.dtabs { margin-bottom: 4px; }
.secline { display: flex; align-items: center; gap: 8px; margin: 0 0 12px; flex-wrap: wrap; }
.secs { flex-wrap: nowrap; overflow-x: auto; max-width: 100%; }
.grow { flex: 1; }
.ystep { display: inline-flex; align-items: center; gap: 4px; }
.ystep .el-button + .el-select, .ystep .el-select + .el-button { margin-left: 0; }
.slide { display: grid; grid-template-columns: 36px minmax(0, 1fr) 380px 36px; gap: 10px; align-items: start; }
.slide-main :deep(.widget) { margin: 0; }
.slide-side { max-height: calc(100vh - 230px); overflow-y: auto; padding: 14px 16px; position: sticky; top: 140px; }
.nav { align-self: center; height: 64px; border: 1px solid var(--fs-line); border-radius: 8px; background: var(--fs-card); color: var(--fs-text);
  cursor: pointer; display: flex; align-items: center; justify-content: center; }
.nav:hover:not(:disabled) { background: var(--fs-hover); border-color: var(--fs-primary-2); }
.nav:disabled { opacity: .35; cursor: default; }
.dots { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin: 12px 46px 0; }
.dot { border: 1px solid var(--fs-line); background: var(--fs-card); color: var(--fs-text); border-radius: 16px; padding: 3px 10px;
  font-size: 12.5px; cursor: pointer; display: inline-flex; gap: 6px; align-items: center; font-family: inherit; }
.dot:hover { border-color: var(--fs-primary-2); }
.dot.on { background: var(--fs-primary); color: var(--fs-on-primary); border-color: var(--fs-primary); }
.dn { font-weight: 600; opacity: .7; }
.dc { font-size: 11px; }
.counter { margin-left: auto; }
@media (max-width: 1200px) {
  .slide { grid-template-columns: 30px minmax(0, 1fr) 30px; }
  .slide-side { grid-column: 2; grid-row: 2; position: static; max-height: none; }
}
</style>
