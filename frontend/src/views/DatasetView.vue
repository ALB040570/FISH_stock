<template>
  <div class="page">
    <StateBlock :loading="loading" :error="error">
      <template v-if="ds">
        <div class="page-head">
          <div>
            <el-button text @click="$router.push({ path: '/input/datasets', query: { wb: ds.water_body } })"><el-icon><ArrowLeft /></el-icon>&nbsp;{{ $t('common.back') }}</el-button>
            <h1>{{ ds.title }}</h1>
            <div class="sub">{{ $t('common.version') }} {{ version }} {{ version !== ds.current_version ? '(не текущая)' : '' }} · {{ vinfo?.comment }} · {{ vinfo ? new Date(vinfo.created_at).toLocaleString('ru-RU') : '' }}</div>
          </div>
          <div class="row">
            <el-select v-model="version" style="width:220px" @change="loadData">
              <el-option v-for="v in versions" :key="v.n" :label="`v${v.n} · ${new Date(v.created_at).toLocaleDateString('ru-RU')} · ${v.comment || ''}`" :value="v.n" />
            </el-select>
            <el-button @click="download('data-admin', `/datasets/${ds.id}/export.xlsx`, { version })">{{ $t('common.export_excel') }}</el-button>
            <el-button v-if="vinfo?.origin?.startsWith('upload')" @click="download('data-admin', `/datasets/${ds.id}/versions/${version}/source`)">{{ $t('data.source_file') }}</el-button>
            <el-button @click="diffOpen = true">{{ $t('data.diff') }}</el-button>
            <template v-if="auth.can('data.edit')">
              <el-button v-if="version !== ds.current_version" @click="restore">{{ $t('common.restore') }}</el-button>
              <el-button v-else-if="!editing" type="primary" @click="startEdit"><el-icon><Edit /></el-icon>&nbsp;{{ $t('data.edit') }}</el-button>
            </template>
          </div>
        </div>
        <div class="card">
          <div v-if="editing" class="row" style="margin-bottom:10px">
            <el-button size="small" @click="addRow"><el-icon><Plus /></el-icon>&nbsp;{{ $t('data.add_row') }}</el-button>
            <el-input v-model="comment" size="small" :placeholder="$t('common.comment')" style="width:320px" />
            <div class="grow" />
            <el-button size="small" @click="cancelEdit">{{ $t('common.cancel') }}</el-button>
            <el-button size="small" type="primary" :loading="busy" @click="save">{{ $t('data.save_version') }}</el-button>
          </div>
          <el-alert v-if="saveErrors.length" type="error" :closable="false" :title="$t('data.report_err')" style="margin-bottom:8px">
            <div v-for="(e, i) in saveErrors.slice(0, 12)" :key="i" class="small">{{ $t('data.row') }} {{ e.row }}: {{ e.message }}</div>
          </el-alert>
          <el-table :data="pageRows" size="small" border max-height="620" :row-class-name="rowClass">
            <el-table-column type="index" :index="(i) => (page - 1) * size + i + 1" width="56" fixed />
            <el-table-column v-for="c in cols" :key="c.code" :label="c.title + (c.unit && !String(c.title).includes(c.unit) ? ', ' + c.unit : '')" :min-width="c.species ? 80 : 120"
                             :align="c.num ? 'right' : 'left'">
              <template #default="{ row }">
                <el-input v-if="editing" v-model="row[c.code]" size="small" :class="{ num: c.num }" />
                <span v-else :class="{ miss: row[c.code] === null || row[c.code] === undefined }">{{ show(row[c.code], c) }}</span>
              </template>
            </el-table-column>
            <el-table-column v-if="editing" width="50" fixed="right">
              <template #default="{ $index }"><el-button text type="danger" size="small" @click="delRow($index)"><el-icon><Delete /></el-icon></el-button></template>
            </el-table-column>
          </el-table>
          <el-pagination v-model:current-page="page" :page-size="size" :total="rows.length" layout="total, prev, pager, next" style="margin-top:8px" />
          <div class="muted small">{{ $t('data.missing_hint') }}</div>
        </div>
      </template>
    </StateBlock>
    <el-dialog v-model="diffOpen" :title="$t('data.diff')" width="900px">
      <div class="row">
        <el-select v-model="da" style="width:120px"><el-option v-for="v in versions" :key="v.n" :label="'v' + v.n" :value="v.n" /></el-select>
        →
        <el-select v-model="db" style="width:120px"><el-option v-for="v in versions" :key="v.n" :label="'v' + v.n" :value="v.n" /></el-select>
        <el-button type="primary" @click="doDiff">{{ $t('common.compare') }}</el-button>
      </div>
      <div v-if="diff" style="margin-top:12px">
        <div class="row"><el-tag type="success">{{ $t('data.added') }}: {{ diff.added.length }}</el-tag><el-tag type="danger">{{ $t('data.removed') }}: {{ diff.removed.length }}</el-tag><el-tag type="warning">{{ $t('data.changed') }}: {{ diff.changed.length }}</el-tag></div>
        <el-table v-if="diff.changed.length" :data="changedFlat" size="small" max-height="360" style="margin-top:8px" border>
          <el-table-column :label="'Ключ'"><template #default="{ row }">{{ Object.values(row.key).join(' / ') }}</template></el-table-column>
          <el-table-column prop="field" :label="$t('dict.field')" />
          <el-table-column :label="'было'" align="right"><template #default="{ row }">{{ row.old ?? '—' }}</template></el-table-column>
          <el-table-column :label="'стало'" align="right"><template #default="{ row }"><b>{{ row.new ?? '—' }}</b></template></el-table-column>
        </el-table>
        <div v-for="(set, name) in { added: diff.added, removed: diff.removed }" :key="name">
          <div v-if="set.length" class="small" style="margin-top:8px"><b>{{ $t('data.' + name) }}:</b>
            <div v-for="(r, i) in set.slice(0, 20)" :key="i" class="mono">{{ Object.entries(r).filter(([k, v]) => v !== null).map(([k, v]) => k + '=' + v).join('; ') }}</div>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>
