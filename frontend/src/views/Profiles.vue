<template>
  <div class="page">
    <div class="page-head">
      <div><h1>{{ $t('profiles.title') }}</h1><div class="sub">{{ $t('profiles.hint') }}</div></div>
      <div class="row">
        <el-select v-model="algo" style="width:280px" @change="load">
          <el-option v-for="a in algos" :key="a.code" :label="tr(a, 'title')" :value="a.code" />
        </el-select>
        <WaterBodySelect v-model="wb" @update:model-value="load" />
      </div>
    </div>
    <StateBlock :loading="loading" :error="error">
      <div v-if="data" class="card">
        <div class="row" style="margin-bottom:10px">
          <el-tag v-if="data.profile" type="success">v{{ data.profile.current_version }} · {{ new Date(data.profile.updated_at).toLocaleString('ru-RU') }}</el-tag>
          <el-tag v-else type="warning">{{ $t('profiles.none') }}</el-tag>
          <div class="grow" />
          <template v-if="auth.can('profile.edit')">
            <el-select v-model="src" :placeholder="$t('profiles.copy_from')" style="width:220px">
              <el-option v-for="s in data.available_sources.filter((x) => x !== wb)" :key="s" :label="s" :value="s" />
            </el-select>
            <el-button :disabled="!src" @click="copyFrom">{{ $t('common.copy') }}</el-button>
          </template>
        </div>
        <div v-if="schema && auth.can('profile.edit') && algo === 'bayes_cohort'" class="row" style="margin-bottom:6px">
          <el-select v-model="newSp" :placeholder="$t('profiles.add_species')" filterable style="width:240px" data-test="add-species">
            <el-option-group v-if="addable.data.length" :label="$t('profiles.in_data')">
              <el-option v-for="c in addable.data" :key="c" :label="spNames[c] || c" :value="c" />
            </el-option-group>
            <el-option-group v-if="addable.other.length" :label="$t('profiles.other_species')">
              <el-option v-for="c in addable.other" :key="c" :label="spNames[c] || c" :value="c" />
            </el-option-group>
          </el-select>
          <el-button :disabled="!newSp" :loading="adding" @click="addSpecies">{{ $t('profiles.add') }}</el-button>
          <el-tag v-if="dirty" type="warning" size="small">{{ $t('profiles.unsaved') }}</el-tag>
        </div>
        <template v-if="schema && species.length">
          <el-tabs v-model="sp">
            <el-tab-pane v-for="s in species" :key="s" :name="s" :label="spNames[s] || s" />
          </el-tabs>
          <div class="row" style="margin-bottom:8px">
            <el-tag v-if="added[sp]" type="warning" size="small" class="wrap-tag">{{ $t(added[sp] === 'reference' ? 'profiles.new_reference' : 'profiles.new_general') }}</el-tag>
            <el-tag v-if="wbSpecies.length && !wbSpecies.includes(sp)" type="info" size="small">{{ $t('profiles.not_in_data') }}</el-tag>
            <div class="grow" />
            <el-button v-if="auth.can('profile.edit')" size="small" text type="danger" data-test="remove-species" @click="removeSpecies">{{ $t('profiles.remove_species') }}</el-button>
          </div>
          <el-collapse v-model="open">
            <el-collapse-item v-for="(rows, g) in groups" :key="g" :name="g" :title="g">
              <div class="pgrid">
                <div v-for="r in rows" :key="r.key" class="prow">
                  <div class="small">{{ r.label }} <el-tag v-if="r.category === 'run'" size="small" type="success">по умолчанию для запуска</el-tag><div class="mono muted small">{{ r.key }}<span v-if="r.value_kind" class="vk">{{ kindName(r.value_kind) }}</span></div></div>
                  <el-select v-if="r.type === 'select'" v-model="values[sp][r.key]" size="small" style="width:260px" :disabled="!auth.can('profile.edit')">
                    <el-option v-for="o in r.options" :key="o.value" :label="o.label" :value="o.value" />
                  </el-select>
                  <el-switch v-else-if="r.type === 'bool'" v-model="values[sp][r.key]" :disabled="!auth.can('profile.edit')" />
                  <el-input-number v-else v-model="values[sp][r.key]" size="small" :controls="false" :step="r.type === 'int' ? 1 : 0.01"
                                   :precision="r.type === 'int' ? 0 : undefined" style="width:140px" :disabled="!auth.can('profile.edit')" />
                </div>
              </div>
            </el-collapse-item>
          </el-collapse>
          <div v-if="auth.can('profile.edit')" class="row" style="margin-top:12px">
            <el-input v-model="comment" :placeholder="$t('common.comment')" style="width:400px" />
            <el-button type="primary" :loading="busy" @click="save">{{ $t('common.save') }}</el-button>
          </div>
          <StateBlock :error="saveErr" />
        </template>
        <div v-else-if="!data.profile" class="state">{{ $t('profiles.none') }}. {{ $t('profiles.start_hint') }}</div>
        <h3>{{ $t('common.history') }}</h3>
        <el-table :data="data.versions" size="small"><el-table-column prop="n" label="v" width="60" /><el-table-column :label="$t('common.date')" width="200"><template #default="{ row }">{{ new Date(row.created_at).toLocaleString('ru-RU') }}</template></el-table-column><el-table-column prop="comment" :label="$t('common.comment')" /></el-table>
      </div>
    </StateBlock>
  </div>
