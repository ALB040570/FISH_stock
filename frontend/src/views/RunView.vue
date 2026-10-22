<template>
  <div class="page">
    <StateBlock :loading="loading" :error="error">
      <template v-if="run">
        <div class="page-head">
          <div>
            <el-button text @click="$router.push('/runs')"><el-icon><ArrowLeft /></el-icon>&nbsp;{{ $t('runs.title') }}</el-button>
            <h1>{{ run.calculation_title }}</h1>
            <div class="sub">
              <RunStatus :status="run.status" /> <el-tag v-if="run.is_main" type="success" size="small">★ {{ $t('runs.is_main') }}</el-tag>
              · {{ run.water_body }} · {{ run.author_name }} · {{ new Date(run.created_at).toLocaleString('ru-RU') }}
              <template v-if="run.queue_position"> · {{ $t('runs.position') }}: {{ run.queue_position }}</template>
            </div>
          </div>
          <div class="row">
            <el-button v-if="['queued', 'running'].includes(run.status) && auth.can('run.execute')" type="danger" plain @click="cancel">{{ $t('runs.cancel') }}</el-button>
            <template v-if="run.status === 'done'">
              <el-button v-if="!run.is_main && auth.can('run.execute')" type="success" plain @click="setMain">★ {{ $t('runs.set_main') }}</el-button>
              <el-button @click="download('algo-admin', `/runs/${run.id}/export.zip`)">{{ $t('runs.export_zip') }}</el-button>
              <el-button @click="download('algo-admin', `/runs/${run.id}/report.docx`)">{{ $t('runs.report_docx') }}</el-button>
              <el-button @click="download('algo-admin', `/runs/${run.id}/report.pdf`)">{{ $t('runs.report_pdf') }}</el-button>
              <el-button type="primary" @click="$router.push('/monitoring/' + run.water_body)">{{ $t('nav.monitoring') }}</el-button>
            </template>
          </div>
        </div>
        <el-alert v-if="run.message && run.status !== 'done'" :type="run.status === 'failed' ? 'error' : 'info'" :closable="false" show-icon :title="run.message" style="margin-bottom:12px" />
        <el-alert v-for="w in run.warnings" :key="w" type="warning" :closable="false" :title="w" style="margin-bottom:6px" />
        <div class="card">
          <div class="steps">
            <div v-for="(s, i) in run.steps" :key="i" class="st" :class="[s.status, { sel: i === cur }]" @click="pick(i)">
              <div class="row" style="gap:6px"><span class="num-badge">{{ i + 1 }}</span><b>{{ s.title }}</b></div>
              <div class="small muted">{{ s.version }} · <RunStatus :status="s.status" /><template v-if="s.seconds"> · {{ dur(s.seconds) }}</template></div>
              <el-progress v-if="s.status === 'running' && run.progress" :percentage="Math.round((run.progress.fraction || 0) * 100)" :stroke-width="6" style="margin-top:4px" />
              <div v-if="s.status === 'running' && run.progress" class="small muted">{{ [run.progress.phase, run.progress.species].filter(Boolean).join(' · ') }}</div>
              <div v-if="s.reused_run" class="small muted">{{ $t('runs.reused') }} <router-link :to="'/runs/' + s.reused_run">{{ s.reused_run.slice(-6) }}</router-link></div>
            </div>
          </div>
        </div>
        <div v-if="cur !== null" class="card">
          <div v-if="METHOD[run.steps[cur].algorithm]" class="method-link">
            <router-link :to="'/help/' + METHOD[run.steps[cur].algorithm]"><el-icon><QuestionFilled /></el-icon> {{ $t('help.method_step') }}</router-link>
          </div>
          <el-tabs v-model="tab">
            <el-tab-pane v-if="view && result" :label="$t('runs.view')" name="view" />
            <el-tab-pane :label="$t('runs.tables')" name="tables" />
            <el-tab-pane :label="$t('runs.files')" name="files" />
            <el-tab-pane :label="$t('common.log')" name="log" />
            <el-tab-pane :label="$t('catalog.params')" name="params" />
          </el-tabs>
          <StateBlock :loading="rLoading" :error="rError">
            <template v-if="tab === 'view' && view && result">
              <component :is="view" :data="{ payload: result.payload }" :filters="{}" :options="{ kind: viewKind }" />
            </template>
            <template v-else-if="tab === 'tables' && result">
              <div v-if="Object.keys(result.metrics || {}).length" class="kpis" style="margin-bottom:10px">
                <div v-for="(m, k) in result.metrics" :key="k" class="kpi"><div class="v">{{ fmt(m.value, 'auto') }}{{ m.unit ? ' ' + m.unit : '' }}</div><div class="l">{{ m.title }}</div></div>
              </div>
              <el-alert v-for="n in result.notes" :key="n" type="info" :closable="false" :title="n" style="margin-bottom:6px" />
              <el-select v-model="tableCode" style="width:420px; margin-bottom:8px">
                <el-option v-for="(t, k) in result.tables" :key="k" :label="t.title + ` (${t.rows.length})`" :value="k" />
              </el-select>
              <ResultTable v-if="result.tables[tableCode]" :table="result.tables[tableCode]" />
            </template>
            <template v-else-if="tab === 'files' && result">
              <el-table :data="result.files" size="small">
                <el-table-column prop="title" :label="$t('common.name')" />
                <el-table-column prop="name" label="Файл" min-width="260"><template #default="{ row }"><span class="mono">{{ row.name }}</span></template></el-table-column>
                <el-table-column prop="format" label="Формат" width="90" />
                <el-table-column width="120"><template #default="{ row }"><el-button size="small" @click="download('algo-admin', `/runs/${run.id}/steps/${cur}/files/${row.name}`)">{{ $t('common.download') }}</el-button></template></el-table-column>
              </el-table>
            </template>
            <template v-else-if="tab === 'log'">
              <el-alert v-if="log?.message" :type="log.status === 'done' ? 'success' : 'error'" :closable="false" :title="log.message" style="margin-bottom:8px" />
              <pre class="code-editor" style="min-height:200px; max-height:520px; overflow:auto">{{ log?.log }}</pre>
              <pre v-if="log?.traceback" class="code-editor" style="min-height:100px; color:var(--fs-danger)">{{ log.traceback }}</pre>
            </template>
            <template v-else-if="tab === 'params'">
              <pre class="code-editor" style="min-height:200px">{{ JSON.stringify(run.steps[cur].params, null, 1) }}</pre>
              <div class="small muted">Наборы данных: <span v-for="(d, k) in run.datasets" :key="k"><router-link :to="'/data/' + d.dataset_id">{{ k }}</router-link> v{{ d.version }}; </span></div>
              <div class="small muted">Контрольная сумма пакета: <span class="mono">{{ run.steps[cur].checksum }}</span></div>
            </template>
          </StateBlock>
        </div>
      </template>
    </StateBlock>
  </div>
