<template>
  <el-dialog :model-value="modelValue" :title="calc ? $t('calcs.edit') : $t('calcs.new')" width="760px" class="fs-dialog-wide"
             @update:model-value="$emit('update:modelValue', $event)" @open="init">
    <el-form label-position="top" class="calc-form" data-test="calc-form">
      <div class="two">
        <el-form-item :label="$t('calcs.algorithm')">
          <el-select v-model="f.algorithm" filterable :disabled="!!calc" style="width:100%" data-test="calc-algorithm" @change="onAlgo">
            <el-option v-for="a in algos" :key="a.code" :label="algoLabel(a, tr)" :value="a.code" />
          </el-select>
        </el-form-item>
        <el-form-item :label="$t('common.water_body')">
          <WaterBodySelect v-model="f.water_body" :disabled="!!calc" style="width:100%" @update:model-value="loadInputs" />
        </el-form-item>
      </div>
      <el-form-item :label="$t('calcs.period')">
        <div class="row" style="gap:8px">
          <span class="muted">{{ $t('calcs.from') }}</span>
          <el-input-number v-model="f.from" :controls="false" :min="1950" :max="2100" :placeholder="$t('calcs.all_years')" style="width:120px" />
          <span class="muted">{{ $t('calcs.to') }}</span>
          <el-input-number v-model="f.to" :controls="false" :min="1950" :max="2100" :placeholder="$t('calcs.all_years')" style="width:120px" />
        </div>
      </el-form-item>
      <el-form-item v-if="inputs.length" :label="$t('calcs.inputs')">
        <div class="inputs">
          <div v-for="dep in inputs" :key="dep" class="row inp">
            <span class="dep">{{ algoLabel(byCode[dep], tr) }}</span>
            <el-select v-model="f.inputs[dep]" style="flex:1; min-width:280px" :data-test="'calc-input-' + dep">
              <el-option value="main" :label="mainLabel(dep)" />
              <el-option v-for="c in alts(dep)" :key="c.id" :value="c.id" :label="c.title + (c.has_result ? ' · ' + dt(c.result?.finished_at) : ' · ' + $t('calcs.no_result'))" />
            </el-select>
          </div>
          <div class="muted small">{{ $t('calcs.inputs_hint') }}</div>
        </div>
      </el-form-item>
      <div class="two">
        <el-form-item :label="$t('calcs.params')">
          <el-select v-model="f.param_set" style="width:100%" data-test="calc-param-set" @change="onSet">
            <el-option v-for="s in sets" :key="s.id" :value="s.id" :label="s.name + (s.is_default ? ' ★' : '')" />
          </el-select>
        </el-form-item>
        <el-form-item :label="$t('calcs.param_version')">
          <el-select v-model="f.param_version" style="width:100%">
            <el-option v-for="v in setVersions" :key="v.n" :value="v.n" :label="'v' + v.n + (v.n === curSet?.current_version ? ' · ' + $t('params.current') : '') + (v.comment ? ' · ' + v.comment : '')" />
          </el-select>
        </el-form-item>
      </div>
      <el-form-item v-for="p in calcParams" :key="p.code" :label="tr(p, 'title') || p.code">
        <ParamField :p="p" v-model="f.calc_params[p.code]" :species="species" />
      </el-form-item>
      <div class="two">
        <el-form-item :label="$t('calcs.code_version')">
          <el-select v-model="f.version" style="width:100%">
            <el-option :value="null" :label="$t('calcs.latest') + (algo?.latest ? ' (' + algo.latest + ')' : '')" />
            <el-option v-for="v in (algo?.versions || []).filter((x) => x.enabled)" :key="v.version" :value="v.version" :label="v.version + ' · ' + $t('calcs.version_pinned')" />
          </el-select>
        </el-form-item>
        <el-form-item :label="$t('common.name')">
          <el-input v-model="f.title" :placeholder="$t('calcs.title_ph')" />
        </el-form-item>
      </div>
      <el-form-item :label="$t('common.comment')"><el-input v-model="f.comment" /></el-form-item>
    </el-form>
    <StateBlock :error="err" />
    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">{{ $t('common.cancel') }}</el-button>
      <el-button :loading="busy" :disabled="!ready" @click="save(false)">{{ $t('calcs.save') }}</el-button>
      <el-button type="primary" :loading="busy" :disabled="!ready" data-test="calc-save-run" @click="save(true)">{{ $t('calcs.save_run') }}</el-button>
    </template>
  </el-dialog>
