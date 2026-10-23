<template>
  <div class="page">
    <div class="page-head">
      <div><h1>{{ $t('dict.title') }}</h1><div class="sub">Конструктор справочников: сущности, поля и структуры таблиц, по которым строятся шаблоны Excel и проверяются загрузки.</div></div>
      <el-button v-if="auth.can('dict.edit')" type="primary" @click="openNew"><el-icon><Plus /></el-icon>&nbsp;{{ $t('dict.new_entity') }}</el-button>
    </div>
    <StateBlock :loading="loading" :error="error">
      <div class="card">
        <h2 style="margin-top:0">{{ $t('dict.entities') }}</h2>
        <el-table :data="grouped" @row-click="(r) => $router.push('/design/dictionaries/entities/' + r.code)" style="cursor:pointer">
          <el-table-column :label="$t('dict.group')" width="150"><template #default="{ row }"><span class="muted">{{ $t('dict.group_' + row.group) }}</span></template></el-table-column>
          <el-table-column :label="$t('common.name')" min-width="200"><template #default="{ row }"><b>{{ tr(row, 'title') }}</b> <el-tag v-if="row.system" size="small" type="info">{{ $t('dict.system') }}</el-tag><div class="muted small">{{ row.description }}</div></template></el-table-column>
          <el-table-column prop="code" :label="$t('common.code')" width="160" />
          <el-table-column :label="$t('dict.fields')" width="90" align="right"><template #default="{ row }">{{ row.fields.length }}</template></el-table-column>
          <el-table-column prop="records_count" :label="$t('dict.records')" width="90" align="right" />
          <el-table-column :label="$t('common.version')" width="90" align="right"><template #default="{ row }">v{{ row.current_version }}</template></el-table-column>
        </el-table>
      </div>
      <div class="card">
        <h2 style="margin-top:0">{{ $t('dict.dtypes') }}</h2>
        <el-table :data="dtypes" @row-click="(r) => $router.push('/design/dictionaries/types/' + r.code)" style="cursor:pointer">
          <el-table-column :label="$t('common.name')" min-width="220"><template #default="{ row }"><b>{{ tr(row, 'title') }}</b><div class="muted small">{{ row.description }}</div></template></el-table-column>
          <el-table-column prop="code" :label="$t('common.code')" width="170" />
          <el-table-column :label="$t('dict.columns')" width="90" align="right"><template #default="{ row }">{{ row.columns.length }}</template></el-table-column>
          <el-table-column :label="$t('dict.species_columns')" width="130" align="center"><template #default="{ row }">{{ row.species_columns?.enabled ? $t('common.yes') : $t('common.no') }}</template></el-table-column>
          <el-table-column :label="$t('common.version')" width="90" align="right"><template #default="{ row }">v{{ row.current_version }}</template></el-table-column>
        </el-table>
        <el-button v-if="auth.can('dict.edit')" style="margin-top:10px" @click="$router.push('/design/dictionaries/types/_new')"><el-icon><Plus /></el-icon>&nbsp;Новый тип набора данных</el-button>
      </div>
    </StateBlock>
    <el-dialog v-model="dlg" :title="$t('dict.new_entity')" width="1100px">
      <el-form label-width="160px">
        <el-form-item :label="$t('common.code')"><el-input v-model="f.code" placeholder="stations" /></el-form-item>
        <el-form-item :label="$t('dict.title_ru')"><el-input v-model="f.title_ru" /></el-form-item>
        <el-form-item :label="$t('dict.title_kk')"><el-input v-model="f.title_kk" /></el-form-item>
        <el-form-item :label="$t('common.description')"><el-input v-model="f.description" /></el-form-item>
      </el-form>
      <FieldsEditor v-model="f.fields" />
      <StateBlock :error="err" />
      <template #footer><el-button @click="dlg = false">{{ $t('common.cancel') }}</el-button><el-button type="primary" @click="create">{{ $t('common.create') }}</el-button></template>
    </el-dialog>
  </div>
</template>
<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { tr } from '../i18n'
import { useAuth } from '../store/auth'
import StateBlock from '../components/StateBlock.vue'
import FieldsEditor from '../components/FieldsEditor.vue'
const auth = useAuth()
const router = useRouter()
const entities = ref([])
const dtypes = ref([])
// разделы справочников (порядок показа)
const GROUPS = {
  water: ['water_bodies', 'water_body_types', 'water_body_statuses', 'water_body_origins', 'fishery_kinds', 'regions', 'fishing_places'],
  fish: ['species', 'fish_families', 'fish_sexes', 'forage_bases'],
  catch: ['gears', 'gear_categories', 'catch_types'],
}
const grouped = computed(() => {
  const order = Object.values(GROUPS).flat()
  const group = (c) => Object.keys(GROUPS).find((g) => GROUPS[g].includes(c)) || 'other'
  return entities.value.map((e) => ({ ...e, group: group(e.code) }))
    .sort((a, b) => ((order.indexOf(a.code) + 1) || 999) - ((order.indexOf(b.code) + 1) || 999) || tr(a, 'title').localeCompare(tr(b, 'title')))
})
const loading = ref(true)
const error = ref(null)
const dlg = ref(false)
const err = ref(null)
const f = reactive({ code: '', title_ru: '', title_kk: '', description: '', fields: [] })
function openNew() { Object.assign(f, { code: '', title_ru: '', title_kk: '', description: '', fields: [{ code: 'name', title_ru: 'Название', title_kk: 'Атауы', type: 'string', required: true }] }); err.value = null; dlg.value = true }
async function create() {
  err.value = null
  try { const e = await api.post('data-model', '/entities', f); dlg.value = false; router.push('/design/dictionaries/entities/' + e.code) } catch (e) { err.value = e }
}
onMounted(async () => {
  try { [entities.value, dtypes.value] = await Promise.all([api.get('data-model', '/entities'), api.get('data-model', '/dataset-types')]) }
  catch (e) { error.value = e } finally { loading.value = false }
})
</script>
