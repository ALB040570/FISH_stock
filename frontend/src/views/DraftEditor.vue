<template>
  <div class="page">
    <StateBlock :loading="loading" :error="error">
      <template v-if="d">
        <div class="page-head">
          <div>
            <el-button text @click="$router.push('/algorithms')"><el-icon><ArrowLeft /></el-icon>&nbsp;{{ $t('algo.title') }}</el-button>
            <h1>{{ d.manifest?.title_ru || d.algorithm }} <span class="mono muted" style="font-size:15px">{{ d.manifest?.version }}</span></h1>
            <div class="sub">{{ d.status === 'published' ? 'опубликован ' + d.published_version : 'черновик' }}<template v-if="d.base_version"> · от версии {{ d.base_version }}</template> · ревизия {{ d.current_version }}</div>
          </div>
          <div class="row">
            <input ref="zip" type="file" accept=".zip" style="display:none" @change="uploadZip" />
            <el-button @click="$refs.zip.click()">{{ $t('algo.upload_zip') }}</el-button>
            <el-button @click="download('algo-model', `/drafts/${d.id}/download.zip`)">{{ $t('algo.download_zip') }}</el-button>
            <el-button @click="validate">{{ $t('algo.validate') }}</el-button>
            <el-button type="primary" :disabled="d.status === 'published'" @click="testOpen = true">{{ $t('algo.test') }}</el-button>
            <el-button type="success" :disabled="d.status === 'published'" @click="publish">{{ $t('algo.publish') }}</el-button>
          </div>
        </div>
        <el-alert v-if="val" :type="val.ok ? 'success' : 'error'" :closable="true" show-icon :title="val.ok ? 'Проверка пройдена' : 'Ошибки проверки'" style="margin-bottom:10px" @close="val = null">
          <div v-for="e in val.errors" :key="e" class="small">• {{ e }}</div>
          <div v-for="w in val.warnings" :key="w" class="small muted">• {{ w }}</div>
        </el-alert>
        <StateBlock :error="actErr" />
        <div class="grid12">
          <div class="card" style="grid-column: span 3; padding:10px">
            <div class="row" style="justify-content:space-between"><b>{{ $t('algo.files') }}</b><el-button size="small" text @click="newFile"><el-icon><Plus /></el-icon></el-button></div>
            <el-scrollbar max-height="64vh">
              <div v-for="f in d.files" :key="f.path" class="fl" :class="{ sel: f.path === path, dim: f.path.startsWith('fishcore/') }" @click="open(f.path)">{{ f.path }}</div>
            </el-scrollbar>
          </div>
          <div class="card" style="grid-column: span 9">
            <div class="row" style="margin-bottom:6px">
              <span class="mono">{{ path }}</span><span v-if="dirty" class="muted small">● изменён</span>
              <div class="grow" />
              <el-input v-model="comment" size="small" :placeholder="$t('common.comment')" style="width:280px" />
              <el-button size="small" type="primary" :disabled="!dirty || d.status === 'published'" @click="saveFile">{{ $t('common.save') }}</el-button>
              <el-button v-if="path !== 'manifest.json'" size="small" text type="danger" :disabled="d.status === 'published'" @click="delFile"><el-icon><Delete /></el-icon></el-button>
            </div>
            <div class="muted small" style="margin-bottom:6px">{{ $t('algo.contract') }}</div>
            <textarea v-model="text" class="code-editor nowrap" wrap="off" spellcheck="false" @input="dirty = true" @keydown.tab.prevent="tabKey" />
          </div>
        </div>
        <div class="card">
          <h2 style="margin-top:0">{{ $t('algo.test') }}</h2>
          <el-table :data="d.tests" size="small" @row-click="showTest">
            <el-table-column :label="$t('common.date')" width="170"><template #default="{ row }">{{ new Date(row.created_at).toLocaleString('ru-RU') }}</template></el-table-column>
            <el-table-column :label="$t('common.status')" width="140"><template #default="{ row }"><el-tag size="small" :type="row.status === 'passed' ? 'success' : row.status === 'failed' ? 'danger' : 'info'">{{ $t('algo.' + row.status) }}</el-tag></template></el-table-column>
            <el-table-column prop="draft_version" label="ревизия" width="90" />
            <el-table-column prop="water_body" :label="$t('common.water_body')" width="120" />
            <el-table-column :label="$t('algo.comparison')" width="160"><template #default="{ row }"><span v-if="row.compare_with">{{ row.compare_with }}: {{ row.comparison_ok === false ? 'есть отличия' : row.comparison_ok ? 'совпадает' : '' }}</span></template></el-table-column>
            <el-table-column prop="message" :label="$t('data.message')" show-overflow-tooltip />
          </el-table>
          <div class="muted small" style="margin-top:6px">{{ $t('algo.publish_hint') }}</div>
        </div>
      </template>
    </StateBlock>
    <el-dialog v-model="testOpen" :title="$t('algo.test')" width="620px">
      <el-form label-width="180px">
        <el-form-item :label="$t('common.water_body')"><WaterBodySelect v-model="tf.water_body" /></el-form-item>
        <el-form-item :label="$t('algo.compare_with')">
          <el-select v-model="tf.compare_with" clearable style="width:200px"><el-option v-for="v in published" :key="v.version" :label="v.version" :value="v.version" /></el-select>
        </el-form-item>
        <el-form-item :label="$t('algo.test_params')"><el-input v-model="tf.params" type="textarea" :rows="4" class="mono" placeholder='{"mode": "prior"}' /></el-form-item>
      </el-form>
      <div class="muted small">Предыдущие шаги цепочки выполняются опубликованными версиями; байесовская модель как предшественник — короткой выборкой.</div>
      <template #footer><el-button @click="testOpen = false">{{ $t('common.cancel') }}</el-button><el-button type="primary" @click="startTest">{{ $t('common.run') }}</el-button></template>
    </el-dialog>
    <el-drawer v-model="testView" :title="$t('algo.test')" size="60%">
      <template v-if="tv">
        <el-alert :type="tv.status === 'passed' ? 'success' : tv.status === 'failed' ? 'error' : 'info'" :closable="false" :title="tv.message || tv.status" />
        <div v-if="tv.summary" style="margin-top:8px">
          <div v-for="(t, k) in tv.summary.tables" :key="k" class="small">таблица <b>{{ t.title }}</b>: {{ t.rows }} строк</div>
          <div v-for="(m, k) in tv.summary.metrics || {}" :key="k" class="small">{{ m.title }}: {{ fmt(m.value, 'auto') }}</div>
        </div>
        <div v-if="tv.comparison" style="margin-top:8px">
          <h3>{{ $t('algo.comparison') }} — {{ tv.compare_with }}</h3>
          <el-table :data="tv.comparison.tables" size="small">
            <el-table-column prop="table" label="Таблица" /><el-table-column prop="status" :label="$t('common.status')" />
            <el-table-column label="Наиб. отн. отличие" align="right"><template #default="{ row }">{{ row.max_rel_diff == null ? '—' : row.max_rel_diff.toExponential(2) }}</template></el-table-column>
            <el-table-column prop="column" label="Столбец" />
          </el-table>
        </div>
        <pre class="code-editor" style="margin-top:8px; min-height:200px; max-height:50vh; overflow:auto">{{ tv.log }}{{ tv.traceback ? '\n' + tv.traceback : '' }}</pre>
      </template>
    </el-drawer>
  </div>
