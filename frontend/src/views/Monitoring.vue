<template>
  <div class="page mon">
    <div ref="sentinel" class="sentinel" />
    <!-- шапка: одна строка; при прокрутке сжимается до «Зайсан · лещ · Уловы · 3 из 9» -->
    <header class="mhead" :class="{ compact }">
      <div class="mline">
        <h1 class="mtitle">{{ $t('monitoring.title') }}</h1>
        <el-select v-model="wb" filterable :placeholder="$t('monitoring.choose')" class="wbsel" @change="go">
          <el-option v-for="w in wbs" :key="w.code" :label="tr(w, 'name')" :value="w.code" />
        </el-select>
        <el-popover v-if="wb && runInfo" trigger="click" :width="380" placement="bottom-start">
          <template #reference>
            <button class="status" :class="statusKind" data-test="mon-status"><span class="sdot" />{{ statusText }}</button>
          </template>
          <div class="small">
            <template v-if="mains.length">
              <div class="muted" style="margin-bottom:4px">{{ $t('monitoring.mains') }}</div>
              <div v-for="m in mains" :key="m.id" class="mrow">
                <b>{{ m.letter }}.</b>
                <router-link v-if="canGo('/calc/', auth.role)" :to="'/calc/calculations/' + m.id">{{ m.title }}</router-link><span v-else>{{ m.title }}</span>
                <span class="muted"> · {{ m.finished_at ? new Date(m.finished_at).toLocaleDateString('ru-RU') : '—' }}</span>
                <el-tag v-if="m.stale?.length && !hideInternal" size="small" type="warning" effect="plain" :title="m.stale.join('; ')">{{ $t('calcs.stale') }}</el-tag>
              </div>
              <router-link v-if="canGo('/calc/', auth.role)" :to="{ path: '/calc/calculations', query: { wb } }" class="plink">{{ $t('mon.run_link') }} →</router-link>
            </template>
            <template v-else>
              <div>{{ $t('monitoring.no_run') }}</div>
              <router-link v-if="auth.can('run.execute')" :to="{ path: '/calc/calculations', query: { wb } }" class="plink">{{ $t('mon.start_calc') }} →</router-link>
            </template>
          </div>
        </el-popover>
        <span v-if="compact && wb" class="crumb">
          <b>{{ wbRec ? tr(wbRec, 'name') : '' }}</b> · {{ sp ? spName(sp) : $t('mon.all_species') }}
          <template v-if="bstate.section"> · {{ bstate.section }}</template>
          <template v-if="bstate.slides && bstate.count"> · {{ bstate.index }} {{ $t('mon.of') }} {{ bstate.count }}</template>
        </span>
        <span class="grow" />
        <span v-if="!compact && wbRec" class="muted small region">{{ regionNames(wbRec.regions) }}</span>
        <el-dropdown v-if="board && auth.can('dashboard.edit')" trigger="click" @command="(c) => c === 'copy' && copy()">
          <el-button text><el-icon><MoreFilled /></el-icon></el-button>
          <template #dropdown><el-dropdown-menu>
            <el-dropdown-item command="copy"><el-icon><CopyDocument /></el-icon>{{ $t('monitoring.copy') }}</el-dropdown-item>
          </el-dropdown-menu></template>
        </el-dropdown>
      </div>
      <!-- два режима: «Все виды» (водоём целиком) и «Все данные по виду» -->
      <div v-if="wb && board" class="chips">
        <button class="chip" :class="{ on: !sp }" @click="sp = null">{{ $t('mon.all_species') }}</button>
        <button v-for="s in chips" :key="s.code" class="chip" :class="{ on: sp === s.code }" :title="s.down ? $t('mon.down') : ''"
                @click="sp = sp === s.code ? null : s.code">
          <span v-if="s.down" class="cdot" />{{ s.name }}
        </button>
      </div>
    </header>
    <StateBlock :loading="loading" :error="error">
      <template v-if="wb && board">
        <DashboardBoard :board="board" :filters="filters" :species="spNames" :wb-name="wbRec ? tr(wbRec, 'name') : ''" slides
                        @species="(c) => (sp = c)" @state="(s) => (bstate = s)" />
      </template>
      <div v-else-if="!wb" class="card state">{{ $t('monitoring.choose') }}</div>
    </StateBlock>
  </div>
</template>
<script setup>
import { canGo } from '../cabinets'
import { loadRegions, regionNames } from '../regions'
loadRegions()
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { api } from '../api'
import i18n, { tr } from '../i18n'
import { useAuth } from '../store/auth'
import StateBlock from '../components/StateBlock.vue'
import DashboardBoard from '../widgets/DashboardBoard.vue'

const auth = useAuth()
const route = useRoute()
const router = useRouter()
const { t, locale } = useI18n()
const wb = ref(route.params.wb || null)
const sp = ref(route.query.sp || null)
const wbs = ref([])
const speciesList = ref([])
const board = ref(null)
const runInfo = ref(null)
const loading = ref(true)
const error = ref(null)
const bstate = ref({})
const traffic = ref([])
const wbRec = computed(() => wbs.value.find((w) => w.code === wb.value))
const spNames = computed(() => Object.fromEntries(speciesList.value.map((s) => [s.code, s.name_ru])))
const spName = (c) => { const r = speciesList.value.find((s) => s.code === c); return r ? tr(r, 'name') : c }
const filters = computed(() => ({ water_body: wb.value, species: sp.value, species_ru: sp.value ? spNames.value[sp.value] : null }))
function go(v) { sp.value = null; router.push('/monitoring/waterbody/' + v) }