</template>
<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api, download } from '../api'
const METHOD = { seine_catchability: 'method-seine', stock_by_catch: 'method-stock', pdu_by_age: 'method-pdu-age', bayes_cohort: 'method-bayes', forecast_pdu: 'method-forecast' }
import { useAuth } from '../store/auth'
import { fmt } from '../components/charts'
import StateBlock from '../components/StateBlock.vue'
import RunStatus from '../components/RunStatus.vue'
import ResultTable from '../components/ResultTable.vue'
import specials from '../widgets/specials'
const VIEWS = { seine_catchability: 'seine_curves', stock_by_catch: 'net_curves', pdu_by_age: 'pdu_breakdown', bayes_cohort: 'bayes_band', forecast_pdu: 'forecast_scenarios' }
const auth = useAuth()
const route = useRoute()
const run = ref(null)
const loading = ref(true)
const error = ref(null)
const cur = ref(null)
const tab = ref('tables')
const result = ref(null)
const log = ref(null)
const rLoading = ref(false)
const rError = ref(null)
const tableCode = ref(null)
let timer
const viewKind = computed(() => VIEWS[run.value?.steps[cur.value]?.algorithm])
const view = computed(() => specials[viewKind.value])
const dur = (s) => (s >= 60 ? `${Math.floor(s / 60)} мин ${Math.round(s % 60)} с` : `${s} с`)
async function load() {
  try {
    run.value = await api.get('algo-admin', `/runs/${route.params.id}`)
    error.value = null
    if (cur.value === null) {
      const done = run.value.steps.map((s, i) => [s, i]).filter(([s]) => ['done', 'reused'].includes(s.status))
      const running = run.value.steps.findIndex((s) => s.status === 'running')
      if (running >= 0) pick(running)
      else if (done.length) pick(done[done.length - 1][1])
    }
    if (['done', 'failed', 'cancelled'].includes(run.value.status)) clearInterval(timer)
  } catch (e) { error.value = e } finally { loading.value = false }
}
async function pick(i) {
  cur.value = i; result.value = null; log.value = null; rError.value = null
  const s = run.value.steps[i]
  tab.value = ['done', 'reused'].includes(s.status) ? (VIEWS[s.algorithm] ? 'view' : 'tables') : 'log'
  await loadStep()
}
async function loadStep() {
  const s = run.value.steps[cur.value]
  rLoading.value = true
  try {
    if (['done', 'reused'].includes(s.status)) {
      result.value = await api.get('algo-admin', `/runs/${run.value.id}/steps/${cur.value}/result`)
      tableCode.value = Object.keys(result.value.tables || {})[0]
    }
    if (s.dir || s.status === 'reused') log.value = await api.get('algo-admin', `/runs/${run.value.id}/steps/${cur.value}/log`)
  } catch (e) { rError.value = e } finally { rLoading.value = false }
}
watch(tab, async (t) => { if (t === 'log' && cur.value !== null) log.value = await api.get('algo-admin', `/runs/${run.value.id}/steps/${cur.value}/log`).catch(() => null) })
async function cancel() { run.value = await api.post('algo-admin', `/runs/${run.value.id}/cancel`) }
async function setMain() { run.value = await api.post('algo-admin', `/runs/${run.value.id}/main`); ElMessage.success('Запуск отмечен основным для мониторинга') }
onMounted(() => { load(); timer = setInterval(async () => { const before = run.value?.steps.map((s) => s.status).join(); await load(); if (cur.value !== null && before !== run.value.steps.map((s) => s.status).join()) loadStep() }, 2500) })
onBeforeUnmount(() => clearInterval(timer))
</script>
<style scoped>
.steps { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 10px; }
.st { border: 1px solid var(--fs-line); border-radius: 8px; padding: 10px; cursor: pointer; background: var(--fs-card-soft); }
.st.sel { border-color: var(--fs-primary); box-shadow: 0 0 0 1px var(--fs-primary) inset; }
.st.done, .st.reused { background: var(--fs-success-bg); }
.st.failed { background: var(--fs-danger-bg); }
.num-badge { width: 22px; height: 22px; border-radius: 50%; background: var(--fs-primary); color: var(--fs-on-primary); display: grid; place-items: center; font-size: 12px; }
.method-link { float: right; font-size: 13px; margin-top: 10px; position: relative; z-index: 1; }
.method-link a { color: var(--fs-primary); text-decoration: none; display: inline-flex; gap: 4px; align-items: center; }
</style>
