<template>
  <div class="page">
    <StateBlock :loading="loading" :error="error">
      <div class="page-head">
        <div>
          <el-button text @click="$router.push('/dictionaries')"><el-icon><ArrowLeft /></el-icon>&nbsp;{{ $t('dict.title') }}</el-button>
          <h1>{{ isNew ? 'Новый тип набора данных' : f.title_ru }}</h1>
          <div class="sub">{{ $t('dict.dtypes') }}<template v-if="!isNew"> · v{{ cur?.current_version }}</template></div>
        </div>
        <el-button v-if="!isNew" @click="download('data-admin', `/templates/${f.code}.xlsx`)">{{ $t('data.template') }}</el-button>
      </div>
      <div class="card">
        <el-form label-width="200px">
          <el-form-item :label="$t('common.code')"><el-input v-model="f.code" :disabled="!isNew" style="width:260px" /></el-form-item>
          <el-form-item :label="$t('dict.title_ru')"><el-input v-model="f.title_ru" /></el-form-item>
          <el-form-item :label="$t('dict.title_kk')"><el-input v-model="f.title_kk" /></el-form-item>
          <el-form-item :label="$t('common.description')"><el-input v-model="f.description" type="textarea" :rows="2" /></el-form-item>
        </el-form>
        <h3>{{ $t('dict.columns') }}</h3>
        <FieldsEditor v-model="f.columns" :allow-unique="false" />
        <h3>{{ $t('dict.species_columns') }}</h3>
        <el-checkbox v-model="f.species_columns.enabled">{{ $t('dict.species_cols_enabled') }}</el-checkbox>
        <div v-if="f.species_columns.enabled" class="row" style="margin-top:8px">
          <el-select v-model="f.species_columns.value_type" style="width:150px"><el-option label="Целое число" value="integer" /><el-option label="Число" value="number" /></el-select>
          <el-input v-model="f.species_columns.unit" :placeholder="$t('common.unit')" style="width:120px" />
          <el-input-number v-model="f.species_columns.min" :controls="false" :placeholder="$t('dict.min')" style="width:110px" />
          <el-input v-model="f.species_columns.title_ru" placeholder="Подпись столбцов видов" style="width:300px" />
        </div>
        <el-form label-width="200px" style="margin-top:14px">
          <el-form-item :label="$t('dict.period_field')">
            <el-select v-model="f.period_field" clearable style="width:260px"><el-option v-for="c in f.columns" :key="c.code" :label="c.title_ru" :value="c.code" /></el-select>
          </el-form-item>
          <el-form-item :label="$t('dict.key_fields')">
            <el-select v-model="f.key_fields" multiple clearable style="width:400px"><el-option v-for="c in f.columns" :key="c.code" :label="c.title_ru" :value="c.code" /></el-select>
          </el-form-item>
          <el-form-item :label="$t('common.comment')"><el-input v-model="f.comment" style="width:400px" /></el-form-item>
        </el-form>
        <StateBlock :error="saveErr" />
        <el-button type="primary" :disabled="!auth.can('dict.edit')" @click="save">{{ $t('common.save') }}</el-button>
      </div>
      <div v-if="!isNew" class="card">
        <h3 style="margin-top:0">{{ $t('common.history') }}</h3>
        <el-table :data="versions" size="small"><el-table-column prop="n" label="v" width="60" /><el-table-column :label="$t('common.date')"><template #default="{ row }">{{ new Date(row.created_at).toLocaleString('ru-RU') }}</template></el-table-column><el-table-column prop="comment" :label="$t('common.comment')" /></el-table>
      </div>
    </StateBlock>
  </div>
</template>
<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api, download } from '../api'
import { useAuth } from '../store/auth'
import StateBlock from '../components/StateBlock.vue'
import FieldsEditor from '../components/FieldsEditor.vue'
const auth = useAuth()
const route = useRoute()
const router = useRouter()
const isNew = route.params.code === '_new'
const cur = ref(null)
const versions = ref([])
const loading = ref(!isNew)
const error = ref(null)
const saveErr = ref(null)
const f = reactive({ code: '', title_ru: '', title_kk: '', description: '', period_field: 'year', key_fields: [], rules: [],
  columns: [{ code: 'year', title_ru: 'Год', title_kk: 'Жыл', type: 'integer', required: true, min: 1900, max: 2100 }],
  species_columns: { enabled: false, value_type: 'number', unit: '', min: 0, title_ru: '' }, comment: '' })
async function load() {
  try {
    cur.value = await api.get('data-model', `/dataset-types/${route.params.code}`)
    versions.value = await api.get('data-model', `/dataset-types/${route.params.code}/versions`)
    Object.assign(f, JSON.parse(JSON.stringify(cur.value)), { comment: '' })
    f.species_columns = { enabled: false, value_type: 'number', unit: '', min: 0, ...(cur.value.species_columns || {}) }
    f.key_fields = f.key_fields || []
  } catch (e) { error.value = e } finally { loading.value = false }
}
async function save() {
  saveErr.value = null
  const body = { code: f.code, title_ru: f.title_ru, title_kk: f.title_kk, description: f.description, period_field: f.period_field || null,
    columns: f.columns, species_columns: f.species_columns, key_fields: f.key_fields, rules: f.rules || [], comment: f.comment }
  try {
    if (isNew) { await api.post('data-model', '/dataset-types', body); router.replace('/dictionaries/types/' + f.code) }
    else { await api.put('data-model', `/dataset-types/${f.code}`, body); ElMessage.success('Сохранена новая версия'); await load() }
  } catch (e) { saveErr.value = e }
}
onMounted(() => { if (!isNew) load() })
</script>
