<template>
  <div class="page">
    <div class="page-head">
      <div><h1>{{ design ? $t('calc.design_title') : $t('calc.title') }}</h1><div class="sub">{{ design ? $t('calc.design_hint') : $t('calc.run_hint') }}</div></div>
      <div class="row">
        <WaterBodySelect v-model="wb" clearable @update:model-value="sync" />
        <template v-if="design && auth.can('run.execute')">
          <el-dropdown split-button type="primary" :disabled="!wb" @click="fromTpl('full')" @command="fromTpl">
            {{ $t('calc.new') }}
            <template #dropdown><el-dropdown-menu>
              <el-dropdown-item command="full">{{ $t('calc.tpl_full') }}</el-dropdown-item>
              <el-dropdown-item command="stock">{{ $t('calc.tpl_stock') }}</el-dropdown-item>
            </el-dropdown-menu></template>
          </el-dropdown>
        </template>
      </div>
    </div>
    <div v-if="!design" class="queue card">
      <span class="muted">{{ $t('calc.queue_now') }}:</span>
      <span>{{ $t('runs.st_queued') }}: <b class="num">{{ queue.queued?.length ?? '—' }}</b></span>
      <span>{{ $t('runs.st_running') }}: <b class="num">{{ queue.running?.length ?? '—' }}</b></span>
      <div class="grow" />
      <router-link to="/calc/runs">{{ $t('calc.all_runs') }} →</router-link>
    </div>
    <StateBlock :loading="loading" :error="error" :empty="!items.length" :empty-text="design ? (wb ? 'Для водоёма ещё нет расчётов — создайте из шаблона.' : 'Расчётов пока нет.') : $t('calc.no_calc_run')">
      <div class="card">
        <el-table :data="items" @row-click="(r) => $router.push(base + '/' + r.id)" style="cursor:pointer">
          <el-table-column :label="$t('common.name')" min-width="300"><template #default="{ row }"><b>{{ row.title }}</b><div class="muted small">{{ row.description }}</div></template></el-table-column>
          <el-table-column prop="water_body" :label="$t('common.water_body')" width="140" />
          <el-table-column :label="$t('calc.steps')" min-width="260"><template #default="{ row }"><span class="small">{{ row.steps.map((s) => titles[s.algorithm] || s.algorithm).join(' → ') }}</span></template></el-table-column>
          <el-table-column :label="$t('common.version')" width="80" align="right"><template #default="{ row }">v{{ row.current_version }}</template></el-table-column>
          <el-table-column :label="$t('common.date')" width="170"><template #default="{ row }">{{ new Date(row.updated_at).toLocaleString('ru-RU') }}</template></el-table-column>
        </el-table>
      </div>
    </StateBlock>
  </div>
</template>
<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import { useAuth } from '../store/auth'
import StateBlock from '../components/StateBlock.vue'
import WaterBodySelect from '../components/WaterBodySelect.vue'
const auth = useAuth()
const route = useRoute()
// /calculations — запуск (раздел «Расчёт»); /design/calculations — порядок расчёта (раздел «Конструктор»)
const design = !!route.meta.design
const base = design ? '/design/calculations' : '/calc/calculations'
const queue = ref({})
const router = useRouter()
const wb = ref(route.query.wb || null)
const items = ref([])
const titles = ref({})
const loading = ref(true)
const error = ref(null)
function sync() { router.replace({ query: wb.value ? { wb: wb.value } : {} }); load() }
async function load() {
  loading.value = true; error.value = null
  try {
    const [c, cat] = await Promise.all([api.get('algo-admin', '/calculations', { water_body: wb.value }), api.get('algo-admin', '/catalog')])
    items.value = c.sort((a, b) => (a.updated_at < b.updated_at ? 1 : -1))
    titles.value = Object.fromEntries(cat.map((a) => [a.code, a.title_ru]))
    if (!design) { try { queue.value = await api.get('algo-admin', '/queue') } catch (e) { queue.value = {} } }
  } catch (e) { error.value = e } finally { loading.value = false }
}
async function fromTpl(t) {
  try { const c = await api.post('algo-admin', '/calculations/from-template', { water_body: wb.value, template: t }); router.push(base + '/' + c.id) }
  catch (e) { error.value = e }
}
onMounted(load)
</script>
<style scoped>
.queue { display: flex; gap: 18px; align-items: center; padding: 10px 16px; margin-bottom: 14px; }
</style>
