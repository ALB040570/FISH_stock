<template>
  <div class="map-page">
    <div class="panel">
      <div class="ph">
        <h1>{{ $t('map.title') }}</h1>
        <el-input v-model="q" :placeholder="$t('common.search')" clearable prefix-icon="Search" />
        <div class="row" style="margin-top:8px">
          <el-select v-model="fRegion" clearable :placeholder="$t('map.filter_region')" style="flex:1">
            <el-option v-for="r in regions" :key="r" :label="regionName(r)" :value="r" />
          </el-select>
          <el-select v-model="fState" clearable :placeholder="$t('map.filter_state')" style="flex:1">
            <el-option v-for="s in STATES" :key="s" :label="$t('map.' + s)" :value="s">
              <span class="tag-dot" :style="{ background: COLORS[s] }" />{{ $t('map.' + s) }}
            </el-option>
          </el-select>
        </div>
        <div class="row" style="margin-top:8px">
          <el-select v-model="fType" clearable :placeholder="$t('map.filter_type')" style="flex:1">
            <el-option v-for="o in dictOptions('water_body_types')" :key="o.code" :label="o.label" :value="o.code" />
          </el-select>
          <el-select v-model="fStatus" clearable :placeholder="$t('map.filter_status')" style="flex:1">
            <el-option v-for="o in dictOptions('water_body_statuses')" :key="o.code" :label="o.label" :value="o.code" />
          </el-select>
        </div>
        <div class="row" style="margin-top:8px">
          <el-select v-model="fOrigin" clearable :placeholder="$t('map.filter_origin')" style="flex:1">
            <el-option v-for="o in dictOptions('water_body_origins')" :key="o.code" :label="o.label" :value="o.code" />
          </el-select>
          <el-select v-model="fSpecies" clearable :placeholder="$t('map.filter_species')" style="flex:1">
            <el-option v-for="s in species" :key="s.code" :label="tr(s, 'name')" :value="s.code" />
          </el-select>
        </div>
      </div>
      <StateBlock :loading="loading" :error="error" :retry="load">
        <div class="list">
          <div v-for="w in filtered" :key="w.id" class="item" :class="{ sel: sel && sel.id === w.id }" @click="select(w, true)">
            <span class="tag-dot" :style="{ background: COLORS[w.state] }" />
            <div class="grow">
              <div class="nm">{{ tr(w, 'name') }}</div>
              <div class="muted small">{{ regionNames(w.regions) || '—' }}<template v-if="w.years.length"> · {{ w.years[0] }}–{{ w.years[w.years.length - 1] }}</template></div>
            </div>
          </div>
          <div v-if="!filtered.length" class="state">{{ $t('map.none_found') }}</div>
        </div>
      </StateBlock>
    </div>
    <div class="mapbox">
      <div ref="mapEl" class="map" />
      <div class="legend card">
        <div class="small muted" style="margin-bottom:4px">{{ $t('map.legend') }}</div>
        <div v-for="s in STATES" :key="s" class="small"><span class="tag-dot" :style="{ background: COLORS[s] }" />{{ $t('map.' + s) }}</div>
        <div class="small muted" style="margin:8px 0 4px">{{ $t('map.basemap') }}</div>
        <el-radio-group v-model="basemap" size="small" @change="applyBasemap">
          <el-radio-button value="osm">{{ $t('map.basemap_osm') }}</el-radio-button>
          <el-radio-button value="none">{{ $t('map.basemap_none') }}</el-radio-button>
        </el-radio-group>
      </div>
      <transition name="slide">
        <div v-if="sel" class="info card">
          <div class="row" style="justify-content:space-between; align-items:flex-start">
            <div>
              <h2 style="margin:0">{{ tr(sel, 'name') }}</h2>
              <div class="muted small">{{ typeTitle(sel.type) }} · {{ regionNames(sel.regions) || '—' }}</div>
              <div v-if="sel.status || sel.origin" class="muted small">{{ [dictName('water_body_statuses', sel.status), dictName('water_body_origins', sel.origin)].filter(Boolean).join(' · ') }}</div>
              <div v-if="sel.fishery_kinds?.length" class="muted small">{{ dictNames('fishery_kinds', sel.fishery_kinds) }}</div>
            </div>
            <el-button text @click="sel = null"><el-icon><Close /></el-icon></el-button>
          </div>
          <div class="kpis" style="margin-top:10px">
            <div class="kpi"><div class="v">{{ sel.years.length ? sel.years[0] + '–' + sel.years[sel.years.length - 1] : '—' }}</div><div class="l">{{ $t('map.years') }}</div></div>
            <div class="kpi"><div class="v">{{ sel.ndatasets }}</div><div class="l">{{ $t('map.datasets') }}</div></div>
          </div>
          <div v-if="sel.speciesList.length" class="small" style="margin-top:8px"><span class="muted">{{ $t('map.species_in_data') }}:</span> {{ sel.speciesList.join(', ') }}</div>
          <div v-if="sel.run" class="small" style="margin-top:8px">
            <span class="muted">{{ sel.run.main_run ? $t('map.main_run') : $t('map.last_run') }}:</span>
            {{ (sel.run.main_run || sel.run.last_done || sel.run.last_run || {}).calculation_title }}
            <span class="muted"> · {{ shortDate((sel.run.main_run || sel.run.last_done || sel.run.last_run || {}).finished_at) }}</span>
          </div>
          <div v-if="sel.pdu?.rows?.length" style="margin-top:8px">
            <div class="small muted">{{ $t('map.pdu') }}, т ({{ sel.pdu.rows[0].year }})</div>
            <el-table :data="sel.pdu.rows" size="small" max-height="190">
              <el-table-column prop="species" :label="$t('common.species')" />
              <el-table-column :label="$t('map.pdu')" align="right"><template #default="{ row }">{{ fmt(row.pdu_t, 1) }}</template></el-table-column>
            </el-table>
          </div>
          <div class="row" style="margin-top:12px">
            <el-button type="primary" @click="$router.push('/monitoring/waterbody/' + sel.code)"><el-icon><DataLine /></el-icon>&nbsp;{{ $t('map.monitoring') }}</el-button>
            <el-button @click="$router.push({ path: '/input/datasets', query: { wb: sel.code } })">{{ $t('map.data') }}</el-button>
            <el-button v-if="auth.can('run.execute')" @click="$router.push({ path: '/calc/calculations', query: { wb: sel.code } })">{{ $t('map.start_calc') }}</el-button>
          </div>
        </div>
      </transition>
    </div>
  </div>
