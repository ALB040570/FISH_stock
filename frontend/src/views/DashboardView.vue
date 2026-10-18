<template>
  <div class="page">
    <StateBlock :loading="loading" :error="error">
      <template v-if="b">
        <div class="page-head">
          <div>
            <el-button text @click="$router.push('/dashboards')"><el-icon><ArrowLeft /></el-icon>&nbsp;{{ $t('dash.title') }}</el-button>
            <h1 v-if="!editing">{{ tr(b, 'title') }}</h1>
            <el-input v-else v-model="b.title_ru" style="width:420px; font-size:18px" />
            <div class="sub">{{ b.description }}</div>
          </div>
          <div class="row">
            <WaterBodySelect v-if="!multi" v-model="f.water_body" />
            <el-select v-else v-model="f.water_bodies" multiple filterable :placeholder="$t('dash.water_bodies')" style="width:360px">
              <el-option v-for="w in wbs" :key="w.code" :label="w.name_ru" :value="w.code" />
            </el-select>
            <el-select v-model="f.species" clearable :placeholder="$t('monitoring.species_all')" style="width:160px">
              <el-option v-for="s in species" :key="s.code" :label="tr(s, 'name')" :value="s.code" />
            </el-select>
            <template v-if="b.can_edit">
              <el-button v-if="!editing" @click="editing = true"><el-icon><Edit /></el-icon>&nbsp;{{ $t('dash.edit') }}</el-button>
              <template v-else>
                <el-select v-if="!b.is_template" v-model="b.visibility" style="width:170px"><el-option :label="$t('dash.private')" value="private" /><el-option :label="$t('dash.shared')" value="shared" /></el-select>
                <el-button @click="cancelEdit">{{ $t('common.cancel') }}</el-button>
                <el-button type="primary" @click="save">{{ $t('common.save') }}</el-button>
              </template>
            </template>
            <el-button v-if="auth.can('dashboard.edit')" @click="copy">{{ $t('monitoring.copy') }}</el-button>
            <el-button v-if="b.can_edit && !b.system" text type="danger" @click="del"><el-icon><Delete /></el-icon></el-button>
          </div>
        </div>
        <div v-if="editing" class="card row" style="margin-bottom:12px">
          <el-button size="small" type="primary" @click="editW(null)"><el-icon><Plus /></el-icon>&nbsp;{{ $t('dash.add_widget') }}</el-button>
          <el-button size="small" @click="addTab"><el-icon><Plus /></el-icon>&nbsp;{{ $t('dash.add_tab') }}</el-button>
          <template v-if="b.tabs?.length">
            <span class="small muted">{{ $t('dash.tab') }}:</span>
            <el-input v-for="t in b.tabs" :key="t.code" v-model="t.title_ru" size="small" style="width:150px" />
          </template>
          <el-checkbox v-model="multiFlag">{{ $t('dash.water_bodies') }}</el-checkbox>
          <StateBlock :error="saveErr" />
        </div>
        <DashboardBoard v-model="tab" :board="b" :filters="filters" :species="spNames" :editing="editing" @edit-widget="editW" @move="move" @remove="remove" />
      </template>
    </StateBlock>
    <el-dialog v-model="wdlg" :title="$t('dash.widget')" width="760px">
      <el-form v-if="w" label-width="170px">
        <el-form-item :label="$t('common.name')"><el-input v-model="w.title_ru" /></el-form-item>
        <el-form-item :label="$t('common.type')">
          <el-select v-model="w.type"><el-option v-for="t in ['kpi', 'line', 'bar', 'table', 'text', 'special']" :key="t" :label="$t('dash.w_' + t)" :value="t" /></el-select>
        </el-form-item>
        <el-form-item v-if="b.tabs?.length" :label="$t('dash.tab')"><el-select v-model="w.tab"><el-option v-for="t in b.tabs" :key="t.code" :label="t.title_ru" :value="t.code" /></el-select></el-form-item>
        <template v-if="w.type === 'text'"><el-form-item label="Текст"><el-input v-model="w.options.text" type="textarea" :rows="5" /></el-form-item></template>
        <template v-else>
          <el-form-item :label="$t('dash.source')">
            <el-radio-group v-model="w.source.kind">
              <el-radio value="dataset">{{ $t('dash.src_dataset') }}</el-radio><el-radio value="run">{{ $t('dash.src_run') }}</el-radio><el-radio value="payload">{{ $t('dash.src_payload') }}</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item v-if="w.source.kind === 'dataset'" :label="$t('data.choose_type')">
            <el-select v-model="w.source.dataset_type" style="width:300px"><el-option v-for="t in dtypes" :key="t.code" :label="t.title_ru" :value="t.code" /></el-select>
          </el-form-item>
          <template v-if="w.source.kind === 'run' || w.source.kind === 'payload'">
            <el-form-item :label="$t('catalog.title')">
              <el-select v-model="w.source.algorithm" style="width:300px"><el-option v-for="a in catalog" :key="a.code" :label="a.title_ru" :value="a.code" /></el-select>
            </el-form-item>
            <el-form-item v-if="w.source.kind === 'run'" :label="$t('runs.tables')">
              <el-select v-model="w.source.table" style="width:300px"><el-option v-for="o in outputsOf(w.source.algorithm)" :key="o.code" :label="o.title_ru" :value="o.code" /></el-select>
            </el-form-item>
          </template>
          <el-form-item v-if="w.type === 'special'" :label="$t('dash.w_special')">
            <el-select v-model="w.options.kind" style="width:300px"><el-option v-for="(t, k) in SPECIALS" :key="k" :label="t" :value="k" /></el-select>
          </el-form-item>
          <template v-if="['line', 'bar', 'kpi'].includes(w.type)">
            <el-form-item :label="$t('dash.x')"><el-input v-model="w.options.x" placeholder="year" style="width:200px" /></el-form-item>
            <el-form-item :label="$t('dash.y')"><el-input v-model="w.options.y" placeholder="$species или stock" style="width:200px" /><span class="muted small" style="margin-left:8px">$species — столбец выбранного вида</span></el-form-item>
            <el-form-item :label="$t('dash.series')"><el-input v-model="w.options.series" placeholder="gear / species / water_body" style="width:200px" /></el-form-item>
            <el-form-item :label="$t('dash.agg')"><el-select v-model="w.options.agg" style="width:160px"><el-option v-for="a in ['sum', 'mean', 'count', 'last']" :key="a" :label="$t('dash.agg_' + a)" :value="a" /></el-select></el-form-item>
          </template>
          <el-form-item :label="$t('dash.table_filter')"><el-input v-model="filterText" class="mono" placeholder='{"variant": "with_ages", "year": "$last_year"}' /></el-form-item>
          <el-form-item v-if="multi" label=" "><el-checkbox v-model="w.source.multi">по всем выбранным водоёмам</el-checkbox></el-form-item>
        </template>
        <el-form-item :label="$t('dash.width')"><el-slider v-model="w.w" :min="3" :max="12" :step="1" show-stops style="width:300px" /></el-form-item>
        <el-form-item :label="$t('dash.height')"><el-slider v-model="w.h" :min="2" :max="10" style="width:300px" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="wdlg = false">{{ $t('common.cancel') }}</el-button><el-button type="primary" @click="applyW">{{ $t('common.save') }}</el-button></template>
    </el-dialog>
  </div>
