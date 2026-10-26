<template>
  <div class="page">
    <div class="page-head">
      <div><h1>{{ $t('params.title') }}</h1><div class="sub">{{ $t('params.sub') }}</div></div>
      <div class="row">
        <el-select v-model="algo" filterable style="width:320px" data-test="params-algorithm" @change="pickAlgo">
          <el-option v-for="a in algos" :key="a.code" :label="algoLabel(a, tr)" :value="a.code" />
        </el-select>
      </div>
    </div>
    <div class="ps">
      <div class="card list">
        <div class="muted small" style="margin-bottom:6px">{{ $t('params.sets') }}</div>
        <div v-for="s in sets" :key="s.id" class="item" :class="{ sel: s.id === sid }" :data-test="'set-' + s.id" @click="open(s.id)">
          <div><b>{{ s.name }}</b> <el-tag v-if="s.is_default" size="small" type="success">★ {{ $t('params.default') }}</el-tag></div>
          <div class="muted small">v{{ s.current_version }} · {{ $t('params.used', { n: s.used_by }) }}</div>
        </div>
        <div v-if="auth.can('profile.edit') && cur" class="row" style="margin-top:10px">
          <el-button size="small" data-test="set-base-on" @click="baseOn"><el-icon><CopyDocument /></el-icon>&nbsp;{{ $t('params.base_on') }}</el-button>
        </div>
      </div>
      <StateBlock :loading="loading" :error="error">
        <div v-if="cur" class="card editor">
          <div class="row" style="justify-content:space-between; align-items:flex-start; gap:12px; flex-wrap:wrap">
            <div style="flex:1; min-width:260px">
              <el-input v-if="editable" v-model="name" :placeholder="$t('params.name')" style="max-width:420px; margin-bottom:6px" />
              <h2 v-else style="margin:0 0 4px">{{ cur.name }}</h2>
              <el-input v-if="editable" v-model="description" type="textarea" :rows="2" :placeholder="$t('params.description')" />
              <div v-else class="muted small">{{ cur.description }}</div>
            </div>
            <div class="row">
              <span class="muted small">{{ $t('params.version') }}</span>
              <el-select v-model="version" style="width:260px" @change="loadVersion">
                <el-option v-for="v in cur.versions" :key="v.n" :value="v.n" :label="'v' + v.n + ' · ' + dt(v.created_at) + (v.n === cur.current_version ? ' · ' + $t('params.current') : '')" />
              </el-select>
              <el-button v-if="auth.can('profile.edit') && !cur.system && !cur.used_by" text type="danger" @click="removeSet"><el-icon><Delete /></el-icon></el-button>
            </div>
          </div>
          <el-alert v-if="cur.system" type="info" :closable="false" :title="$t('params.readonly_system')" style="margin:10px 0" />
          <el-alert v-else-if="version !== cur.current_version" type="info" :closable="false" :title="$t('params.readonly_old')" style="margin:10px 0" />
          <div v-if="versionComment" class="muted small" style="margin:6px 0">{{ versionComment }}</div>

          <!-- пояснения к параметрам простыми словами (справка, param_notes.json) -->
          <div class="row notes-bar">
            <el-switch v-model="showNotes" size="small" :active-text="$t('params.show_notes')" data-test="params-notes" @change="saveNotesPref" />
            <div class="grow" />
            <router-link v-if="METHOD[algo]" :to="helpPath(METHOD[algo])" class="small"><el-icon><QuestionFilled /></el-icon> {{ $t('params.notes_help') }}</router-link>
          </div>
          <!-- обычные параметры алгоритма -->
          <div v-if="plain.length" class="pgrid" :class="{ wide: showNotes }" style="margin-top:10px">
            <div v-for="p in plain" :key="p.code" class="prow" :class="{ changed: differs(p.code) }">
              <div class="small">{{ tr(p, 'title') || p.code }}
                <div class="mono muted small">{{ p.code }}<span v-if="differs(p.code)" class="chg"> · {{ $t('params.changed') }} ({{ show(cur.defaults[p.code]) }})</span></div>
                <div v-if="showNotes && notes[p.code]" class="pnote" data-test="param-note">{{ notes[p.code] }}</div>
              </div>
              <ParamField :p="p" v-model="values[p.code]" :species="speciesList" :disabled="!editable" />
            </div>
          </div>

          <!-- модель (алгоритм i): значения по видам -->
          <template v-if="schema">
            <div v-if="editable" class="row" style="margin:12px 0 6px">
              <el-select v-model="newSp" :placeholder="$t('params.add_species')" filterable style="width:240px" data-test="add-species">
                <el-option v-for="c in addable" :key="c" :label="spNames[c] || c" :value="c" />
              </el-select>
              <el-button :disabled="!newSp" :loading="adding" @click="addSpecies">{{ $t('common.add') }}</el-button>
            </div>
            <div v-if="showNotes" class="pnote" style="margin:4px 0 8px">{{ $t('params.profile_note') }} <router-link :to="helpPath('method-priors')">{{ $t('params.profile_link') }}</router-link></div>
            <el-tabs v-if="profSpecies.length" v-model="sp">
              <el-tab-pane v-for="s in profSpecies" :key="s" :name="s" :label="spNames[s] || s" />
            </el-tabs>
            <div v-if="sp && editable" class="row" style="justify-content:flex-end; margin-bottom:6px">
              <el-button size="small" text type="danger" data-test="remove-species" @click="removeSpecies">{{ $t('params.remove_species') }}</el-button>
            </div>
            <el-collapse v-if="sp" v-model="openGroups">
              <el-collapse-item v-for="(rows, g) in groups" :key="g" :name="g" :title="g">
                <div class="pgrid">
                  <div v-for="r in rows" :key="r.key" class="prow">
                    <div class="small">{{ r.label }}<div class="mono muted small">{{ r.key }}<span v-if="r.value_kind" class="vk">{{ kindName(r.value_kind) }}</span></div></div>
                    <el-select v-if="r.type === 'select'" v-model="prof[sp][r.key]" size="small" style="width:260px" :disabled="!editable">
                      <el-option v-for="o in r.options" :key="o.value" :label="o.label" :value="o.value" />
                    </el-select>
                    <el-switch v-else-if="r.type === 'bool'" v-model="prof[sp][r.key]" :disabled="!editable" />
                    <el-input v-else-if="r.type === 'text'" v-model="prof[sp][r.key]" size="small" style="width:100%; max-width:520px"
                              :disabled="!editable" :placeholder="'2015: 150000; 2016: 200000'" :data-test="'prof-' + r.key" />
                    <el-input-number v-else v-model="prof[sp][r.key]" size="small" :controls="false" :step="r.type === 'int' ? 1 : 0.01"
                                     :precision="r.type === 'int' ? 0 : undefined" style="width:140px" :disabled="!editable" />
                  </div>
                </div>
              </el-collapse-item>
            </el-collapse>
          </template>

          <div v-if="editable" class="row" style="margin-top:14px">
            <el-input v-model="comment" :placeholder="$t('params.comment_ph')" style="width:420px; max-width:100%" />
            <el-button type="primary" :loading="busy" data-test="set-save" @click="save">{{ $t('params.save') }}</el-button>
          </div>
          <StateBlock :error="saveErr" />

          <h3>{{ $t('params.usage') }}</h3>
          <div v-if="cur.usage?.length"><div v-for="u in cur.usage" :key="u.id"><router-link :to="'/calc/calculations/' + u.id">{{ u.title }}</router-link></div></div>
          <div v-else class="muted small">{{ $t('params.none_used') }}</div>
        </div>
      </StateBlock>
    </div>
  </div>