</template>
<script setup>
import { loadRegions, regionName, regionNames } from '../regions'
import { dictName, dictNames, dictOptions, loadDict } from '../dicts'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import L from 'leaflet'
import { useI18n } from 'vue-i18n'
import { api } from '../api'
import { tr } from '../i18n'
import { useAuth } from '../store/auth'
import { fmt } from '../components/charts'
import { MAP, MAP_STATE, themeMode } from '../theme'
import StateBlock from '../components/StateBlock.vue'

const auth = useAuth()
const STATES = ['no_data', 'has_data', 'has_run', 'stale']
const COLORS = MAP_STATE
const { t } = useI18n()
const typeTitle = (x) => dictName('water_body_types', x) || '—'
const mapEl = ref(null)
const loading = ref(true)
const error = ref(null)
const wbs = ref([])
const species = ref([])
const q = ref('')
const fRegion = ref('')
const fState = ref('')
const fSpecies = ref('')
const fType = ref('')
const fStatus = ref('')
const fOrigin = ref('')
const sel = ref(null)
let map = null
let layer = null
// Подложка: «карта» — OpenStreetMap только внутри Казахстана (снаружи — маска цветом фона);
// «без подложки» — силуэт страны, работает без интернета. Выбор запоминается в браузере.
const BASEMAP_KEY = 'fishstock.basemap'
function savedBasemap() { try { return localStorage.getItem(BASEMAP_KEY) || 'osm' } catch (e) { return 'osm' } }
const basemap = ref(savedBasemap())
let tiles = null
let land = null
let maskLayer = null
let borderLayer = null
function applyBasemap() {
  try { localStorage.setItem(BASEMAP_KEY, basemap.value) } catch (e) { /* приватный режим */ }
  if (!map) return
  if (basemap.value === 'osm') { land && land.remove(); tiles.addTo(map) } else { tiles.remove(); land && land.addTo(map) }
}
// маска: прямоугольник «весь мир» с вырезанными контурами Казахстана
function maskLatLngs(geo) {
  const holes = []
  const add = (g) => {
    if (g.type === 'Polygon') holes.push(g.coordinates[0].map(([x, y]) => [y, x]))
    else if (g.type === 'MultiPolygon') g.coordinates.forEach((p) => holes.push(p[0].map(([x, y]) => [y, x])))
  }
  for (const f of geo.features || [geo]) add(f.geometry || f)
  return [[[-89, -179], [-89, 179], [89, 179], [89, -179]], ...holes]
}
const layers = {}

