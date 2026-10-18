<template>
  <div class="page">
    <div class="page-head">
      <div><h1>{{ $t('dash.title') }}</h1><div class="sub">Представления исходных данных и результатов расчётов. Шаблоны можно скопировать и настроить.</div></div>
      <el-button v-if="auth.can('dashboard.edit')" type="primary" @click="create"><el-icon><Plus /></el-icon>&nbsp;{{ $t('dash.new') }}</el-button>
    </div>
    <StateBlock :loading="loading" :error="error">
      <div class="cards">
        <div v-for="d in items" :key="d.id" class="card dcard" @click="$router.push('/dashboards/' + d.id)">
          <div class="row" style="justify-content:space-between">
            <b>{{ tr(d, 'title') }}</b>
            <el-tag size="small" :type="d.is_template ? 'warning' : d.visibility === 'shared' ? 'success' : 'info'">{{ d.is_template ? $t('dash.templates') : $t('dash.' + d.visibility) }}</el-tag>
          </div>
          <div class="muted small" style="margin-top:6px; min-height:34px">{{ d.description }}</div>
          <div class="small muted">{{ d.widgets }} виджетов · v{{ d.current_version }} · {{ new Date(d.updated_at).toLocaleDateString() }}</div>
        </div>
      </div>
    </StateBlock>
  </div>
</template>
<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { tr } from '../i18n'
import { useAuth } from '../store/auth'
import StateBlock from '../components/StateBlock.vue'
const auth = useAuth()
const router = useRouter()
const items = ref([])
const loading = ref(true)
const error = ref(null)
async function create() {
  const d = await api.post('dashboards', '/dashboards', { title_ru: 'Новый дашборд', visibility: 'private', filters: { water_body: 'zhaysan' },
    tabs: [{ code: 'main', title_ru: 'Главная', title_kk: 'Басты' }], widgets: [] })
  router.push({ path: '/dashboards/' + d.id, query: { edit: 1 } })
}
onMounted(async () => { try { items.value = await api.get('dashboards', '/dashboards') } catch (e) { error.value = e } finally { loading.value = false } })
</script>
<style scoped>
.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 14px; }
.dcard { cursor: pointer; transition: box-shadow .15s; }
.dcard:hover { box-shadow: 0 4px 16px rgba(18,50,74,.12); }
.card + .card { margin-top: 0; }
</style>