</template>
<script setup>
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, download } from '../api'
import { fmt } from '../components/charts'
import StateBlock from '../components/StateBlock.vue'
import WaterBodySelect from '../components/WaterBodySelect.vue'
const route = useRoute()
const d = ref(null)
const published = ref([])
const loading = ref(true)
const error = ref(null)
const actErr = ref(null)
const path = ref('algorithm.py')
const text = ref('')
const dirty = ref(false)
const comment = ref('')
const val = ref(null)
const testOpen = ref(false)
const testView = ref(false)
const tv = ref(null)
const tf = reactive({ water_body: 'zhaysan', compare_with: null, params: '{}' })
let poll
async function load() {
  try {
    d.value = await api.get('algo-model', `/drafts/${route.params.id}`)
    if (!published.value.length) published.value = (await api.get('algo-model', `/algorithms/${d.value.algorithm}`)).published
  } catch (e) { error.value = e } finally { loading.value = false }
}
async function open(p) {
  if (dirty.value && !(await ElMessageBox.confirm('Есть несохранённые изменения. Перейти?', '', { type: 'warning' }).catch(() => false))) return
  path.value = p; text.value = (await api.get('algo-model', `/drafts/${d.value.id}/file`, { path: p })).text; dirty.value = false
}
async function saveFile() {
  actErr.value = null
  try { d.value = await api.put('algo-model', `/drafts/${d.value.id}/file`, { path: path.value, text: text.value, comment: comment.value }); dirty.value = false; comment.value = ''; ElMessage.success('Сохранено') }
  catch (e) { actErr.value = e }
}
async function newFile() {
  const { value } = await ElMessageBox.prompt('Имя файла (например helpers.py)', 'Новый файл')
  path.value = value; text.value = ''; dirty.value = true
}
async function delFile() { await ElMessageBox.confirm(`Удалить ${path.value}?`, '', { type: 'warning' }); d.value = await api.del('algo-model', `/drafts/${d.value.id}/file`, { path: path.value }); open('algorithm.py') }
async function uploadZip(e) { actErr.value = null; try { d.value = await api.upload('algo-model', `/drafts/${d.value.id}/upload`, { file: e.target.files[0] }); open('manifest.json') } catch (x) { actErr.value = x } e.target.value = '' }
async function validate() { val.value = await api.post('algo-model', `/drafts/${d.value.id}/validate`) }
async function startTest() {
  actErr.value = null
  let params = {}
  try { params = JSON.parse(tf.params || '{}') } catch (e) { actErr.value = 'Параметры теста — неверный JSON'; return }
  try {
    const t = await api.post('algo-model', `/drafts/${d.value.id}/test`, { water_body: tf.water_body, compare_with: tf.compare_with, params })
    testOpen.value = false; await load(); showTest(t)
  } catch (e) { actErr.value = e; testOpen.value = false }
}
async function showTest(t) {
  tv.value = await api.get('algo-model', `/tests/${t.id}`); testView.value = true
  clearInterval(poll)
  if (['queued', 'running'].includes(tv.value.status)) {
    poll = setInterval(async () => {
      tv.value = await api.get('algo-model', `/tests/${t.id}`)
      if (!['queued', 'running'].includes(tv.value.status)) { clearInterval(poll); load() }
    }, 2000)
  }
}
async function publish() {
  actErr.value = null
  try { await ElMessageBox.confirm(`Опубликовать версию ${d.value.manifest.version} в каталог?`, '', { type: 'info' }); d.value = await api.post('algo-model', `/drafts/${d.value.id}/publish`, {}); ElMessage.success('Версия опубликована') }
  catch (e) { if (e !== 'cancel') actErr.value = e }
}
function tabKey(e) { const t = e.target; const s = t.selectionStart; text.value = text.value.slice(0, s) + '    ' + text.value.slice(t.selectionEnd); dirty.value = true; requestAnimationFrame(() => { t.selectionStart = t.selectionEnd = s + 4 }) }
onMounted(async () => { await load(); if (d.value) open(d.value.files.find((f) => f.path === 'algorithm.py') ? 'algorithm.py' : 'manifest.json') })
onBeforeUnmount(() => clearInterval(poll))
</script>
<style scoped>
.fl { padding: 3px 6px; cursor: pointer; font-family: monospace; font-size: 12px; border-radius: 4px; }
.fl:hover { background: var(--fs-hover); }
.fl.sel { background: var(--fs-selected); font-weight: 600; }
.fl.dim { color: var(--fs-faint); }
.nowrap { white-space: pre; overflow-x: auto; overflow-wrap: normal; }
</style>
