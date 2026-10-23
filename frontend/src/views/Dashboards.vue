<template>
  <div class="page">
    <div class="page-head">
      <div><h1>{{ design ? $t('dash.design_title') : $t('dash.title') }}</h1><div class="sub">{{ design ? 'Создание и правка дашбордов и шаблонов. Шаблон можно скопировать и настроить.' : 'Представления исходных данных и результатов расчётов.' }}</div></div>
      <div v-if="design && auth.can('dashboard.edit')" class="row">
        <el-button @click="$router.push('/design/signal-rules')"><el-icon><Bell /></el-icon>&nbsp;{{ $t('wv.rules') }}</el-button>
        <el-button type="primary" @click="create"><el-icon><Plus /></el-icon>&nbsp;{{ $t('dash.new') }}</el-button>
      </div>
    </div>
    <StateBlock :loading="loading" :error="error">
      <div class="cards">
        <div v-for="d in items" :key="d.id" class="card dcard" @click="$router.push(base + '/' + d.id)">
          <div class="row" style="justify-content:space-between">
            <b>{{ tr(d, 'title') }}</b>
            <el-tag size="small" :type="d.is_template ? 'warning' : d.visibility === 'shared' ? 'success' : 'info'">{{ d.is_template ? $t('dash.templates') : $t('dash.' + d.visibility) }}</el-tag>
          </div>
          <div class="muted small" style="margin-top:6px; min-height:34px">{{ d.description }}</div>
          <div class="small muted">{{ d.widgets }} виджетов · v{{ d.current_version }} · {{ new Date(d.updated_at).toLocaleDateString('ru-RU') }}</div>
        </div>
      </div>
    </StateBlock>
  </div>
</template>
<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import { tr } from '../i18n'
import { useAuth } from '../store/auth'
import StateBlock from '../components/StateBlock.vue'
const auth = useAuth()
// /dashboards — просмотр (раздел «Аналитика»); /design/dashboards — конструктор: свои, шаблоны, новый
const design = !!useRoute().meta.design
const base = design ? '/design/dashboards' : '/monitoring/dashboards'
const router = useRouter()
const items = ref([])
const loading = ref(true)
const error = ref(null)
async function create() {
  const d = await api.post('dashboards', '/dashboards', { title_ru: 'Новый дашборд', visibility: 'private', filters: { water_body: 'zhaysan' },
    tabs: [{ code: 'main', title_ru: 'Главная', title_kk: 'Басты' }], widgets: [] })
  router.push(base + '/' + d.id)
}
onMounted(async () => { try {
    const all = await api.get('dashboards', '/dashboards')
    // в конструкторе — то, что можно править или копировать; в просмотре — готовые дашборды без заготовок
    items.value = design ? all.filter((d) => d.can_edit || d.is_template) : all.filter((d) => !d.is_template || d.system)
  } catch (e) { error.value = e } finally { loading.value = false } })
</script>
<style scoped>
.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 14px; }
.dcard { cursor: pointer; transition: box-shadow .15s; }
.dcard:hover { box-shadow: none; border-color: var(--fs-primary-soft); }
.card + .card { margin-top: 0; }
</style>