</template>
<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../api'
import { tr } from '../i18n'
import { useAuth } from '../store/auth'
import StateBlock from '../components/StateBlock.vue'
import WaterBodySelect from '../components/WaterBodySelect.vue'
import DashboardBoard from '../widgets/DashboardBoard.vue'
const SPECIALS = { data_summary: 'Сводка данных', seine_curves: 'Уловистость невода', net_curves: 'Уловистость сети', bayes_band: 'Численность (модель)',
  pdu_summary: 'ПДУ по видам', pdu_breakdown: 'Раскладка ПДУ', forecast_scenarios: 'Прогноз по сценариям' }
const auth = useAuth()
const route = useRoute()
const router = useRouter()
const b = ref(null)
let orig = null
const loading = ref(true)
const error = ref(null)
const saveErr = ref(null)
const editing = ref(!!route.query.edit)
const tab = ref(null)
const species = ref([])
const wbs = ref([])
const dtypes = ref([])
const catalog = ref([])
const f = reactive({ water_body: route.query.wb || 'zhaysan', water_bodies: [], species: null })
const multiFlag = ref(false)
const multi = computed(() => multiFlag.value)
const spNames = computed(() => Object.fromEntries(species.value.map((s) => [s.code, s.name_ru])))
const filters = computed(() => ({ water_body: f.water_body, water_bodies: f.water_bodies, species: f.species, species_ru: f.species ? spNames.value[f.species] : null }))
const wdlg = ref(false)
const w = ref(null)
const filterText = ref('')
let editIndex = -1
const outputsOf = (code) => (catalog.value.find((a) => a.code === code)?.manifest?.outputs || []).filter((o) => o.format === 'table')
async function load() {
  try {
    const [d, sp, wb, dt, cat] = await Promise.all([api.get('dashboards', `/dashboards/${route.params.id}`), api.get('data-model', '/entities/species/records'),
      api.get('data-model', '/entities/water_bodies/records'), api.get('data-model', '/dataset-types'), api.get('algo-admin', '/catalog')])
    b.value = d; orig = JSON.parse(JSON.stringify(d))
    species.value = sp.map((r) => r.values); wbs.value = wb.map((r) => r.values); dtypes.value = dt; catalog.value = cat
    multiFlag.value = 'water_bodies' in (d.filters || {})
    if (multiFlag.value) f.water_bodies = d.filters.water_bodies?.length ? d.filters.water_bodies : ['zhaysan']
    if (d.filters?.water_body) f.water_body = route.query.wb || d.filters.water_body
  } catch (e) { error.value = e } finally { loading.value = false }
}
function editW(x) {
  editIndex = x ? b.value.widgets.indexOf(x) : -1
  w.value = JSON.parse(JSON.stringify(x || { id: 'w' + Date.now(), type: 'line', title_ru: 'Новый виджет', tab: tab.value || b.value.tabs?.[0]?.code,
    source: { kind: 'dataset', dataset_type: 'npc_pdu' }, w: 6, h: 4, options: { x: 'year', y: '$species', agg: 'sum' } }))
  w.value.options ||= {}
  filterText.value = w.value.options.filter ? JSON.stringify(w.value.options.filter) : ''
  wdlg.value = true
}
function applyW() {
  try { w.value.options.filter = filterText.value ? JSON.parse(filterText.value) : undefined } catch (e) { ElMessage.error('Фильтр — неверный JSON'); return }
  if (editIndex >= 0) b.value.widgets.splice(editIndex, 1, w.value); else b.value.widgets.push(w.value)
  wdlg.value = false
}
function move(x, d) { const a = b.value.widgets; const i = a.indexOf(x); const j = i + d; if (j < 0 || j >= a.length) return; a.splice(i, 1); a.splice(j, 0, x) }
function remove(x) { b.value.widgets.splice(b.value.widgets.indexOf(x), 1) }
function addTab() { b.value.tabs ||= []; const code = 't' + Date.now(); b.value.tabs.push({ code, title_ru: 'Вкладка', title_kk: '' }); tab.value = code }
function cancelEdit() { b.value = JSON.parse(JSON.stringify(orig)); editing.value = false }
async function save() {
  saveErr.value = null
  const filtersSave = multiFlag.value ? { water_bodies: f.water_bodies, species: f.species } : { water_body: f.water_body, species: f.species }
  try {
    b.value = await api.put('dashboards', `/dashboards/${b.value.id}`, { title_ru: b.value.title_ru, title_kk: b.value.title_kk, description: b.value.description,
      visibility: b.value.visibility, filters: filtersSave, tabs: b.value.tabs || [], widgets: b.value.widgets })
    orig = JSON.parse(JSON.stringify(b.value)); editing.value = false; ElMessage.success('Дашборд сохранён')
  } catch (e) { saveErr.value = e }
}
async function copy() { const d = await api.post('dashboards', `/dashboards/${b.value.id}/copy`, {}); router.push({ path: '/dashboards/' + d.id, query: { edit: 1 } }) }
async function del() { await ElMessageBox.confirm('Удалить дашборд?', '', { type: 'warning' }); await api.del('dashboards', `/dashboards/${b.value.id}`); router.push('/dashboards') }
onMounted(load)
</script>
