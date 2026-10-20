<template>
  <div class="page">
    <StateBlock :loading="loading" :error="error">
      <template v-if="calc">
        <div class="page-head">
          <div>
            <el-button text @click="$router.push({ path: '/calculations', query: { wb: calc.water_body } })"><el-icon><ArrowLeft /></el-icon>&nbsp;{{ $t('calc.title') }}</el-button>
            <h1>{{ calc.title }}</h1>
            <div class="sub">{{ $t('common.water_body') }}: {{ calc.water_body }} · v{{ calc.current_version }}</div>
          </div>
          <div class="row">
            <el-button @click="check">{{ $t('calc.check') }}</el-button>
            <el-button v-if="auth.can('run.execute')" type="primary" :loading="busy" @click="run"><el-icon><VideoPlay /></el-icon>&nbsp;{{ $t('calc.run') }}</el-button>
          </div>
        </div>
        <div class="grid12">
          <div class="card" style="grid-column: span 7">
            <h2 style="margin-top:0">{{ $t('calc.steps') }}</h2>
            <el-form label-width="120px">
              <el-form-item :label="$t('common.name')"><el-input v-model="def.title" /></el-form-item>
              <el-form-item :label="$t('common.description')"><el-input v-model="def.description" /></el-form-item>
            </el-form>
            <div v-for="(s, i) in def.steps" :key="i" class="stp">
              <div class="row">
                <span class="num-badge">{{ i + 1 }}</span>
                <el-select v-model="s.algorithm" style="width:330px">
                  <el-option v-for="a in catalog" :key="a.code" :label="tr(a, 'title')" :value="a.code" />
                </el-select>
                <el-select v-model="s.version" clearable :placeholder="$t('calc.latest')" style="width:180px">
                  <el-option v-for="v in versionsOf(s.algorithm)" :key="v.version" :label="v.version + (v.enabled ? '' : ' (откл.)')" :value="v.version" :disabled="!v.enabled" />
                </el-select>
                <el-button text :disabled="i === 0" @click="moveStep(i, -1)"><el-icon><Top /></el-icon></el-button>
                <el-button text type="danger" @click="def.steps.splice(i, 1)"><el-icon><Delete /></el-icon></el-button>
              </div>
              <div v-if="runParams(s.algorithm).length" class="params">
                <div v-for="p in runParams(s.algorithm)" :key="p.code" class="prm">
                  <div class="small" style="width:260px">{{ tr(p, 'title') }}</div>
                  <ParamField :p="p" :species="species" :model-value="paramVal(s.algorithm, p)" :placeholder="p.default == null ? '' : String(p.default)"
                              @update:model-value="setParam(s.algorithm, p.code, $event)" />
                </div>
              </div>
            </div>
            <el-button size="small" @click="def.steps.push({ algorithm: catalog[0].code, version: null })"><el-icon><Plus /></el-icon>&nbsp;шаг</el-button>
            <div class="row" style="margin-top:14px">
              <span class="small">{{ $t('calc.formats') }}:</span>
              <el-checkbox-group v-model="def.result_formats"><el-checkbox value="json">таблицы</el-checkbox><el-checkbox value="xlsx">Excel</el-checkbox><el-checkbox value="nc">NetCDF</el-checkbox><el-checkbox value="docx">Word</el-checkbox><el-checkbox value="pdf">PDF</el-checkbox></el-checkbox-group>
            </div>
            <div class="row" style="margin-top:12px">
              <el-input v-model="def.comment" :placeholder="$t('common.comment')" style="width:340px" />
              <el-button :disabled="!auth.can('run.execute')" @click="save">{{ $t('common.save') }}</el-button>
            </div>
            <StateBlock :error="saveErr" />
          </div>
          <div style="grid-column: span 5">
            <div class="card">
              <h2 style="margin-top:0">{{ $t('calc.plan') }}</h2>
              <div v-if="!plan" class="muted">Нажмите «{{ $t('calc.check') }}».</div>
              <template v-else>
                <el-alert :type="plan.ok ? 'success' : 'error'" :closable="false" show-icon :title="plan.ok ? $t('calc.ready') : $t('calc.not_ready')">
                  <ul v-if="plan.errors.length" style="margin:4px 0 0; padding-left:18px"><li v-for="e in plan.errors" :key="e">{{ e }}</li></ul>
                </el-alert>
                <el-alert v-for="w in plan.warnings" :key="w" type="warning" :closable="false" :title="w" style="margin-top:6px" />
                <template v-if="plan.plan?.steps">
                  <h3>{{ $t('calc.steps') }}</h3>
                  <div v-for="s in plan.plan.steps" :key="s.algorithm" class="small">{{ s.title }} <span class="mono">{{ s.version }}</span><span v-if="s.profile_version" class="muted"> · профиль v{{ s.profile_version }}</span></div>
                  <h3>{{ $t('calc.datasets_used') }}</h3>
                  <div v-for="(d, k) in plan.plan.datasets" :key="k" class="small"><router-link :to="'/data/' + d.dataset_id">{{ k }}</router-link> v{{ d.version }}</div>
                </template>
              </template>
            </div>
            <div class="card">
              <h2 style="margin-top:0">{{ $t('runs.title') }}</h2>
              <el-form v-if="lastDone" label-position="top">
                <el-form-item :label="$t('calc.from_step')">
                  <div class="row">
                    <el-select v-model="fromStep" clearable style="width:240px"><el-option v-for="s in def.steps.slice(1)" :key="s.algorithm" :label="titleOf(s.algorithm)" :value="s.algorithm" /></el-select>
                    <span class="muted small">{{ lastDone.id.slice(-6) }}</span>
                  </div>
                </el-form-item>
              </el-form>
              <el-table :data="runs" size="small" @row-click="(r) => $router.push('/runs/' + r.id)" style="cursor:pointer">
                <el-table-column :label="$t('common.date')"><template #default="{ row }">{{ new Date(row.created_at).toLocaleString('ru-RU') }}</template></el-table-column>
                <el-table-column :label="$t('common.status')" width="120"><template #default="{ row }"><RunStatus :status="row.status" /> <el-tag v-if="row.is_main" size="small">★</el-tag></template></el-table-column>
                <el-table-column prop="author_name" :label="$t('common.author')" width="120" />
              </el-table>
            </div>
          </div>
        </div>
      </template>
    </StateBlock>
  </div>