<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, download } from '../api'
import { useAuth } from '../store/auth'
import { fmt } from '../components/charts'
import StateBlock from '../components/StateBlock.vue'

const auth = useAuth()
const route = useRoute()
const ds = ref(null)
const dtype = ref(null)
const versions = ref([])
const version = ref(null)
const vinfo = ref(null)
const table = ref(null)
const rows = ref([])
const loading = ref(true)
const error = ref(null)
const editing = ref(false)
const comment = ref('')
const busy = ref(false)
const saveErrors = ref([])
const page = ref(1)
const size = 50
const spNames = ref({})
const refNames = ref({})   // {справочник: {код: название}}
const diffOpen = ref(false)
const da = ref(null)
const db = ref(null)
const diff = ref(null)

const cols = computed(() => {
  if (!dtype.value || !table.value) return []
  const c = dtype.value.columns.map((x) => ({ code: x.code, title: x.title_ru, unit: x.unit, type: x.type, ref: x.ref_entity,
    num: ['integer', 'number'].includes(x.type) }))
  const sc = dtype.value.species_columns || {}
  for (const s of table.value.species || []) c.push({ code: s, title: spNames.value[s] || s, unit: '', type: sc.value_type, num: true, species: true })
  return c
})
const pageRows = computed(() => rows.value.slice((page.value - 1) * size, page.value * size))
const changedFlat = computed(() => (diff.value?.changed || []).flatMap((c) => c.cells.map((x) => ({ key: c.key, ...x }))))
function show(v, c) {
  if (v === null || v === undefined) return '·'
  if (c.type === 'ref') return (refNames.value[c.ref] || {})[v] || v
  if (c.type === 'boolean') return v ? 'да' : 'нет'
  if (c.type === 'date') { const [y, m, d] = String(v).split('-'); return `${d}.${m}.${y}` }
  if (typeof v === 'number' && c.code !== 'year') return fmt(v, 'auto')
  return v
}
function rowClass() { return '' }
async function load() {
  loading.value = true; error.value = null
  try {
    ds.value = await api.get('data-admin', `/datasets/${route.params.id}`)
    const [t, vs, sp] = await Promise.all([api.get('data-model', `/dataset-types/${ds.value.dataset_type}`),
      api.get('data-admin', `/datasets/${ds.value.id}/versions`), api.get('data-model', '/entities/species/records')])
    dtype.value = t; versions.value = vs
    spNames.value = Object.fromEntries(sp.map((r) => [r.values.code, r.values.name_ru]))
    const ents = [...new Set(t.columns.filter((c) => c.type === 'ref').map((c) => c.ref_entity))]
    const lists = await Promise.all(ents.map((e) => api.get('data-model', `/entities/${e}/records`)))
    refNames.value = Object.fromEntries(ents.map((e, i) => [e, Object.fromEntries(lists[i].map((r) => [r.values.code || r.id, r.values.name_ru]))]))
    version.value = ds.value.current_version
    da.value = vs[1]?.n || vs[0]?.n; db.value = vs[0]?.n
    await loadData()
  } catch (e) { error.value = e } finally { loading.value = false }
}
async function loadData() {
  const j = await api.get('data-admin', `/datasets/${ds.value.id}/data`, { version: version.value })
  table.value = j.table; vinfo.value = j.version_info; rows.value = j.table.rows.map((r) => ({ ...r })); page.value = 1
}
function startEdit() {
  editing.value = true
  rows.value = table.value.rows.map((r) => {
    const o = { ...r }
    for (const c of cols.value) {
      if (c.type === 'date' && o[c.code]) { const [y, m, d] = o[c.code].split('-'); o[c.code] = `${d}.${m}.${y}` }
      if (c.type === 'boolean' && o[c.code] !== null) o[c.code] = o[c.code] ? 'да' : 'нет'
      if (c.type === 'ref' && o[c.code]) o[c.code] = (refNames.value[c.ref] || {})[o[c.code]] || o[c.code]
      if (o[c.code] === null || o[c.code] === undefined) o[c.code] = ''
      else o[c.code] = String(o[c.code])
    }
    return o
  })
}
function cancelEdit() { editing.value = false; saveErrors.value = []; rows.value = table.value.rows.map((r) => ({ ...r })) }
function addRow() { rows.value.push(Object.fromEntries(cols.value.map((c) => [c.code, '']))); page.value = Math.ceil(rows.value.length / size) }
function delRow(i) { rows.value.splice((page.value - 1) * size + i, 1) }
async function save() {
  busy.value = true; saveErrors.value = []
  try {
    const r = await api.put('data-admin', `/datasets/${ds.value.id}/data`, { rows: rows.value, comment: comment.value, base_version: ds.value.current_version })
    if (!r.ok) { saveErrors.value = r.errors; return }
    ElMessage.success(`${'Сохранена версия'} v${r.version}`)
    if (r.warnings?.length) ElMessage({ type: 'warning', duration: 8000, showClose: true,
      message: r.warnings.slice(0, 3).map((w) => w.message).join('\n') + (r.warnings.length > 3 ? ` … (+${r.warnings.length - 3})` : '') })
    editing.value = false; comment.value = ''
    await load()
  } catch (e) { saveErrors.value = [{ row: '', message: e.message }] } finally { busy.value = false }
}
async function restore() {
  await ElMessageBox.confirm(`Восстановить версию v${version.value} как новую текущую?`, '', { type: 'warning' })
  await api.post('data-admin', `/datasets/${ds.value.id}/restore/${version.value}`)
  await load()
}
async function doDiff() { diff.value = await api.get('data-admin', `/datasets/${ds.value.id}/diff`, { a: da.value, b: db.value }) }
onMounted(load)
</script>
<style scoped>
.miss { color: var(--fs-faint); }
</style>
