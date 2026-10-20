<template>
  <div class="page">
    <div class="page-head">
      <div><h1>{{ $t('runs.title') }}</h1><div class="sub">{{ $t('runs.queue') }}: {{ queue.queued.length }} · {{ $t('runs.st_running') }}: {{ queue.running.length }}</div></div>
      <div class="row">
        <WaterBodySelect v-model="wb" clearable @update:model-value="load" />
        <el-select v-model="status" clearable :placeholder="$t('common.status')" style="width:150px" @change="load">
          <el-option v-for="s in ['queued', 'running', 'done', 'failed', 'cancelled']" :key="s" :label="$t('runs.st_' + s)" :value="s" />
        </el-select>
        <el-button @click="load"><el-icon><Refresh /></el-icon></el-button>
      </div>
    </div>
    <StateBlock :loading="loading" :error="error" :empty="!items.length">
      <div class="card">
        <el-table :data="items" @row-click="(r) => $router.push('/runs/' + r.id)" style="cursor:pointer">
          <el-table-column :label="$t('runs.started')" width="170"><template #default="{ row }">{{ new Date(row.created_at).toLocaleString('ru-RU') }}</template></el-table-column>
          <el-table-column prop="calculation_title" :label="$t('calc.title')" min-width="280" />
          <el-table-column prop="water_body" :label="$t('common.water_body')" width="130" />
          <el-table-column :label="$t('runs.steps')" min-width="170">
            <template #default="{ row }"><span v-for="s in row.steps" :key="s.algorithm" class="tag-dot" :title="s.title" :style="{ background: dot[s.status] || '#ccd5de' }" /></template>
          </el-table-column>
          <el-table-column :label="$t('common.status')" width="140"><template #default="{ row }"><RunStatus :status="row.status" /> <el-tag v-if="row.is_main" size="small">★</el-tag></template></el-table-column>
          <el-table-column prop="author_name" :label="$t('common.author')" width="150" />
          <el-table-column prop="message" :label="$t('data.message')" min-width="220" show-overflow-tooltip />
        </el-table>
      </div>
    </StateBlock>
  </div>
</template>
<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { api } from '../api'
import StateBlock from '../components/StateBlock.vue'
import RunStatus from '../components/RunStatus.vue'
import WaterBodySelect from '../components/WaterBodySelect.vue'
const dot = { done: '#2f9e6b', reused: '#7cc7a3', running: '#3b82c4', failed: '#c44536', cancelled: '#e08a1e', skipped: '#ccd5de', pending: '#ccd5de' }
const wb = ref(null)
const status = ref(null)
const items = ref([])
const queue = ref({ queued: [], running: [] })
const loading = ref(true)
const error = ref(null)
let timer
async function load() {
  try {
    ;[items.value, queue.value] = await Promise.all([api.get('algo-admin', '/runs', { water_body: wb.value, status: status.value }), api.get('algo-admin', '/queue')])
    error.value = null
  } catch (e) { error.value = e } finally { loading.value = false }
}
onMounted(() => { load(); timer = setInterval(load, 5000) })
onBeforeUnmount(() => clearInterval(timer))
</script>
