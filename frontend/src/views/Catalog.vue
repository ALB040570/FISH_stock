<template>
  <div class="page">
    <div class="page-head"><div><h1>{{ $t('catalog.title') }}</h1><div class="sub">Опубликованные проверенные версии алгоритмов. Для расчётов доступны только включённые версии.</div></div></div>
    <StateBlock :loading="loading" :error="error">
      <div v-for="a in items" :key="a.code" class="card">
        <div class="row" style="justify-content:space-between">
          <div>
            <h2 style="margin:0">{{ tr(a, 'title') }} <span class="muted small mono">{{ a.code }}</span></h2>
            <div class="muted small">{{ a.description }}</div>
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
              <el-table-column :label="$t('common.date')" width="170"><template #default="{ row }">{{ new Date(row.created_at).toLocaleString() }}</template></el-table-column>
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
    <el-drawer v-model="codeOpen" :title="codeTitle" size="70%">
      <div class="row" style="align-items:flex-start; gap:12px">
        <el-scrollbar style="width:280px; height:78vh"><div v-for="f in files" :key="f.path" class="fl" :class="{ sel: f.path === filePath }" @click="openFile(f.path)">{{ f.path }}</div></el-scrollbar>
        <pre class="code-editor grow" style="height:78vh; overflow:auto; margin:0">{{ fileText }}</pre>
      </div>
    </el-drawer>
  </div>
</template>
<script setup>
import { onMounted, ref } from 'vue'
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
async function load() {
  try { items.value = await api.get('algo-admin', '/catalog') } catch (e) { error.value = e } finally { loading.value = false }
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
.fl:hover { background: #eef3f7; }
.fl.sel { background: #e3eef4; font-weight: 600; }
</style>
