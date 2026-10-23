<template>
  <div class="page">
    <StateBlock :loading="loading" :error="error">
      <template v-if="ent">
        <div class="page-head">
          <div>
            <el-button text @click="$router.push('/design/dictionaries')"><el-icon><ArrowLeft /></el-icon>&nbsp;{{ $t('dict.title') }}</el-button>
            <h1>{{ tr(ent, 'title') }}</h1><div class="sub">{{ ent.description }} · {{ $t('common.version') }} v{{ ent.current_version }}</div>
          </div>
          <el-button v-if="auth.can('dict.edit')" type="primary" @click="openRec(null)"><el-icon><Plus /></el-icon>&nbsp;{{ $t('dict.record_new') }}</el-button>
        </div>
        <el-tabs v-model="tab">
          <el-tab-pane :label="$t('dict.records') + ` (${records.length})`" name="records">
            <div class="card">
              <div class="row" style="gap:8px; margin-bottom:8px; flex-wrap:wrap">
                <el-input v-model="q" :placeholder="$t('common.search')" clearable style="width:300px" prefix-icon="Search" />
                <WaterBodySelect v-if="hasWb" v-model="fWb" clearable />
                <el-button v-if="code === 'fishing_places' && auth.can('dict.edit')" :loading="collecting" @click="collectPlaces">
                  <el-icon><Download /></el-icon>&nbsp;{{ $t('dict.places_collect') }}</el-button>
              </div>
              <el-table :data="shown" size="small" max-height="640" @row-dblclick="openRec">
                <el-table-column v-for="f in listFields" :key="f.code" :label="tr(f, 'title')" :min-width="f.code === 'name_ru' ? 200 : 120">
                  <template #default="{ row }">{{ cell(row.values[f.code], f) }}</template>
                </el-table-column>
                <el-table-column :label="$t('common.version')" width="80" align="right"><template #default="{ row }">v{{ row.current_version }}</template></el-table-column>
                <el-table-column width="150" align="right">
                  <template #default="{ row }">
                    <el-button size="small" @click="openRec(row)">{{ auth.can('dict.edit') ? $t('common.edit') : $t('common.open') }}</el-button>
                    <el-button v-if="auth.can('dict.edit')" size="small" text type="danger" @click="del(row)"><el-icon><Delete /></el-icon></el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </el-tab-pane>
          <el-tab-pane :label="$t('dict.fields')" name="fields">
            <div class="card">
              <FieldsEditor v-model="schema.fields" />
              <div class="row" style="margin-top:12px">
                <el-input v-model="schema.comment" :placeholder="$t('common.comment')" style="width:360px" />
                <el-button type="primary" :disabled="!auth.can('dict.edit')" @click="saveSchema">{{ $t('common.save') }}</el-button>
              </div>
              <StateBlock :error="schemaErr" />
            </div>
          </el-tab-pane>
          <el-tab-pane :label="$t('common.history')" name="history">
            <div class="card">
              <el-table :data="versions" size="small"><el-table-column prop="n" label="v" width="60" /><el-table-column :label="$t('common.date')"><template #default="{ row }">{{ new Date(row.created_at).toLocaleString('ru-RU') }}</template></el-table-column><el-table-column prop="comment" :label="$t('common.comment')" /></el-table>
            </div>
          </el-tab-pane>
        </el-tabs>
      </template>
    </StateBlock>
    <el-dialog v-model="dlg" :title="cur ? $t('dict.record_edit') : $t('dict.record_new')" width="900px" top="4vh">
      <RecordForm v-if="dlg" :fields="ent.fields" :v="form" :errs="recErrs" :is-new="!cur" :locked="ent.system" />
      <div v-if="cur" class="small muted">История записи:
        <span v-for="h in recHistory" :key="h.n">v{{ h.n }} ({{ new Date(h.created_at).toLocaleDateString('ru-RU') }}{{ h.comment ? ', ' + h.comment : '' }}) </span>
      </div>
      <StateBlock :error="recErr" />
      <template #footer>
        <el-button @click="dlg = false">{{ $t('common.cancel') }}</el-button>
        <el-button v-if="auth.can('dict.edit')" type="primary" :loading="busy" @click="saveRec">{{ $t('common.save') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>
<script setup>
import { dictName, dictNames, loadDict } from '../dicts'
import WaterBodySelect from '../components/WaterBodySelect.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../api'
import { useI18n } from 'vue-i18n'
import { tr } from '../i18n'
import { useAuth } from '../store/auth'
import StateBlock from '../components/StateBlock.vue'
import FieldsEditor from '../components/FieldsEditor.vue'
import RecordForm from '../components/RecordForm.vue'
const auth = useAuth()
const { t } = useI18n()
const route = useRoute()
const code = route.params.code
const ent = ref(null)
const records = ref([])
const versions = ref([])
const loading = ref(true)
const error = ref(null)
const tab = ref('records')
const q = ref('')
const schema = reactive({ fields: [], comment: '' })
const schemaErr = ref(null)
const dlg = ref(false)
const cur = ref(null)
const form = reactive({})
const recErrs = ref({})
const recErr = ref(null)
const recHistory = ref([])
const busy = ref(false)
const listFields = computed(() => (ent.value?.fields || []).filter((f) => f.code === 'aliases' || !['geo_shape', 'text'].includes(f.type)).slice(0, 8))
const hasWb = computed(() => (ent.value?.fields || []).some((f) => f.code === 'water_body' && f.ref_entity === 'water_bodies'))
const fWb = ref(null)
const shown = computed(() => records.value.filter((r) => (!fWb.value || r.values.water_body === fWb.value) &&
  (!q.value || JSON.stringify(r.values).toLowerCase().includes(q.value.toLowerCase()))))
const collecting = ref(false)
async function collectPlaces() {
  collecting.value = true
  try {
    const r = await api.post('data-admin', '/fishing-places/collect' + (fWb.value ? `?water_body=${fWb.value}` : ''))
    ElMessage.success(t('dict.places_collected', { n: r.created }))
    await load()
  } catch (e) { ElMessage.error(e.message || String(e)) } finally { collecting.value = false }
}
function cell(v, f) {
  if (v === null || v === undefined) return '—'
  if (f.type === 'boolean') return v ? 'да' : 'нет'
  if (f.type === 'geo_point') return `${v[0]}, ${v[1]}`
  if (f.type === 'enum') { const e = (f.enum || []).find((x) => x.value === v); return e ? tr(e, 'title') : v }
  if (f.type === 'ref_list' && Array.isArray(v)) return dictNames(f.ref_entity, v)
  if (f.type === 'ref') return dictName(f.ref_entity, v)
  if (f.type === 'geo_shape') return v.type
  if (f.code === 'aliases') return String(v).split('\n').filter(Boolean).join('; ') || '—'
  return v
}
async function load() {
  loading.value = true
  try {
    ;[ent.value, records.value, versions.value] = await Promise.all([api.get('data-model', `/entities/${code}`),
      api.get('data-model', `/entities/${code}/records`), api.get('data-model', `/entities/${code}/versions`)])
    schema.fields = JSON.parse(JSON.stringify(ent.value.fields))
    await Promise.all([...new Set(ent.value.fields.filter((f) => ['ref', 'ref_list'].includes(f.type)).map((f) => f.ref_entity))]
      .map((e) => loadDict(e, true)))
  } catch (e) { error.value = e } finally { loading.value = false }
}
async function openRec(r) {
  cur.value = r; recErrs.value = {}; recErr.value = null
  for (const k of Object.keys(form)) delete form[k]
  for (const f of ent.value.fields) form[f.code] = r ? JSON.parse(JSON.stringify(r.values[f.code] ?? null)) : (f.type === 'boolean' ? false : null)
  recHistory.value = r ? await api.get('data-model', `/entities/${code}/records/${r.id}/versions`) : []
  dlg.value = true
}
async function saveRec() {
  busy.value = true; recErrs.value = {}; recErr.value = null
  try {
    if (cur.value) await api.put('data-model', `/entities/${code}/records/${cur.value.id}`, { values: form })
    else await api.post('data-model', `/entities/${code}/records`, { values: form })
    dlg.value = false; ElMessage.success('Сохранено'); await load()
  } catch (e) {
    if (Array.isArray(e.details)) { for (const d of e.details) recErrs.value[d.field] = d.message }
    recErr.value = e
  } finally { busy.value = false }
}
async function del(r) {
  await ElMessageBox.confirm('Удалить запись? История сохраняется.', '', { type: 'warning' })
  await api.del('data-model', `/entities/${code}/records/${r.id}`); await load()
}
async function saveSchema() {
  schemaErr.value = null
  try {
    await api.put('data-model', `/entities/${code}`, { code, title_ru: ent.value.title_ru, title_kk: ent.value.title_kk,
      description: ent.value.description, display_field: ent.value.display_field, fields: schema.fields, comment: schema.comment })
    ElMessage.success('Сохранена новая версия справочника'); schema.comment = ''; await load()
  } catch (e) { schemaErr.value = e }
}
onMounted(load)
</script>
