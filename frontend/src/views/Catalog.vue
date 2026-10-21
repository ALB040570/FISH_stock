<template>
  <div class="page">
    <div class="page-head"><div><h1>{{ $t('catalog.title') }}</h1><div class="sub">Опубликованные проверенные версии алгоритмов. Для расчётов доступны только включённые версии.</div></div></div>
    <StateBlock :loading="loading" :error="error">
      <div class="row" style="gap:8px; margin-bottom:10px">
        <el-select v-model="fModel" clearable :placeholder="$t('catalog.model_type')" style="width:220px">
          <el-option v-for="m in cls.model_types || []" :key="m.code" :label="tr(m, 'name')" :value="m.code" />
        </el-select>
        <el-select v-model="fMethod" clearable :placeholder="$t('catalog.stock_method')" style="width:240px">
          <el-option v-for="m in cls.stock_methods || []" :key="m.code" :label="tr(m, 'name')" :value="m.code" />
        </el-select>
      </div>
      <div v-for="a in shown" :key="a.code" class="card">
        <div class="row" style="justify-content:space-between">
          <div>
            <h2 style="margin:0">{{ tr(a, 'title') }} <span class="muted small mono">{{ a.code }}</span></h2>
            <div class="muted small">{{ a.description }}</div>
            <div class="row small" style="gap:6px; margin-top:6px; flex-wrap:wrap; align-items:center">
              <span class="muted">{{ $t('catalog.model_type') }}:</span>
              <el-tag size="small" :type="a.classification?.model_type === 'stochastic' ? 'warning' : 'info'">{{ clsName('model_types', a.classification?.model_type) }}</el-tag>
              <template v-if="a.classification?.stock_methods?.length">
                <span class="muted" style="margin-left:6px">{{ $t('catalog.stock_method') }}:</span>
                <el-tag v-for="m in a.classification.stock_methods" :key="m" size="small" effect="plain">{{ clsName('stock_methods', m) }}</el-tag>
              </template>
              <el-button v-if="auth.can('catalog.manage')" size="small" text @click="editCls(a)"><el-icon><Edit /></el-icon></el-button>
            </div>
          </div>
          <el-tag v-if="a.latest" type="success">{{ $t('common.version') }} {{ a.latest }}</el-tag>
        </div>
        <el-collapse style="margin-top:8px">
          <el-collapse-item :title="$t('catalog.params') + ` (${a.manifest?.parameters?.length || 0})`">
            <el-table :data="a.manifest?.parameters || []" size="small">
              <el-table-column prop="code" :label="$t('common.code')" width="200"><template #default="{ row }"><span class="mono">{{ row.code }}</span></template></el-table-column>
              <el-table-column prop="title_ru" :label="$t('common.name')" min-width="260" />
              <el-table-column :label="$t('common.type')" width="120" prop="type" />
              <el-table-column label="Категория" width="130"><template #default="{ row }"><el-tag size="small" :type="{ fixed: 'info', waterbody: 'warning', run: 'success' }[row.category]">{{ $t('catalog.cat_' + row.category) }}</el-tag></template></el-table-column>
              <el-table-column label="По умолчанию" min-width="140"><template #default="{ row }"><span class="mono">{{ row.default === null || row.default === undefined ? '—' : JSON.stringify(row.default) }}</span></template></el-table-column>
            </el-table>
            <div class="small" style="margin-top:6px"><b>{{ $t('catalog.requires') }}:</b> {{ (a.manifest?.requires?.datasets || []).join(', ') }} · <b>{{ $t('catalog.steps') }}:</b> {{ (a.manifest?.requires?.steps || []).join(', ') || '—' }}</div>
          </el-collapse-item>
          <el-collapse-item :title="$t('common.versions') + ` (${a.versions.length})`">
            <el-table :data="a.versions" size="small">
              <el-table-column prop="version" :label="$t('common.version')" width="90" />
              <el-table-column :label="$t('common.status')" width="110"><template #default="{ row }"><el-tag size="small" :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? $t('catalog.enabled') : $t('catalog.disabled') }}</el-tag></template></el-table-column>
              <el-table-column :label="$t('catalog.source')" width="120"><template #default="{ row }">{{ row.source === 'builtin' ? $t('algo.builtin') : row.source }}</template></el-table-column>
              <el-table-column :label="$t('common.date')" width="170"><template #default="{ row }">{{ new Date(row.created_at).toLocaleString('ru-RU') }}</template></el-table-column>
              <el-table-column :label="$t('catalog.checksum')" min-width="160"><template #default="{ row }"><span class="mono small">{{ row.checksum.slice(0, 16) }}…</span></template></el-table-column>
              <el-table-column min-width="190"><template #default="{ row }"><span class="small muted">{{ row.report?.note || row.report?.comment || '' }}</span></template></el-table-column>
              <el-table-column width="270" align="right">
                <template #default="{ row }">
                  <el-button size="small" @click="showCode(a, row)">{{ $t('catalog.code_view') }}</el-button>
                  <el-button size="small" @click="download('algo-admin', `/catalog/${a.code}/versions/${row.version}/package.zip`)">zip</el-button>
                  <template v-if="auth.can('catalog.manage')">
                    <el-button v-if="row.enabled" size="small" @click="toggle(a, row, false)">{{ $t('catalog.disable') }}</el-button>
                    <el-button v-else size="small" type="primary" @click="toggle(a, row, true)">{{ $t('catalog.enable') }}</el-button>
                  </template>
                </template>
              </el-table-column>
            </el-table>
          </el-collapse-item>
        </el-collapse>
      </div>
    </StateBlock>
    <el-dialog v-model="clsOpen" :title="$t('catalog.classification')" width="460px">
      <el-form label-position="top">
        <el-form-item :label="$t('catalog.model_type')">
          <el-radio-group v-model="clsForm.model_type">
            <el-radio v-for="m in cls.model_types || []" :key="m.code" :value="m.code">{{ tr(m, 'name') }}</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item :label="$t('catalog.stock_method')">
          <el-checkbox-group v-model="clsForm.stock_methods">
            <el-checkbox v-for="m in cls.stock_methods || []" :key="m.code" :value="m.code">{{ tr(m, 'name') }}</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="clsOpen = false">{{ $t('common.cancel') }}</el-button>
        <el-button type="primary" @click="saveCls">{{ $t('common.save') }}</el-button>
      </template>
    </el-dialog>
    <el-drawer v-model="codeOpen" :title="codeTitle" size="70%">
      <div class="row" style="align-items:flex-start; gap:12px">
        <el-scrollbar style="width:280px; height:78vh"><div v-for="f in files" :key="f.path" class="fl" :class="{ sel: f.path === filePath }" @click="openFile(f.path)">{{ f.path }}</div></el-scrollbar>
        <pre class="code-editor grow" style="height:78vh; overflow:auto; margin:0">{{ fileText }}</pre>
      </div>
    </el-drawer>
  </div>
