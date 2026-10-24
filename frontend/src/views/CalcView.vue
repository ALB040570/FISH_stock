<template>
  <div class="page">
    <StateBlock :loading="loading" :error="error">
      <template v-if="c">
        <div class="page-head">
          <div>
            <el-button text @click="$router.push({ path: '/calc/calculations', query: { wb: c.water_body } })"><el-icon><ArrowLeft /></el-icon>&nbsp;{{ $t('calcs.title') }}</el-button>
            <h1 data-test="calc-title"><span class="letter">{{ c.letter || '·' }}</span> {{ c.title }}</h1>
            <div class="sub">
              <CalcState :calc="c" />
              <el-tooltip :content="$t('calcs.main_hint')" placement="bottom">
                <el-tag v-if="c.is_main" type="success" size="small" data-test="calc-main">★ {{ $t('calcs.main') }}</el-tag>
                <el-tag v-else-if="c.has_result" type="info" size="small" effect="plain">{{ $t('calcs.alternative') }}</el-tag>
              </el-tooltip>
              · {{ c.algorithm_title }} · {{ c.water_body_name }} · {{ c.period_text }}
              <template v-if="c.queue_position"> · {{ $t('runs.position') }}: {{ c.queue_position }}</template>
            </div>
          </div>
          <div class="row actions">
            <template v-if="auth.can('run.execute')">
              <el-button v-if="active" type="danger" plain @click="act('cancel')">{{ $t('calcs.cancel') }}</el-button>
              <el-button v-else type="primary" data-test="calc-run" :disabled="!!c.check?.errors?.length" @click="act('run')">{{ c.has_result ? $t('calcs.rerun') : $t('calcs.run') }}</el-button>
              <el-button v-if="c.has_result && !c.is_main" type="success" plain data-test="calc-set-main" @click="act('main')">★ {{ $t('calcs.set_main') }}</el-button>
              <el-button v-if="!active" @click="formOpen = true"><el-icon><Edit /></el-icon>&nbsp;{{ $t('common.edit') }}</el-button>
            </template>
            <el-dropdown v-if="full && c.has_result" trigger="click" @command="onCmd">
              <el-button><el-icon><Download /></el-icon>&nbsp;{{ $t('common.download') }}</el-button>
              <template #dropdown><el-dropdown-menu>
                <el-dropdown-item command="zip">{{ $t('calcs.export_zip') }}</el-dropdown-item>
                <el-dropdown-item command="docx" divided>{{ $t('calcs.report_docx') }}</el-dropdown-item>
                <el-dropdown-item command="pdf">{{ $t('calcs.report_pdf') }}</el-dropdown-item>
              </el-dropdown-menu></template>
            </el-dropdown>
            <el-button v-if="c.has_result" @click="$router.push('/monitoring/waterbody/' + c.water_body)">{{ $t('nav.monitoring') }}</el-button>
            <el-button v-if="auth.can('run.execute') && !active" text type="danger" @click="remove"><el-icon><Delete /></el-icon></el-button>
          </div>
        </div>
        <el-progress v-if="c.state === 'running'" :percentage="pct" :stroke-width="8" style="margin-bottom:6px" />
        <div v-if="c.state === 'running' && c.progress" class="small muted" style="margin-bottom:10px">{{ [c.progress.phase, c.progress.species].filter(Boolean).join(' · ') }}</div>
        <el-alert v-if="c.state === 'failed' && c.message" type="error" :closable="false" show-icon :title="c.message" style="margin-bottom:8px" />
        <el-alert v-if="c.stale?.length" type="warning" :closable="false" show-icon :title="$t('calcs.stale_title') + ': ' + c.stale.join('; ')" style="margin-bottom:8px" data-test="calc-stale" />
        <el-alert v-if="c.check?.errors?.length && !active" type="error" :closable="false" :title="$t('calcs.check_errors')" style="margin-bottom:8px">
          <ul class="ul"><li v-for="e in c.check.errors" :key="e">{{ e }}</li></ul>
        </el-alert>
        <el-alert v-for="w in c.check?.warnings || []" :key="w" type="info" :closable="false" :title="w" style="margin-bottom:6px" />

        <div class="card">
          <h3 style="margin-top:0">{{ $t('calcs.what') }}</h3>
          <div class="kv">
            <div class="k">{{ $t('calcs.algorithm') }}</div>
            <div><router-link :to="{ path: '/calc/catalog', hash: '#' + c.algorithm }">{{ c.algorithm_title }}</router-link>
              <span class="muted"> · {{ $t('calcs.code_version') }} {{ c.result?.version || c.version_effective }}{{ c.version ? ' (' + $t('calcs.version_pinned') + ')' : ' (' + $t('calcs.latest') + ')' }}</span></div>
            <div class="k">{{ $t('calcs.params') }}</div>
            <div><router-link v-if="auth.can('profile.view')" :to="'/calc/params/' + c.param_set">{{ c.param_set_name }}</router-link><span v-else>{{ c.param_set_name }}</span>
              <span class="muted"> · v{{ c.param_version }}</span>
              <el-tag v-if="c.param_set_current && c.param_set_current > c.param_version" size="small" type="warning" effect="plain" style="margin-left:6px">v{{ c.param_set_current }}</el-tag></div>
            <template v-if="Object.keys(c.calc_params || {}).length">
              <div class="k">{{ $t('calcs.calc_params') }}</div><div class="mono small">{{ JSON.stringify(c.calc_params) }}</div>
            </template>
            <div class="k">{{ $t('calcs.period') }}</div>
            <div>{{ c.period_text }}<span v-if="c.result?.years?.length" class="muted"> · {{ $t('calcs.years') }}: {{ c.result.years[0] }}–{{ c.result.years[c.result.years.length - 1] }}</span></div>
            <template v-if="Object.keys(c.inputs_resolved || {}).length">
              <div class="k">{{ $t('calcs.inputs') }}</div>
              <div>
                <div v-for="(i, dep) in c.inputs_resolved" :key="dep" class="inp">
                  <b>{{ i.letter }}.</b>
                  <router-link v-if="i.calc_id" :to="'/calc/calculations/' + i.calc_id">{{ i.title }}</router-link><span v-else class="muted">{{ $t('calcs.input_main_none') }}</span>
                  <span class="muted small"> · {{ i.ref === 'main' ? $t('calcs.input_main').toLowerCase() : $t('calcs.explicit') }}</span>
                  <el-tag v-if="i.calc_id && !i.has_result" size="small" type="info" effect="plain" style="margin-left:4px">{{ $t('calcs.no_result') }}</el-tag>
                </div>
              </div>
            </template>
            <template v-if="c.result">
              <div class="k">{{ $t('calcs.datasets') }}</div>
              <div class="small"><span v-for="(d, k) in c.result.datasets" :key="k" class="ds"><router-link :to="'/input/datasets/' + d.dataset_id">{{ k }}</router-link> v{{ d.version }}</span></div>
              <div class="k">{{ $t('calcs.finished') }}</div>
              <div>{{ dt(c.result.finished_at) }} · {{ c.result.by_name || '—' }} · {{ $t('calcs.duration') }} {{ dur(c.result.seconds) }}</div>
            </template>
            <template v-if="c.dependents?.length">
              <div class="k">{{ $t('calcs.dependents') }}</div>
              <div><span v-for="d in c.dependents" :key="d.id" class="ds"><b>{{ d.letter }}.</b> <router-link :to="'/calc/calculations/' + d.id">{{ d.title }}</router-link></span></div>
            </template>
            <template v-if="c.comment">
              <div class="k">{{ $t('common.comment') }}</div><div>{{ c.comment }}</div>
            </template>
          </div>
        </div>

        <div class="card">
          <div v-if="METHOD[c.algorithm]" class="method-link">
            <router-link :to="helpPath(METHOD[c.algorithm])"><el-icon><QuestionFilled /></el-icon> {{ $t('help.method_step') }}</router-link>
          </div>
          <el-tabs v-model="tab">
            <el-tab-pane v-if="full && view && result" :label="$t('calcs.view')" name="view" />
            <el-tab-pane v-if="full && result" :label="$t('calcs.tables')" name="tables" />
            <el-tab-pane v-if="full && result" :label="$t('calcs.files')" name="files" />
            <el-tab-pane :label="$t('calcs.journal')" name="journal" />
            <el-tab-pane v-if="full" :label="$t('calcs.log')" name="log" />
          </el-tabs>
          <StateBlock :loading="rLoading" :error="rError">
            <template v-if="tab === 'view' && view && result">
              <component :is="view" :data="{ payload: viewPayload(c.algorithm, result.payload) }" :filters="{}" :options="{ kind: VIEWS[c.algorithm] }" />
            </template>
            <template v-else-if="tab === 'tables' && result">
              <div v-if="Object.keys(result.metrics || {}).length" class="fs-tiles" style="margin-bottom:12px">
                <div v-for="(m, k) in result.metrics" :key="k" class="fs-tile"><div class="ft-l">{{ m.title }}</div><div class="ft-v">{{ fmt(m.value, 'auto') }}<span v-if="m.unit" class="ft-u">{{ ' ' + m.unit }}</span></div></div>
              </div>
              <el-alert v-for="n in result.notes" :key="n" type="info" :closable="false" :title="n" style="margin-bottom:6px" />
              <el-select v-model="tableCode" style="width:420px; max-width:100%; margin-bottom:8px">
                <el-option v-for="(t, k) in result.tables" :key="k" :label="t.title + ` (${t.rows.length})`" :value="k" />
              </el-select>
              <ResultTable v-if="result.tables[tableCode]" :table="result.tables[tableCode]" />
            </template>
            <template v-else-if="tab === 'files' && result">
              <el-table :data="result.files" size="small">
                <el-table-column prop="title" :label="$t('common.name')" />
                <el-table-column prop="name" label="Файл" min-width="260"><template #default="{ row }"><span class="mono">{{ row.name }}</span></template></el-table-column>
                <el-table-column prop="format" label="Формат" width="90" />
                <el-table-column width="120"><template #default="{ row }"><el-button size="small" @click="download('algo-admin', `/calcs/${c.id}/files/${row.name}`)">{{ $t('common.download') }}</el-button></template></el-table-column>
              </el-table>
            </template>
            <template v-else-if="tab === 'journal'">
              <el-table :data="journal" size="small" data-test="calc-journal">
                <el-table-column :label="$t('common.date')" width="150"><template #default="{ row }">{{ dt(row.at) }}</template></el-table-column>
                <el-table-column :label="$t('common.status')" width="120">
                  <template #default="{ row }"><el-tag size="small" :type="{ done: 'success', failed: 'danger', cancelled: 'warning' }[row.status] || 'info'">{{ row.status ? $t('calcs.st_' + row.status) : $t('calcs.j_' + row.action) }}</el-tag></template>
                </el-table-column>
                <el-table-column :label="$t('users.user')" width="160"><template #default="{ row }">{{ row.by_name || '—' }}</template></el-table-column>
                <el-table-column :label="$t('common.details')" min-width="320">
                  <template #default="{ row }">
                    <div>{{ row.message }}</div>
                    <div v-if="row.action === 'run' && row.version" class="muted small">
                      {{ $t('calcs.code_version') }} {{ row.version }} · {{ row.param_set_name }} v{{ row.param_version }}
                      <template v-if="row.years?.length"> · {{ row.years[0] }}–{{ row.years[row.years.length - 1] }}</template>
                      <template v-if="row.seconds"> · {{ dur(row.seconds) }}</template>
                      <template v-if="Object.keys(row.inputs || {}).length"> · {{ $t('calcs.inputs').toLowerCase() }}: {{ Object.values(row.inputs).map((i) => i.title).join('; ') }}</template>
                    </div>
                  </template>
                </el-table-column>
              </el-table>
            </template>
            <template v-else-if="tab === 'log'">
              <el-alert v-if="log?.message" :type="log.state === 'done' ? 'success' : log.state === 'failed' ? 'error' : 'info'" :closable="false" :title="log.message" style="margin-bottom:8px" />
              <pre class="code-editor" style="min-height:200px; max-height:520px; overflow:auto">{{ log?.log }}</pre>
              <pre v-if="log?.traceback" class="code-editor" style="min-height:100px; color:var(--fs-danger)">{{ log.traceback }}</pre>
            </template>
          </StateBlock>
        </div>
        <CalcForm v-model="formOpen" :calc="c" @saved="(x) => { c = x; loadResult() }" />
      </template>
    </StateBlock>
  </div>