</template>
<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api } from '../api'
import { tr } from '../i18n'
import { useAuth } from '../store/auth'
import StateBlock from '../components/StateBlock.vue'
import ParamField from '../components/ParamField.vue'
import RunStatus from '../components/RunStatus.vue'
const auth = useAuth()
const route = useRoute()
const router = useRouter()
const calc = ref(null)
const catalog = ref([])
const species = ref([])
const runs = ref([])
const plan = ref(null)
const loading = ref(true)
const error = ref(null)
const saveErr = ref(null)
const busy = ref(false)
const fromStep = ref(null)
const def = reactive({ title: '', description: '', steps: [], params: {}, result_formats: [], comment: '' })
const lastDone = computed(() => runs.value.find((r) => r.status === 'done'))
const manifestOf = (code) => catalog.value.find((a) => a.code === code)?.manifest
const titleOf = (code) => tr(catalog.value.find((a) => a.code === code) || {}, 'title') || code
const versionsOf = (code) => catalog.value.find((a) => a.code === code)?.versions || []
const runParams = (code) => (manifestOf(code)?.parameters || []).filter((p) => p.category === 'run')
function paramVal(code, p) { const v = def.params[code]?.[p.code]; return v === undefined ? (p.type.endsWith('map') ? {} : null) : v }
function setParam(code, k, v) { def.params[code] = { ...(def.params[code] || {}), [k]: v } }
function moveStep(i, d) { const s = def.steps.splice(i, 1)[0]; def.steps.splice(i + d, 0, s) }
function body() {
  const params = {}
  for (const [a, ps] of Object.entries(def.params)) {
    const clean = Object.fromEntries(Object.entries(ps).filter(([, v]) => v !== null && v !== '' && !(Array.isArray(v) && !v.length) && !(typeof v === 'object' && !Array.isArray(v) && v && !Object.keys(v).length)))
    if (Object.keys(clean).length) params[a] = clean
  }
  return { title: def.title, description: def.description, water_body: calc.value.water_body, steps: def.steps, params,
    datasets: calc.value.datasets || {}, result_formats: def.result_formats, comment: def.comment }
}
async function load() {
  try {
    const [c, cat, sp, rs] = await Promise.all([api.get('algo-admin', `/calculations/${route.params.id}`), api.get('algo-admin', '/catalog'),
      api.get('data-model', '/entities/species/records'), api.get('algo-admin', '/runs', { calculation: route.params.id, limit: 20 })])
    calc.value = c; catalog.value = cat; runs.value = rs
    species.value = sp.map((r) => r.values)
    Object.assign(def, { title: c.title, description: c.description, steps: JSON.parse(JSON.stringify(c.steps)), params: JSON.parse(JSON.stringify(c.params || {})),
      result_formats: [...(c.result_formats || [])], comment: '' })
  } catch (e) { error.value = e } finally { loading.value = false }
}
async function save() {
  saveErr.value = null
  try { calc.value = await api.put('algo-admin', `/calculations/${calc.value.id}`, body()); ElMessage.success('Сохранена новая версия расчёта'); def.comment = '' }
  catch (e) { saveErr.value = e }
}
async function check() {
  saveErr.value = null
  try { await api.put('algo-admin', `/calculations/${calc.value.id}`, body()); plan.value = await api.post('algo-admin', `/calculations/${calc.value.id}/check`, {}) }
  catch (e) { saveErr.value = e }
}
async function run() {
  busy.value = true; saveErr.value = null
  try {
    await api.put('algo-admin', `/calculations/${calc.value.id}`, body())
    const r = await api.post('algo-admin', `/calculations/${calc.value.id}/run`, fromStep.value ? { from_step: fromStep.value, base_run: lastDone.value.id } : {})
    router.push('/runs/' + r.id)
  } catch (e) { saveErr.value = e; plan.value = { ok: false, errors: Array.isArray(e.details) ? e.details : [e.message], warnings: [] } }
  finally { busy.value = false }
}
onMounted(load)
</script>
<style scoped>
.stp { border: 1px solid var(--fs-line); border-radius: 8px; padding: 10px; margin-bottom: 8px; background: #fbfcfd; }
.num-badge { width: 24px; height: 24px; border-radius: 50%; background: #1d5c7a; color: #fff; display: grid; place-items: center; font-size: 12px; }
.params { margin: 8px 0 0 32px; }
.prm { display: flex; gap: 10px; align-items: flex-start; padding: 4px 0; border-top: 1px dashed #edf1f4; }
</style>