</template>
<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { api, download } from '../api'
import { tr } from '../i18n'
import { useAuth } from '../store/auth'
import StateBlock from '../components/StateBlock.vue'
const auth = useAuth()
const items = ref([])
const loading = ref(true)
const error = ref(null)
const codeOpen = ref(false)
const codeTitle = ref('')
const files = ref([])
const filePath = ref('')
const fileText = ref('')
let cur = null
const cls = ref({})
const fModel = ref('')
const fMethod = ref('')
const shown = computed(() => items.value.filter((a) => (!fModel.value || a.classification?.model_type === fModel.value) &&
  (!fMethod.value || (a.classification?.stock_methods || []).includes(fMethod.value))))
function clsName(group, code) {
  const r = (cls.value[group] || []).find((x) => x.code === code)
  return r ? tr(r, 'name') : (code || '—')
}
const clsOpen = ref(false)
const clsForm = reactive({ model_type: null, stock_methods: [] })
let clsCode = null
function editCls(a) {
  clsCode = a.code
  clsForm.model_type = a.classification?.model_type || null
  clsForm.stock_methods = [...(a.classification?.stock_methods || [])]
  clsOpen.value = true
}
async function saveCls() {
  await api.put('algo-admin', `/catalog/${clsCode}/classification`, { ...clsForm })
  clsOpen.value = false; await load()
}
async function load() {
  try {
    ;[items.value, cls.value] = await Promise.all([api.get('algo-admin', '/catalog'), api.get('algo-admin', '/classifiers')])
  } catch (e) { error.value = e } finally { loading.value = false }
}
async function toggle(a, v, on) { await api.post('algo-admin', `/catalog/${a.code}/versions/${v.version}/${on ? 'enable' : 'disable'}`); await load() }
async function showCode(a, v) {
  cur = { a, v }; codeTitle.value = `${a.code} ${v.version}`
  files.value = await api.get('algo-admin', `/catalog/${a.code}/versions/${v.version}/files`)
  codeOpen.value = true
  openFile(files.value.find((f) => f.path === 'algorithm.py')?.path || files.value[0].path)
}
async function openFile(p) {
  filePath.value = p
  fileText.value = (await api.get('algo-admin', `/catalog/${cur.a.code}/versions/${cur.v.version}/files`, { path: p })).text
}
onMounted(load)
</script>
<style scoped>
.fl { padding: 3px 8px; cursor: pointer; font-family: monospace; font-size: 12px; border-radius: 4px; }
.fl:hover { background: var(--fs-hover); }
.fl.sel { background: var(--fs-selected); font-weight: 600; }
</style>
