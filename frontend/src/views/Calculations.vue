<template>
  <div class="page">
    <div class="page-head">
      <div><h1>{{ $t('calc.title') }}</h1><div class="sub">Расчёт — наборы данных водоёма, цепочка алгоритмов, параметры и формат результатов.</div></div>
      <div class="row">
        <WaterBodySelect v-model="wb" clearable @update:model-value="sync" />
        <template v-if="auth.can('run.execute')">
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
    <StateBlock :loading="loading" :error="error" :empty="!items.length" :empty-text="wb ? 'Для водоёма ещё нет расчётов — создайте из шаблона.' : 'Расчётов пока нет.'">
      <div class="card">
        <el-table :data="items" @row-click="(r) => $router.push('/calculations/' + r.id)" style="cursor:pointer">
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
  } catch (e) { error.value = e } finally { loading.value = false }
}
async function fromTpl(t) {
  try { const c = await api.post('algo-admin', '/calculations/from-template', { water_body: wb.value, template: t }); router.push('/calculations/' + c.id) }
  catch (e) { error.value = e }
}
onMounted(load)
</script>