</template>
<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { api, download } from '../api'
import { helpPath } from '../cabinets'
import { useAuth } from '../store/auth'
import { fmt } from '../components/charts'
import { METHOD, VIEWS, dt, dur, isActive, viewPayload } from '../calcs'
import StateBlock from '../components/StateBlock.vue'
import CalcState from '../components/CalcState.vue'
import CalcForm from '../components/CalcForm.vue'
import ResultTable from '../components/ResultTable.vue'
import specials from '../widgets/specials'
const auth = useAuth()
const { t } = useI18n()
// без права на результаты («Презентация», наблюдатель, № 62) — определение, состояние и журнал, без таблиц и файлов
const full = auth.can('results.view')
const route = useRoute()
const router = useRouter()
const c = ref(null)
const loading = ref(true)
const error = ref(null)
const result = ref(null)
const journal = ref([])
const log = ref(null)
const tab = ref('journal')
const rLoading = ref(false)
const rError = ref(null)
const tableCode = ref(null)
const formOpen = ref(false)
let timer
let resultId = null
const active = computed(() => isActive(c.value))
const view = computed(() => specials[VIEWS[c.value?.algorithm]])
const pct = computed(() => Math.round((c.value?.progress?.fraction || 0) * 100))
async function load() {
  try {
    c.value = await api.get('algo-admin', `/calcs/${route.params.id}`)
    error.value = null
    const rid = c.value.result?.result_id || null
    if (rid !== resultId) { resultId = rid; await loadResult() }
    if (tab.value === 'journal' || active.value) journal.value = await api.get('algo-admin', `/calcs/${c.value.id}/journal`)
  } catch (e) { error.value = e } finally { loading.value = false }
}
async function loadResult() {
  result.value = null
  journal.value = await api.get('algo-admin', `/calcs/${c.value.id}/journal`).catch(() => [])
  if (!full || !c.value.has_result) { tab.value = full && c.value.state === 'failed' ? 'log' : 'journal'; return }
  rLoading.value = true
  try {
    result.value = await api.get('algo-admin', `/calcs/${c.value.id}/result`)
    tableCode.value = Object.keys(result.value.tables || {})[0]
    tab.value = view.value ? 'view' : 'tables'
  } catch (e) { rError.value = e } finally { rLoading.value = false }
}
watch(tab, async (x) => {
  if (x === 'log' && c.value) log.value = await api.get('algo-admin', `/calcs/${c.value.id}/log`).catch(() => null)
  if (x === 'journal' && c.value) journal.value = await api.get('algo-admin', `/calcs/${c.value.id}/journal`).catch(() => journal.value)
})
async function act(what) {
  try {
    c.value = await api.post('algo-admin', `/calcs/${c.value.id}/${what}`)
    if (what === 'main') ElMessage.success(t('calcs.main_done'))
  } catch (e) { ElMessage.error([e.message, ...(e.details || [])].join(': ')) }
}
async function remove() {
  try { await ElMessageBox.confirm(t('calcs.delete_confirm', { t: c.value.title }), '', { type: 'warning' }) } catch { return }
  try { await api.del('algo-admin', `/calcs/${c.value.id}`); ElMessage.success(t('calcs.deleted')); router.push({ path: '/calc/calculations', query: { wb: c.value.water_body } }) }
  catch (e) { ElMessage.error([e.message, ...(e.details || [])].join(': ')) }
}
function onCmd(cmd) {
  if (cmd === 'zip') download('algo-admin', `/calcs/${c.value.id}/export.zip`)
  else download('algo-admin', `/water-bodies/${c.value.water_body}/report.${cmd}`)
}
onMounted(() => { load(); timer = setInterval(() => { if (active.value) load() }, 2500) })
onBeforeUnmount(() => clearInterval(timer))
watch(() => route.params.id, () => { if (route.params.id) { resultId = null; loading.value = true; load() } })
</script>
<style scoped>
.letter { display: inline-grid; place-items: center; width: 32px; height: 32px; border-radius: 50%; background: var(--fs-primary); color: var(--fs-on-primary); font-weight: 600; font-size: 17px; vertical-align: middle; }
.actions { flex-wrap: wrap; justify-content: flex-end; }
.kv { display: grid; grid-template-columns: 200px 1fr; gap: 8px 16px; align-items: baseline; }
.kv .k { color: var(--fs-muted); }
.inp { margin-bottom: 2px; }
.ds { display: inline-block; margin-right: 12px; }
.ul { margin: 4px 0 0; padding-left: 18px; }
.method-link { float: right; font-size: 13px; margin-top: 10px; position: relative; z-index: 1; }
.method-link a { color: var(--fs-link); text-decoration: none; display: inline-flex; gap: 4px; align-items: center; }
@media (max-width: 640px) { .kv { grid-template-columns: 1fr; gap: 2px; } .kv .k { margin-top: 8px; } }
</style>
