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
        <template v-if="schema && species.length">
          <el-tabs v-model="sp">
            <el-tab-pane v-for="s in species" :key="s" :name="s" :label="spNames[s] || s" />
          </el-tabs>
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
        <div v-else-if="!data.profile" class="state">{{ $t('profiles.none') }}. {{ $t('profiles.copy_from') }}.</div>
        <h3>{{ $t('common.history') }}</h3>
        <el-table :data="data.versions" size="small"><el-table-column prop="n" label="v" width="60" /><el-table-column :label="$t('common.date')" width="200"><template #default="{ row }">{{ new Date(row.created_at).toLocaleString('ru-RU') }}</template></el-table-column><el-table-column prop="comment" :label="$t('common.comment')" /></el-table>
      </div>
    </StateBlock>
  </div>
</template>
<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api'
import { tr } from '../i18n'
import { useAuth } from '../store/auth'
import StateBlock from '../components/StateBlock.vue'
import WaterBodySelect from '../components/WaterBodySelect.vue'
const auth = useAuth()
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
    sp.value = species.value[0]
    open.value = Object.keys(groups.value).slice(0, 1)
  } catch (e) { error.value = e } finally { loading.value = false }
}
async function save() {
  busy.value = true; saveErr.value = null
  try {
    data.value = await api.put('algo-admin', `/profiles/${algo.value}/${wb.value}`, { values: { species_profiles: values.value }, comment: comment.value })
    ElMessage.success('Сохранена новая версия профиля'); comment.value = ''
  } catch (e) { saveErr.value = e } finally { busy.value = false }
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
.pgrid { display: grid; grid-template-columns: repeat(auto-fill, minmax(360px, 1fr)); gap: 8px 18px; }
.prow { display: flex; justify-content: space-between; align-items: center; gap: 10px; border-bottom: 1px dashed var(--fs-line-soft); padding: 4px 0; }
</style>
