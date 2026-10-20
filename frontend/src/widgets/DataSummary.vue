<template>
  <div>
    <div class="kpis">
      <div class="kpi"><div class="v">{{ years }}</div><div class="l">{{ $t('w.years') }}</div></div>
      <div class="kpi"><div class="v">{{ nsets }}</div><div class="l">{{ $t('w.datasets') }}</div></div>
      <div class="kpi"><div class="v">{{ rows }}</div><div class="l">{{ $t('w.hauls') }}</div></div>
      <div class="kpi"><div class="v">{{ lastRun }}</div><div class="l">{{ $t('w.last_run') }}</div></div>
      <div class="kpi"><div class="v">{{ mainRun }}</div><div class="l">{{ $t('w.main_run') }}</div></div>
    </div>
    <div v-if="missing.length" class="small" style="margin-top:8px"><el-tag type="warning" size="small">{{ $t('w.not_loaded') }}</el-tag> {{ missing.join(', ') }}</div>
  </div>
</template>
<script setup>
import { useI18n } from 'vue-i18n'
import { computed } from 'vue'
const p = defineProps({ data: Object })
const { t } = useI18n()
const ALL = { catches: 'Уловы по ловам', age_samples: 'Возрастные пробы', mean_weights: 'Средний вес', species_props: 'Биол. параметры видов',
  yearly_conditions: 'Условия по годам', npc_stock: 'Оценка запаса НПЦ', npc_pdu: 'ПДУ НПЦ' }
const d = computed(() => p.data?.data || { datasets: {}, years: [] })
const years = computed(() => (d.value.years?.length ? `${d.value.years[0]}–${d.value.years[d.value.years.length - 1]}` : '—'))
const nsets = computed(() => Object.keys(d.value.datasets || {}).length)
const rows = computed(() => d.value.datasets?.catches?.rows ?? '—')
const dt = (r) => (r ? new Date(r.finished_at || r.created_at).toLocaleDateString('ru-RU') : '—')
const lastRun = computed(() => dt(p.data?.runs?.last_done))
const mainRun = computed(() => dt(p.data?.runs?.main_run))
const missing = computed(() => Object.keys(ALL).filter((k) => !(d.value.datasets || {})[k]).map((k) => ALL[k]))
</script>