const regions = computed(() => [...new Set(wbs.value.flatMap((w) => w.regions || []))].sort((a, b) => regionName(a).localeCompare(regionName(b))))
const filtered = computed(() => wbs.value.filter((w) =>
  (!q.value || (w.name_ru + ' ' + (w.name_kk || '')).toLowerCase().includes(q.value.toLowerCase())) &&
  (!fRegion.value || (w.regions || []).includes(fRegion.value)) && (!fState.value || w.state === fState.value) &&
  (!fSpecies.value || w.speciesCodes.includes(fSpecies.value)) && (!fType.value || w.type === fType.value) &&
  (!fStatus.value || w.status === fStatus.value) && (!fOrigin.value || w.origin === fOrigin.value)
).sort((a, b) => (a.state === 'no_data') - (b.state === 'no_data') || a.name_ru.localeCompare(b.name_ru)))

const shortDate = (s) => (s ? new Date(s).toLocaleDateString('ru-RU') : '')

async function load() {
  loading.value = true; error.value = null
  loadRegions()
  for (const e of ['water_body_types', 'water_body_statuses', 'water_body_origins', 'fishery_kinds']) loadDict(e)
  try {
    const [fc, ds, rs, sp] = await Promise.all([
      api.get('data-model', '/water-bodies.geojson'), api.get('data-admin', '/water-bodies/status'),
      api.get('algo-admin', '/water-bodies/status'), api.get('data-model', '/entities/species/records'),
    ])
    species.value = sp.map((r) => r.values)
    const spName = Object.fromEntries(species.value.map((s) => [s.code, tr(s, 'name')]))
    const datasetsSpecies = {}
    wbs.value = fc.features.map((f) => {
      const p = f.properties
      const d = ds[p.code]
      const r = rs[p.code]
      let state = 'no_data'
      if (d) {
        state = 'has_data'
        const done = r && (r.main_run || r.last_done)
        if (done) state = (d.updated_at && done.finished_at && d.updated_at > done.finished_at) ? 'stale' : 'has_run'
      }
      return { ...p, feature: f, state, years: d?.years || [], ndatasets: d ? Object.keys(d.datasets).length : 0,
        speciesCodes: [], speciesList: [], run: r, pdu: r?.pdu, updated_at: d?.updated_at }
    })
    // виды в данных водоёмов (по набору уловов)
    const sets = await api.get('data-admin', '/datasets', { dataset_type: 'catches' })
    for (const s of sets) datasetsSpecies[s.water_body] = s.summary?.species || []
    for (const w of wbs.value) {
      w.speciesCodes = datasetsSpecies[w.code] || []
      w.speciesList = w.speciesCodes.map((c) => spName[c] || c)
    }
    draw()
  } catch (e) { error.value = e } finally { loading.value = false }
}

function style(w) {
  const c = COLORS[w.state]
  return { color: c, weight: sel.value?.id === w.id ? 3 : 1.5, fillColor: c, fillOpacity: w.state === 'no_data' ? 0.25 : 0.5 }
}

function draw() {
  if (!map) return
  if (layer) layer.remove()
  layer = L.layerGroup().addTo(map)
  for (const w of wbs.value) {
    let lay
    if (w.feature.geometry && w.feature.geometry.type !== 'Point') {
      lay = L.geoJSON(w.feature, { style: () => style(w) })
    } else if (w.point) {
      lay = L.circleMarker([w.point[0], w.point[1]], { radius: 7, ...style(w), fillOpacity: 0.8 })
    } else continue
    lay.bindTooltip(`<b>${tr(w, 'name')}</b><br>${w.years.length ? w.years[0] + '–' + w.years[w.years.length - 1] : ''}${
      w.pdu?.rows?.length ? '<br>' + t('map.pdu') + ': ' + fmt(w.pdu.rows.reduce((a, r) => a + (r.pdu_t || 0), 0), 0) + ' т' : ''}`, { sticky: true })
    lay.on('click', () => select(w, false))
    lay.addTo(layer)
    layers[w.id] = lay
    if (w.state !== 'no_data' && w.point) {
      L.circleMarker([w.point[0], w.point[1]], { radius: 4, color: MAP.markerStroke, weight: 1, fillColor: COLORS[w.state], fillOpacity: 1 })
        .on('click', () => select(w, false)).addTo(layer)
    }
  }
}

