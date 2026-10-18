<template>
  <div class="page">
    <div class="page-head">
      <div><h1>{{ $t('audit.title') }}</h1><div class="sub">{{ $t('audit.retention', { days: retention }) }}</div></div>
      <el-button @click="download('users', '/audit/export.xlsx', query)">{{ $t('audit.export') }}</el-button>
    </div>
    <div class="card row" style="margin-bottom:12px">
      <el-date-picker v-model="range" type="daterange" value-format="YYYY-MM-DD" format="DD.MM.YYYY" style="width:280px" />
      <el-input v-model="f.login" :placeholder="$t('audit.user')" clearable style="width:160px" />
      <el-select v-model="f.service" clearable :placeholder="$t('audit.service')" style="width:160px">
        <el-option v-for="s in ['users', 'data_model', 'data_admin', 'algo_model', 'algo_admin', 'dashboards']" :key="s" :label="s" :value="s" />
      </el-select>
      <el-input v-model="f.action" :placeholder="$t('audit.action')" clearable style="width:170px" />
      <el-input v-model="f.text" :placeholder="$t('common.search')" clearable style="width:200px" />
      <el-button type="primary" @click="pg = 1; load()">{{ $t('common.show') }}</el-button>
    </div>
    <StateBlock :loading="loading" :error="error">
      <div class="card">
        <el-table :data="items" size="small">
          <el-table-column :label="$t('audit.ts')" width="170"><template #default="{ row }">{{ new Date(row.ts).toLocaleString() }}</template></el-table-column>
          <el-table-column prop="login" :label="$t('audit.user')" width="130" />
          <el-table-column prop="service" :label="$t('audit.service')" width="110" />
          <el-table-column prop="action" :label="$t('audit.action')" width="180" />
          <el-table-column :label="$t('audit.object')" min-width="200"><template #default="{ row }">{{ row.object_type }} <span class="mono small muted">{{ row.object_id }}</span></template></el-table-column>
          <el-table-column :label="$t('audit.ok')" width="80"><template #default="{ row }"><el-tag size="small" :type="row.ok === false ? 'danger' : 'success'">{{ row.ok === false ? $t('common.no') : $t('common.yes') }}</el-tag></template></el-table-column>
          <el-table-column :label="$t('common.details')" min-width="260"><template #default="{ row }"><span class="mono small">{{ row.details ? JSON.stringify(row.details) : '' }}</span></template></el-table-column>
        </el-table>
        <el-pagination v-model:current-page="pg" :page-size="100" :total="total" layout="total, prev, pager, next" style="margin-top:8px" @current-change="load" />
      </div>
    </StateBlock>
  </div>
</template>
<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { api, download } from '../api'
import StateBlock from '../components/StateBlock.vue'
const f = reactive({ login: '', service: '', action: '', text: '' })
const range = ref(null)
const items = ref([])
const total = ref(0)
const retention = ref(365)
const pg = ref(1)
const loading = ref(true)
const error = ref(null)
const query = computed(() => ({ ...f, date_from: range.value?.[0], date_to: range.value?.[1] }))
async function load() {
  loading.value = true
  try { const j = await api.get('users', '/audit', { ...query.value, offset: (pg.value - 1) * 100, limit: 100 }); items.value = j.items; total.value = j.total; retention.value = j.retention_days }
  catch (e) { error.value = e } finally { loading.value = false }
}
onMounted(load)
</script>
