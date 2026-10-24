<template>
  <div class="page">
    <div class="page-head">
      <div><h1>{{ $t('calcs.title') }}</h1><div class="sub">{{ $t('calcs.sub') }}</div></div>
      <div class="row">
        <el-button v-if="auth.can('run.execute')" type="primary" data-test="calc-new" @click="formOpen = true"><el-icon><Plus /></el-icon>&nbsp;{{ $t('calcs.new') }}</el-button>
      </div>
    </div>
    <div class="card filters">
      <WaterBodySelect v-model="wb" clearable @update:model-value="sync" />
      <el-select v-model="algo" clearable :placeholder="$t('calcs.algorithm')" style="width:300px" @change="sync">
        <el-option v-for="a in catalog.filter((x) => !x.planned)" :key="a.code" :label="algoLabel(a, tr)" :value="a.code" />
      </el-select>
      <el-checkbox v-model="onlyStale" @change="sync">{{ $t('calcs.only_stale') }}</el-checkbox>
      <div class="grow" />
      <span class="muted small">{{ $t('calcs.queued_n', { n: queue.queued?.length ?? 0 }) }} · {{ $t('calcs.running_n', { n: queue.running?.length ?? 0 }) }}</span>
      <el-button v-if="auth.can('run.execute') && staleCount" type="warning" plain :loading="recalcBusy" data-test="recalc-stale" @click="recalc">
        {{ $t('calcs.recalc_stale', { n: staleCount }) }}
      </el-button>
    </div>
    <StateBlock :loading="loading" :error="error" :empty="!shown.length" :empty-text="items.length ? $t('calcs.empty_filtered') : $t('calcs.empty')">
      <div class="card">
        <el-table :data="shown" row-key="id" style="cursor:pointer" data-test="calcs-table" @row-click="(r) => $router.push('/calc/calculations/' + r.id)">
          <el-table-column width="56" align="center">
            <template #default="{ row }"><span class="letter" :title="row.algorithm_title">{{ row.letter || '·' }}</span></template>
          </el-table-column>
          <el-table-column :label="$t('calcs.calc')" min-width="320">
            <template #default="{ row }">
              <b>{{ row.title }}</b>
              <div class="muted small">{{ $t('calcs.period') }}: {{ row.period_text }} · {{ row.param_set_name }}<template v-if="row.param_version"> v{{ row.param_version }}</template></div>
            </template>
          </el-table-column>
          <el-table-column v-if="!wb" :label="$t('common.water_body')" width="160" prop="water_body_name" />
          <el-table-column :label="$t('calcs.result')" width="150">
            <template #default="{ row }">
              <el-tag v-if="row.is_main" type="success" size="small">★ {{ $t('calcs.main') }}</el-tag>
              <el-tag v-else-if="row.has_result" type="info" size="small" effect="plain">{{ $t('calcs.alternative') }}</el-tag>
              <span v-else class="muted small">{{ $t('calcs.no_result') }}</span>
            </template>
          </el-table-column>
          <el-table-column :label="$t('calcs.state')" width="190"><template #default="{ row }"><CalcState :calc="row" /></template></el-table-column>
          <el-table-column :label="$t('calcs.finished')" width="150"><template #default="{ row }"><span class="small">{{ dt(row.result?.finished_at) }}</span></template></el-table-column>
          <el-table-column v-if="auth.can('run.execute')" width="210" align="right">
            <template #default="{ row }">
              <el-button v-if="!isActive(row)" size="small" @click.stop="run(row)">{{ row.has_result ? $t('calcs.rerun') : $t('calcs.run') }}</el-button>
              <el-button v-if="row.has_result && !row.is_main" size="small" type="success" plain @click.stop="setMain(row)">★</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </StateBlock>
    <CalcForm v-model="formOpen" :preset="{ water_body: wb, algorithm: algo }" @saved="(c) => $router.push('/calc/calculations/' + c.id)" />
  </div>
</template>
<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { api } from '../api'
import { tr } from '../i18n'
import { useAuth } from '../store/auth'
import { algoLabel, dt, isActive, loadCatalog } from '../calcs'
import StateBlock from '../components/StateBlock.vue'
import WaterBodySelect from '../components/WaterBodySelect.vue'
import CalcState from '../components/CalcState.vue'
import CalcForm from '../components/CalcForm.vue'
const auth = useAuth()
const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const wb = ref(route.query.wb || null)
const algo = ref(route.query.algorithm || null)
const onlyStale = ref(route.query.stale === '1')
const items = ref([])
const catalog = ref([])
const queue = ref({})
const loading = ref(true)
const error = ref(null)
const formOpen = ref(false)
const recalcBusy = ref(false)
let timer
const shown = computed(() => items.value.filter((c) => !onlyStale.value || c.stale?.length))
const staleCount = computed(() => items.value.filter((c) => c.stale?.length && !isActive(c)).length)
function sync() {
  const q = {}
  if (wb.value) q.wb = wb.value
  if (algo.value) q.algorithm = algo.value
  if (onlyStale.value) q.stale = '1'
  router.replace({ query: q }); load()
}
async function load() {
  try {
    const [c, qu] = await Promise.all([api.get('algo-admin', '/calcs', { water_body: wb.value, algorithm: algo.value }),
      api.get('algo-admin', '/queue').catch(() => ({}))])
    items.value = c; queue.value = qu; error.value = null
  } catch (e) { error.value = e } finally { loading.value = false }
}
async function run(row) {
  try { await api.post('algo-admin', `/calcs/${row.id}/run`); await load() } catch (e) { ElMessage.error(e.details?.join('; ') || e.message) }
}
async function setMain(row) {
  try { await api.post('algo-admin', `/calcs/${row.id}/main`); ElMessage.success(t('calcs.main_done')); await load() } catch (e) { ElMessage.error(e.message) }
}
async function recalc() {
  recalcBusy.value = true
  try {
    const r = await api.post('algo-admin', '/calcs/recalc-stale', { water_body: wb.value || null })
    ElMessage.success(t('calcs.recalc_done', { n: r.queued.length }) + (r.skipped.length ? ' · ' + t('calcs.recalc_skipped', { n: r.skipped.length }) : ''))
    await load()
  } catch (e) { ElMessage.error(e.message) } finally { recalcBusy.value = false }
}
onMounted(async () => {
  catalog.value = (await loadCatalog()).list
  await load()
  timer = setInterval(() => { if (items.value.some(isActive) || queue.value.queued?.length || queue.value.running?.length) load() }, 4000)
})
onBeforeUnmount(() => clearInterval(timer))
</script>
<style scoped>
.filters { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; padding: 10px 16px; margin-bottom: 14px; }
.letter { display: inline-grid; place-items: center; width: 28px; height: 28px; border-radius: 50%; background: var(--fs-primary); color: var(--fs-on-primary); font-weight: 600; }
</style>
