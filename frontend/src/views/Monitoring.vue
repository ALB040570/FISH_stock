<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1>{{ $t('monitoring.title') }}<template v-if="wbRec">: {{ tr(wbRec, 'name') }}</template></h1>
        <div class="sub">{{ wbRec ? (wbRec.region || '') : $t('monitoring.choose') }}</div>
      </div>
      <div class="row">
        <el-select v-model="wb" filterable :placeholder="$t('monitoring.choose')" style="width:260px" @change="go">
          <el-option v-for="w in wbs" :key="w.code" :label="tr(w, 'name')" :value="w.code" />
        </el-select>
        <el-select v-model="sp" clearable :placeholder="$t('monitoring.species_all')" style="width:170px">
          <el-option v-for="s in speciesList" :key="s.code" :label="tr(s, 'name')" :value="s.code" />
        </el-select>
        <el-button v-if="board && auth.can('dashboard.edit')" @click="copy">{{ $t('monitoring.copy') }}</el-button>
      </div>
    </div>
    <StateBlock :loading="loading" :error="error">
      <template v-if="wb && board">
        <el-alert v-if="runInfo && !runInfo.run" type="info" :closable="false" show-icon :title="$t('monitoring.no_run')" style="margin-bottom:12px">
          <router-link v-if="auth.can('run.execute')" :to="{ path: '/calculations', query: { wb } }">{{ $t('map.start_calc') }}</router-link>
        </el-alert>
        <el-alert v-else-if="runInfo && !runInfo.is_main" type="warning" :closable="false" show-icon style="margin-bottom:12px"
                  :title="$t('monitoring.run_last')">
          <router-link :to="'/runs/' + runInfo.run.id">{{ runInfo.run.calculation_title }}</router-link>
        </el-alert>
        <el-alert v-else-if="runInfo" type="success" :closable="false" show-icon style="margin-bottom:12px" :title="$t('monitoring.run_main')">
          <router-link :to="'/runs/' + runInfo.run.id">{{ runInfo.run.calculation_title }}</router-link>
          <span class="muted"> · {{ new Date(runInfo.run.finished_at).toLocaleString() }}</span>
        </el-alert>
        <DashboardBoard :board="board" :filters="filters" :species="spNames" />
      </template>
      <div v-else-if="!wb" class="card state">{{ $t('monitoring.choose') }}</div>
    </StateBlock>
  </div>
</template>
<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api } from '../api'
import { tr } from '../i18n'
import { useAuth } from '../store/auth'
import StateBlock from '../components/StateBlock.vue'
import DashboardBoard from '../widgets/DashboardBoard.vue'

const auth = useAuth()
const route = useRoute()
const router = useRouter()
const wb = ref(route.params.wb || null)
const sp = ref(null)
const wbs = ref([])
const speciesList = ref([])
const board = ref(null)
const runInfo = ref(null)
const loading = ref(true)
const error = ref(null)
const wbRec = computed(() => wbs.value.find((w) => w.code === wb.value))
const spNames = computed(() => Object.fromEntries(speciesList.value.map((s) => [s.code, s.name_ru])))
const filters = computed(() => ({ water_body: wb.value, species: sp.value, species_ru: sp.value ? spNames.value[sp.value] : null }))
function go(v) { router.push('/monitoring/' + v) }
onMounted(async () => {
  try {
    const [w, s, b] = await Promise.all([api.get('data-model', '/entities/water_bodies/records'),
      api.get('data-model', '/entities/species/records'), api.get('dashboards', '/dashboards/monitoring')])
    wbs.value = w.map((r) => r.values).sort((a, b) => a.name_ru.localeCompare(b.name_ru))
    speciesList.value = s.map((r) => r.values)
    board.value = b
    if (wb.value) runInfo.value = await api.get('algo-admin', `/water-bodies/${wb.value}/monitoring-run`)
  } catch (e) { error.value = e } finally { loading.value = false }
})
async function copy() {
  const d = await api.post('dashboards', '/dashboards/monitoring/copy', {})
  ElMessage.success(d.title_ru)
  router.push({ path: '/dashboards/' + d.id, query: { wb: wb.value, edit: 1 } })
}
</script>