// виды водоёма в порядке доли в улове; красная точка — снижение по светофору
const chips = computed(() => traffic.value.map((r) => ({ code: r._code, name: spName(r._code),
  down: Object.values(r._levels || {}).includes('down') })))
async function loadTraffic() {
  traffic.value = []
  if (!wb.value) return
  try {
    const d = await api.post('dashboards', '/widgets/data', { source: { kind: 'insight', view: 'traffic' },
      filters: { water_body: wb.value, lang: i18n.global.locale.value }, options: {} })
    traffic.value = d?.rows || []
  } catch (e) { traffic.value = [] }
}
watch([wb, locale], loadTraffic)

// основные расчёты водоёма (решение № 66): мониторинг собирает картину из них; «устарели» — не для наблюдателя (№ 55)
const mains = computed(() => Object.values(runInfo.value || {}).sort((a, b) => (a.letter || '').localeCompare(b.letter || '')))
const hideInternal = !auth.can('results.view')
const staleN = computed(() => mains.value.filter((m) => m.stale?.length).length)
const statusKind = computed(() => (!mains.value.length ? 'none' : staleN.value && !hideInternal ? 'last' : 'main'))
const statusText = computed(() => (statusKind.value === 'last' ? t('mon.status_stale', { n: staleN.value }) : t('mon.status_' + statusKind.value)))

// сжатие шапки при прокрутке (прокручивается .main)
const sentinel = ref(null)
const compact = ref(false)
let obs = null
onMounted(() => {
  const root = sentinel.value?.closest('.main') || null
  obs = new IntersectionObserver(([e]) => { compact.value = !e.isIntersecting }, { root, threshold: 0 })
  if (sentinel.value) obs.observe(sentinel.value)
})
onBeforeUnmount(() => obs?.disconnect())

onMounted(async () => {
  try {
    const [w, s, b] = await Promise.all([api.get('data-model', '/entities/water_bodies/records'),
      api.get('data-model', '/entities/species/records'), api.get('dashboards', '/dashboards/monitoring')])
    wbs.value = w.map((r) => r.values).sort((a, b) => a.name_ru.localeCompare(b.name_ru))
    speciesList.value = s.map((r) => r.values)
    board.value = b
    if (wb.value) {
      loadTraffic()
      runInfo.value = await api.get('algo-admin', `/water-bodies/${wb.value}/mains`)
    }
  } catch (e) { error.value = e } finally { loading.value = false }
})
async function copy() {
  const d = await api.post('dashboards', '/dashboards/monitoring/copy', {})
  ElMessage.success(d.title_ru)
  router.push({ path: '/design/dashboards/' + d.id, query: { wb: wb.value } })
}
</script>
<style scoped>
.mon { padding-top: 0; }
.sentinel { height: 1px; }
.mhead { position: sticky; top: 0; z-index: 20; background: var(--fs-bg); padding: 12px 0 10px; margin-bottom: 8px;
  border-bottom: 1px solid transparent; transition: padding .15s; }
.mhead.compact { padding: 6px 0; border-bottom-color: var(--fs-line); box-shadow: 0 4px 10px -8px var(--fs-muted); }
.mline { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.mtitle { margin: 0; font-size: 22px; }
.compact .mtitle { font-size: 16px; }
.wbsel { width: 240px; }
.compact .wbsel { width: 200px; }
.grow { flex: 1; }
.crumb { font-size: 13.5px; color: var(--fs-text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 50vw; }
.status { display: inline-flex; align-items: center; gap: 6px; border: 1px solid var(--fs-line); background: var(--fs-card); color: var(--fs-text);
  border-radius: 14px; padding: 3px 10px; font-size: 12.5px; cursor: pointer; font-family: inherit; }
.status:hover { border-color: var(--fs-primary-2); }
.sdot { width: 8px; height: 8px; border-radius: 50%; background: var(--fs-faint); }
.status.main .sdot { background: var(--fs-success); }
.mrow { margin-bottom: 3px; }
.status.last .sdot { background: var(--fs-warning); }
.plink { display: inline-block; margin-top: 8px; }
.chips { display: flex; gap: 6px; margin-top: 10px; overflow-x: auto; padding-bottom: 2px; scrollbar-width: thin; }
.compact .chips { margin-top: 6px; }
.chip { flex: none; border: 1px solid var(--fs-line); background: var(--fs-card); color: var(--fs-text); border-radius: 16px;
  padding: 4px 12px; font-size: 13px; cursor: pointer; font-family: inherit; display: inline-flex; align-items: center; gap: 6px; }
.chip:hover { border-color: var(--fs-primary-2); }
.chip.on { background: var(--fs-primary); border-color: var(--fs-primary); color: var(--fs-on-primary); }
.cdot { width: 7px; height: 7px; border-radius: 50%; background: var(--fs-danger); }
@media (max-width: 700px) { .region, .crumb { display: none; } .wbsel { width: 100%; } }
</style>