function select(w, fly) {
  sel.value = w
  for (const x of wbs.value) {
    const l = layers[x.id]
    if (l && l.setStyle) l.setStyle(style(x))
  }
  if (fly && w.point) map.flyTo([w.point[0], w.point[1]], Math.max(map.getZoom(), 7), { duration: 0.6 })
}

onMounted(async () => {
  await nextTick()
  map = L.map(mapEl.value, { zoomControl: true, attributionControl: true, zoomSnap: 0.25 }).setView([48.2, 67.5], 5)
  map.createPane('land').style.zIndex = 250   // над подложкой, под маской
  map.createPane('mask').style.zIndex = 350   // над подложкой, под водоёмами (overlayPane = 400)
  tiles = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 13, attribution: 'подложка © участники OpenStreetMap' })
  map.attributionControl.setPrefix(false)
  map.attributionControl.addAttribution('граница: geoBoundaries / © участники OpenStreetMap (ODbL) · контуры водоёмов: Natural Earth')
  try {
    const kz = await api.get('data-model', '/kazakhstan.geojson')
    // запас отрисовки за краем экрана (padding: 1 = ещё один экран со всех сторон) — без «дыр» во время перелёта к водоёму
    const rLand = L.svg({ pane: 'land', padding: 1 })
    const rMask = L.svg({ pane: 'mask', padding: 1 })
    land = L.geoJSON(kz, { pane: 'land', renderer: rLand, style: { stroke: false, fillColor: MAP.land, fillOpacity: 1 }, interactive: false })
    maskLayer = L.polygon(maskLatLngs(kz), { pane: 'mask', renderer: rMask, stroke: false, fillColor: MAP.mask, fillOpacity: 1, interactive: false }).addTo(map)
    const border = borderLayer = L.geoJSON(kz, { pane: 'mask', renderer: rMask, style: { color: MAP.border, weight: 1.6, fill: false }, interactive: false }).addTo(map)
    const b = border.getBounds()
    map.fitBounds(b, { padding: [12, 12] })
    map.setMinZoom(Math.floor(map.getZoom() * 4) / 4 - 0.25)
    map.setMaxBounds(b.pad(0.15))
    map.options.maxBoundsViscosity = 1
  } catch (e) { /* граница не обязательна: без неё — обычная карта */ }
  if (basemap.value === 'osm' || !land) tiles.addTo(map); else land.addTo(map)
  await load()
})
// смена схемы (светлая/тёмная): перекрасить маску, страну, границу и водоёмы
watch(themeMode, () => {
  if (!map) return
  maskLayer && maskLayer.setStyle({ fillColor: MAP.mask })
  land && land.setStyle({ fillColor: MAP.land })
  borderLayer && borderLayer.setStyle({ color: MAP.border })
  draw()
})
onBeforeUnmount(() => map && map.remove())
watch(filtered, () => {})
</script>
<style scoped>
.map-page { display: grid; grid-template-columns: 330px 1fr; height: calc(100vh - 52px); }
.panel { border-right: 1px solid var(--fs-line); background: var(--fs-card); display: flex; flex-direction: column; min-height: 0; }
.ph { padding: 16px; border-bottom: 1px solid var(--fs-line); }
.ph h1 { margin-bottom: 10px; }
.list { overflow: auto; flex: 1; }
.item { display: flex; gap: 6px; align-items: flex-start; padding: 9px 16px; cursor: pointer; border-bottom: 1px solid var(--fs-line-soft); }
.item:hover { background: var(--fs-hover); }
.item.sel { background: var(--fs-selected); box-shadow: inset 3px 0 0 var(--fs-primary); }
.item .tag-dot { margin-top: 5px; }
.nm { font-weight: 550; }
.mapbox { position: relative; min-height: 0; }
.map { position: absolute; inset: 0; background: var(--fs-bg); }
.legend { position: absolute; left: 12px; bottom: 22px; z-index: 500; padding: 8px 12px; }
.info { position: absolute; right: 12px; top: 12px; width: 380px; max-height: calc(100% - 24px); overflow: auto; z-index: 500; box-shadow: var(--fs-shadow-pop); }
.slide-enter-active, .slide-leave-active { transition: all .2s; }
.slide-enter-from, .slide-leave-to { opacity: 0; transform: translateX(16px); }
@media (max-width: 900px) { .map-page { grid-template-columns: 1fr; grid-template-rows: 40vh 1fr; } .info { width: auto; left: 12px; } }
</style>