</template>
<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { api } from '../api'
import { tr } from '../i18n'
import { useAuth } from '../store/auth'
import { METHOD, algoLabel, dt, loadCatalog } from '../calcs'
import { helpPath } from '../cabinets'
import StateBlock from '../components/StateBlock.vue'
import ParamField from '../components/ParamField.vue'
const auth = useAuth()
const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const algos = ref([])
const algo = ref(null)
const sets = ref([])
const sid = ref(null)
const cur = ref(null)
const version = ref(null)
const values = ref({})
const prof = ref({})
const name = ref('')
const description = ref('')
const comment = ref('')
const sp = ref(null)
const newSp = ref(null)
const adding = ref(false)
const openGroups = ref([])
const busy = ref(false)
const loading = ref(false)
const error = ref(null)
const saveErr = ref(null)
const spNames = ref({})
const speciesList = ref([])
const kinds = ref({})
const notes = ref({})
const NOTES_KEY = 'fishstock.params.notes'
function readPref() { try { return localStorage.getItem(NOTES_KEY) !== '0' } catch { return true } }
const showNotes = ref(readPref())
function saveNotesPref(v) { try { localStorage.setItem(NOTES_KEY, v ? '1' : '0') } catch { /* нет хранилища — только на этот раз */ } }
async function loadNotes() {
  try { notes.value = algo.value ? await api.get('help', `/param-notes/${algo.value}`, { lang: locale.value }) : {} } catch { notes.value = {} }
}
const editable = computed(() => auth.can('profile.edit') && cur.value && !cur.value.system && version.value === cur.value.current_version)
const plain = computed(() => (cur.value?.parameters || []).filter((p) => p.type !== 'profile'))
const schema = computed(() => cur.value?.schema)
const groups = computed(() => { const g = {}; for (const r of schema.value || []) (g[r.group] ||= []).push(r); return g })
const profSpecies = computed(() => Object.keys(prof.value))
const addable = computed(() => Object.keys(spNames.value).filter((c) => !(c in prof.value)))
const versionComment = computed(() => cur.value?.versions?.find((v) => v.n === version.value)?.comment || '')
const kindName = (k) => (kinds.value[k] ? tr(kinds.value[k], 'name') : k)
const show = (v) => (v === null || v === undefined ? '—' : typeof v === 'object' ? JSON.stringify(v) : String(v))
const differs = (code) => cur.value && !cur.value.is_default && JSON.stringify(values.value[code] ?? null) !== JSON.stringify(cur.value.defaults?.[code] ?? null)
async function pickAlgo() {
  loadNotes()
  sets.value = await api.get('algo-admin', '/param-sets', { algorithm: algo.value })
  const want = sets.value.find((s) => s.id === sid.value) || sets.value.find((s) => s.is_default) || sets.value[0]
  if (want) await open(want.id)
}
function fill(d) {
  values.value = JSON.parse(JSON.stringify(d.values || {}))
  prof.value = values.value.species_profiles ? values.value.species_profiles : {}
  if (!profSpecies.value.includes(sp.value)) sp.value = profSpecies.value[0] || null
  if (!openGroups.value.length) openGroups.value = Object.keys(groups.value).slice(0, 1)
}
async function open(id) {
  loading.value = true; error.value = null; saveErr.value = null
  try {
    const d = await api.get('algo-admin', `/param-sets/${id}`)
    cur.value = d; sid.value = id; version.value = d.current_version
    name.value = d.name; description.value = d.description || ''; comment.value = ''
    fill(d)
    if (route.params.id !== id) router.replace({ path: '/calc/params/' + id })
  } catch (e) { error.value = e } finally { loading.value = false }
}
async function loadVersion() {
  const d = await api.get('algo-admin', `/param-sets/${sid.value}`, { version: version.value })
  fill(d)
}
async function save() {
  busy.value = true; saveErr.value = null
  try {
    const body = { name: name.value, description: description.value, comment: comment.value,
      values: schema.value ? { ...values.value, species_profiles: prof.value } : values.value }
    const d = await api.put('algo-admin', `/param-sets/${sid.value}`, body)
    cur.value = d; version.value = d.current_version; fill(d); comment.value = ''
    ElMessage.success(t('params.saved'))
    sets.value = await api.get('algo-admin', '/param-sets', { algorithm: algo.value })
  } catch (e) { saveErr.value = e } finally { busy.value = false }
}
async function baseOn() {
  let v
  try { v = (await ElMessageBox.prompt(t('params.new_name'), t('params.base_on'), { inputValue: cur.value.name + ' (копия)' })).value } catch { return }
  try {
    const d = await api.post('algo-admin', '/param-sets', { name: v, base: sid.value })
    sets.value = await api.get('algo-admin', '/param-sets', { algorithm: algo.value })
    await open(d.id)
  } catch (e) { ElMessage.error([e.message, ...(e.details || [])].join(': ')) }
}
async function removeSet() {
  try { await ElMessageBox.confirm(t('params.delete_confirm', { n: cur.value.name }), '', { type: 'warning' }) } catch { return }
  try { await api.del('algo-admin', `/param-sets/${sid.value}`); sid.value = null; await pickAlgo() } catch (e) { ElMessage.error(e.message) }
}
async function addSpecies() {
  adding.value = true
  try {
    const d = await api.get('algo-admin', `/param-sets/species-defaults/${newSp.value}`)
    prof.value = { ...prof.value, [newSp.value]: d.values }
    sp.value = newSp.value; newSp.value = null
  } catch (e) { saveErr.value = e } finally { adding.value = false }
}
function removeSpecies() {
  const v = { ...prof.value }; delete v[sp.value]; prof.value = v
  sp.value = Object.keys(v)[0] || null
}
onMounted(async () => {
  const [cat, s] = await Promise.all([loadCatalog(), api.get('data-model', '/entities/species/records')])
  algos.value = cat.list.filter((a) => !a.planned && a.latest)
  speciesList.value = s.map((r) => r.values)
  spNames.value = Object.fromEntries(s.map((r) => [r.values.code, r.values.name_ru]))
  api.get('algo-admin', '/classifiers').then((c) => { kinds.value = Object.fromEntries((c.param_values || []).map((x) => [x.code, x])) }).catch(() => {})
  if (route.params.id) {
    try { const d = await api.get('algo-admin', `/param-sets/${route.params.id}`); algo.value = d.algorithm; sid.value = d.id } catch (e) { /* набор удалён */ }
  }
  algo.value = algo.value || route.query.algorithm || 'bayes_cohort'
  await pickAlgo()
})
</script>
<style scoped>
.ps { display: grid; grid-template-columns: 300px 1fr; gap: 14px; align-items: start; }
.list .item { padding: 8px 10px; border-radius: 8px; cursor: pointer; border: 1px solid transparent; }
.list .item:hover { background: var(--fs-hover); }
.list .item.sel { background: var(--fs-selected); border-color: var(--fs-line); }
.pgrid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(380px, 100%), 1fr)); gap: 8px 18px; }
.prow { display: flex; justify-content: space-between; align-items: center; gap: 10px; border-bottom: 1px dashed var(--fs-line-soft); padding: 4px 0; }
.prow > div:first-child { min-width: 150px; flex: 1; overflow-wrap: anywhere; }
.prow :deep(.pf .el-select) { width: 230px !important; }
.prow :deep(.pf .el-input-number) { width: 150px !important; }
.prow.changed > div:first-child { font-weight: 600; }
.chg { color: var(--fs-warning); }
.vk { margin-left: 8px; font-family: inherit; color: var(--fs-muted); }
@media (max-width: 900px) { .ps { grid-template-columns: 1fr; } }
.notes-bar { margin-top: 10px; gap: 10px; align-items: center; }
.pnote { margin-top: 4px; font-size: 12px; line-height: 1.45; color: var(--fs-muted); max-width: 640px; }
.pgrid.wide { grid-template-columns: 1fr; }
</style>