</template>
<script setup>
import { computed, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api'
import { tr } from '../i18n'
import { algoLabel, calcParamsOf, dt, inputsOf, loadCatalog } from '../calcs'
import StateBlock from './StateBlock.vue'
import WaterBodySelect from './WaterBodySelect.vue'
import ParamField from './ParamField.vue'
const props = defineProps({ modelValue: Boolean, calc: Object, preset: Object })
const emit = defineEmits(['update:modelValue', 'saved'])
const { t } = useI18n()
const algos = ref([])
const byCode = ref({})
const sets = ref([])
const setVersions = ref([])
const others = ref([])
const species = ref([])
const busy = ref(false)
const err = ref(null)
const f = reactive({ algorithm: null, water_body: null, from: null, to: null, inputs: {}, param_set: null, param_version: null,
  calc_params: {}, version: null, title: '', comment: '' })
const algo = computed(() => byCode.value[f.algorithm])
const inputs = computed(() => inputsOf(algo.value))
const calcParams = computed(() => calcParamsOf(algo.value))
const curSet = computed(() => sets.value.find((s) => s.id === f.param_set))
const ready = computed(() => f.algorithm && f.water_body && f.param_set)
const alts = (dep) => others.value.filter((c) => c.algorithm === dep)
function mainLabel(dep) {
  const m = others.value.find((c) => c.algorithm === dep && c.is_main)
  return m ? `★ ${m.title}` : `★ (${t('calcs.input_main_none')})`
}
async function init() {
  err.value = null
  if (!algos.value.length) {
    const c = await loadCatalog()
    algos.value = c.list.filter((a) => !a.planned && a.latest)
    byCode.value = c.byCode
    const sp = await api.get('data-model', '/entities/species/records')
    species.value = sp.map((r) => r.values)
  }
  const c = props.calc
  const pr = props.preset || {}
  Object.assign(f, {
    algorithm: c?.algorithm || pr.algorithm || null, water_body: c?.water_body || pr.water_body || null,
    from: c?.period?.from ?? null, to: c?.period?.to ?? null, inputs: { ...(c?.inputs || {}) },
    param_set: c?.param_set || null, param_version: c?.param_version || null, calc_params: { ...(c?.calc_params || {}) },
    version: c?.version || null, title: c?.title || '', comment: '' })
  await onAlgo(true)
}
async function onAlgo(keep) {
  if (!f.algorithm) return
  sets.value = await api.get('algo-admin', '/param-sets', { algorithm: f.algorithm })
  if (keep !== true || !f.param_set) f.param_set = (sets.value.find((s) => s.is_default) || sets.value[0])?.id || null
  for (const dep of inputs.value) if (!f.inputs[dep]) f.inputs[dep] = 'main'
  for (const k of Object.keys(f.inputs)) if (!inputs.value.includes(k)) delete f.inputs[k]
  await Promise.all([onSet(keep === true), loadInputs()])
}
async function onSet(keep) {
  setVersions.value = []
  if (!f.param_set) return
  try {
    const s = await api.get('algo-admin', `/param-sets/${f.param_set}`)
    setVersions.value = s.versions
    if (keep !== true || !f.param_version) f.param_version = s.current_version
  } catch (e) {
    const s = curSet.value
    setVersions.value = s?.current_version ? [{ n: s.current_version }] : []
    f.param_version = s?.current_version || null
  }
}
async function loadInputs() {
  if (!f.water_body || !inputs.value.length) { others.value = []; return }
  const all = await api.get('algo-admin', '/calcs', { water_body: f.water_body })
  others.value = all.filter((c) => inputs.value.includes(c.algorithm) && c.id !== props.calc?.id)
  for (const dep of inputs.value) if (f.inputs[dep] !== 'main' && !others.value.some((c) => c.id === f.inputs[dep])) f.inputs[dep] = 'main'
}
async function save(run) {
  busy.value = true; err.value = null
  const body = { algorithm: f.algorithm, water_body: f.water_body, title: f.title, version: f.version,
    period: f.from || f.to ? { from: f.from, to: f.to } : null, inputs: f.inputs, param_set: f.param_set,
    param_version: f.param_version, calc_params: Object.fromEntries(Object.entries(f.calc_params).filter(([, v]) => v !== null && v !== undefined && !(Array.isArray(v) && !v.length))),
    comment: f.comment, run }
  try {
    const r = props.calc ? await api.put('algo-admin', `/calcs/${props.calc.id}`, body) : await api.post('algo-admin', '/calcs', body)
    emit('saved', r); emit('update:modelValue', false)
  } catch (e) { err.value = e } finally { busy.value = false }
}
</script>
<style scoped>
.two { display: grid; grid-template-columns: 1fr 1fr; gap: 0 16px; }
.inputs { width: 100%; display: flex; flex-direction: column; gap: 6px; }
.inp { gap: 10px; flex-wrap: wrap; }
.dep { width: 260px; font-weight: 500; }
@media (max-width: 640px) { .two { grid-template-columns: 1fr; } .dep { width: 100%; } }
</style>
