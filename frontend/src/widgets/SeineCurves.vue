<template>
  <div v-if="fits">
    <div class="row" style="margin-bottom:6px">
      <el-select v-model="chosen" size="small" style="width:150px"><el-option v-for="s in list" :key="s" :label="s" :value="s" /></el-select>
      <el-select v-model="year" size="small" style="width:100px"><el-option v-for="y in years" :key="y" :label="y" :value="y" /></el-select>
      <span v-if="fit" class="small muted">
        c̄ = {{ fmt(fit.c_mean, 3) }}<template v-if="fit.j50 != null"> · j50 = {{ fmt(fit.j50, 2) }} · a = {{ fmt(fit.a, 2) }}</template>
        <template v-if="fit.peak != null"> · {{ $t('w.peak') }} c¹ = {{ fmt(fit.peak, 2) }}</template> · {{ $t('w.sample') }} {{ fit.n_sample }} {{ $t('w.pcs') }} ·
        <el-tag size="small" :type="String(fit.status).includes('нарушено') ? 'warning' : 'success'">{{ fit.status }}</el-tag>
      </span>
    </div>
    <EChart v-if="fit" :option="opt" height="300px" />
    <div v-if="fit" class="small muted">{{ fit.source }}</div>
  </div>
</template>
<script setup>
import { useI18n } from 'vue-i18n'
import { computed, ref, watch } from 'vue'
import EChart from '../components/EChart.vue'
import { CHART } from '../theme'
import { compact, fmt, pal } from '../components/charts'
import { useSpecies } from './useSpecies'
const p = defineProps({ data: Object, filters: Object, options: Object })
const { t } = useI18n()
const net = computed(() => p.options?.kind === 'net_curves')
const fits = computed(() => (net.value ? p.data?.payload?.net?.fits : p.data?.payload?.fits))
const { list, chosen } = useSpecies(p, () => Object.keys(fits.value || {}))
const years = computed(() => Object.keys(fits.value?.[chosen.value] || {}))
const year = ref(null)
watch(years, (y) => { if (!y.includes(year.value)) year.value = y[y.length - 1] }, { immediate: true })
const fit = computed(() => fits.value?.[chosen.value]?.[year.value])
const label = (a) => `${a - 1}–${a}`
const opt = computed(() => {
  const f = fit.value
  const ages = f.ages.map(label)
  // у сети нижняя граница своя у каждого вида (c̄/3) — в подгонке; общей нет
  const lo = net.value ? (f.c_lower ?? p.data.payload.net.c_lower) : p.data.payload.c_lower
  const hi = net.value ? p.data.payload.net.c_upper : p.data.payload.c_upper
  return {
    color: pal(),
    grid: { left: 60, right: 52, top: 56, bottom: 34 },
    tooltip: { trigger: 'axis', valueFormatter: (v) => fmt(v, 'auto') },
    legend: { top: 0 },
    xAxis: { type: 'category', data: ages, name: t('w.age_years'), nameLocation: 'middle', nameGap: 22 },
    yAxis: [{ type: 'value', name: f.observed_is_catch ? t('w.catch_pcs') : t('w.sample_pcs'), axisLabel: { formatter: compact }, splitLine: { lineStyle: { color: CHART.grid } } },
      { type: 'value', name: 'c', min: 0, max: 1, splitLine: { show: false } }],
    series: [
      { type: 'bar', name: f.observed_is_catch ? t('w.catch_by_age') : t('w.age_sample'), data: f.observed, itemStyle: { color: CHART.background }, barMaxWidth: 26 },
      ...(f.fitted ? [{ type: 'line', name: t('w.catch_curve'), data: f.fitted, symbol: 'none', lineStyle: { color: CHART.fit } }] : []),
      { type: 'line', name: t('w.catchability'), data: f.c, yAxisIndex: 1, lineStyle: { width: 2.5, color: CHART.main }, itemStyle: { color: CHART.main },
        markLine: { silent: true, symbol: 'none', lineStyle: { type: 'dashed', color: CHART.limit }, label: { formatter: '{c}' }, data: [lo, hi].filter((v) => v !== null && v !== undefined).map((v) => ({ yAxis: v })) } },
    ],
  }
})
</script>
