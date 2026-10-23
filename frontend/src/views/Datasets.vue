<template>
  <div class="page">
    <div class="page-head">
      <div><h1>{{ $t('data.title') }}</h1><div class="sub">{{ $t('data.missing_hint') }}</div></div>
      <div class="row">
        <WaterBodySelect v-model="wb" @update:model-value="sync" />
        <el-button v-if="auth.can('data.edit') && wb" type="primary" @click="openUpload(null)"><el-icon><Upload /></el-icon>&nbsp;{{ $t('data.upload') }}</el-button>
      </div>
    </div>
    <StateBlock :loading="loading" :error="error" :empty="!wb" :empty-text="$t('monitoring.choose')">
      <div class="card">
        <el-table :data="rows" size="default">
          <el-table-column :label="$t('data.choose_type')" min-width="230">
            <template #default="{ row }"><b>{{ tr(row.type, 'title') }}</b><div class="muted small">{{ row.type.description }}</div></template>
          </el-table-column>
          <el-table-column :label="$t('common.status')" width="140">
            <template #default="{ row }">
              <el-tag v-if="row.ds?.current_version" type="success">v{{ row.ds.current_version }}</el-tag>
              <el-tag v-else type="info">{{ $t('data.not_loaded') }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="$t('data.rows')" width="90" align="right"><template #default="{ row }">{{ row.ds?.summary?.rows ?? '—' }}</template></el-table-column>
          <el-table-column :label="$t('data.period')" width="120"><template #default="{ row }">{{ row.ds?.summary?.period_from ? row.ds.summary.period_from + '–' + row.ds.summary.period_to : '—' }}</template></el-table-column>
          <el-table-column :label="$t('common.date')" width="170"><template #default="{ row }">{{ row.ds ? new Date(row.ds.updated_at).toLocaleString('ru-RU') : '' }}</template></el-table-column>
          <el-table-column :label="$t('common.actions')" width="330" align="right">
            <template #default="{ row }">
              <el-button size="small" @click="download('data-admin', `/templates/${row.type.code}.xlsx`, { water_body: wb })">{{ $t('data.template') }}</el-button>
              <el-button v-if="auth.can('data.edit')" size="small" @click="openUpload(row.type.code)">{{ $t('common.upload') }}</el-button>
              <el-button v-if="row.ds?.current_version" size="small" type="primary" plain @click="$router.push('/input/datasets/' + row.ds.id)">{{ $t('common.open') }}</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </StateBlock>
    <UploadDialog v-model="up" :water-body="wb" :types="types" :initial-type="upType" @uploaded="load" />
  </div>
</template>
<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, download } from '../api'
import { tr } from '../i18n'
import { useAuth } from '../store/auth'
import StateBlock from '../components/StateBlock.vue'
import UploadDialog from '../components/UploadDialog.vue'
import WaterBodySelect from '../components/WaterBodySelect.vue'
const auth = useAuth()
const route = useRoute()
const router = useRouter()
const wb = ref(route.query.wb || 'zhaysan')
const types = ref([])
const sets = ref([])
const loading = ref(true)
const error = ref(null)
const up = ref(false)
const upType = ref(null)
const rows = computed(() => types.value.map((t) => ({ type: t, ds: sets.value.find((s) => s.dataset_type === t.code) })))
function sync() { router.replace({ query: { wb: wb.value } }); load() }
function openUpload(t) { upType.value = t || types.value[0]?.code; up.value = true }
async function load() {
  loading.value = true; error.value = null
  try {
    const [t, s] = await Promise.all([api.get('data-model', '/dataset-types'), api.get('data-admin', '/datasets', { water_body: wb.value })])
    types.value = t; sets.value = s
  } catch (e) { error.value = e } finally { loading.value = false }
}
onMounted(load)
</script>