</template>
<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../api'
import { useI18n } from 'vue-i18n'
import { tr } from '../i18n'
import { useAuth } from '../store/auth'
import StateBlock from '../components/StateBlock.vue'
import WaterBodySelect from '../components/WaterBodySelect.vue'
const auth = useAuth()
const { t } = useI18n()
const algos = ref([])
const algo = ref('bayes_cohort')
const wb = ref('zhaysan')
const data = ref(null)
const values = ref({})
const sp = ref(null)
const open = ref([])
const src = ref(null)
const comment = ref('')
const busy = ref(false)
const loading = ref(true)
const error = ref(null)
const saveErr = ref(null)
const spNames = ref({})
const newSp = ref(null)
const adding = ref(false)
const added = ref({})          // виды, добавленные в этом сеансе: источник значений по умолчанию
const dirty = ref(false)
const wbSpecies = computed(() => data.value?.water_body_species || [])
const addable = computed(() => {
  const have = new Set(Object.keys(values.value))
  const inData = wbSpecies.value.filter((c) => !have.has(c))
  const other = Object.keys(spNames.value).filter((c) => !have.has(c) && !inData.includes(c))
  return { data: inData, other }
})
const schema = computed(() => data.value?.schema)
const species = computed(() => Object.keys(values.value))
const groups = computed(() => {
  const g = {}
  for (const r of schema.value || []) (g[r.group] ||= []).push(r)
  return g
})
async function load() {
  loading.value = true; error.value = null; saveErr.value = null
  try {
    data.value = await api.get('algo-admin', `/profiles/${algo.value}/${wb.value}`)
    values.value = JSON.parse(JSON.stringify(data.value.profile?.values?.species_profiles || {}))
    added.value = {}; dirty.value = false; newSp.value = null
    sp.value = species.value[0]
    open.value = Object.keys(groups.value).slice(0, 1)
  } catch (e) { error.value = e } finally { loading.value = false }
}
async function save() {
  busy.value = true; saveErr.value = null
  try {
    data.value = await api.put('algo-admin', `/profiles/${algo.value}/${wb.value}`, { values: { species_profiles: values.value }, comment: comment.value })
    ElMessage.success('Сохранена новая версия профиля'); comment.value = ''; added.value = {}; dirty.value = false
  } catch (e) { saveErr.value = e } finally { busy.value = false }
}
async function addSpecies() {
  adding.value = true; saveErr.value = null
  try {
    const d = await api.get('algo-admin', `/profiles/${algo.value}/species-defaults/${newSp.value}`)
    values.value = { ...values.value, [newSp.value]: d.values }
    added.value = { ...added.value, [newSp.value]: d.source }
    sp.value = newSp.value; newSp.value = null; dirty.value = true
    if (!open.value.length) open.value = Object.keys(groups.value).slice(0, 1)
  } catch (e) { saveErr.value = e } finally { adding.value = false }
}
async function removeSpecies() {
  const name = spNames.value[sp.value] || sp.value
  try { await ElMessageBox.confirm(t('profiles.remove_confirm', { name }), '', { type: 'warning' }) } catch { return }
  const v = { ...values.value }; delete v[sp.value]; values.value = v
  const a = { ...added.value }; delete a[sp.value]; added.value = a
  sp.value = Object.keys(v)[0] || null; dirty.value = true
}
async function copyFrom() { await api.post('algo-admin', `/profiles/${algo.value}/${wb.value}/copy-from/${src.value}`); await load() }
const kinds = ref({})
const kindName = (k) => (kinds.value[k] ? tr(kinds.value[k], 'name') : k)
api.get('algo-admin', '/classifiers').then((c) => { kinds.value = Object.fromEntries((c.param_values || []).map((x) => [x.code, x])) }).catch(() => {})
onMounted(async () => {
  const [cat, s] = await Promise.all([api.get('algo-admin', '/catalog'), api.get('data-model', '/entities/species/records')])
  algos.value = cat.filter((a) => (a.manifest?.parameters || []).some((p) => p.category === 'waterbody'))
  spNames.value = Object.fromEntries(s.map((r) => [r.values.code, r.values.name_ru]))
  await load()
})
</script>
<style scoped>
.vk { margin-left: 8px; font-family: inherit; color: var(--fs-muted); }
.pgrid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(360px, 100%), 1fr)); gap: 8px 18px; }
.prow > div:first-child { min-width: 0; overflow-wrap: anywhere; }
.wrap-tag { height: auto; white-space: normal; line-height: 1.4; padding: 2px 8px; }
.prow { display: flex; justify-content: space-between; align-items: center; gap: 10px; border-bottom: 1px dashed var(--fs-line-soft); padding: 4px 0; }
</style>
