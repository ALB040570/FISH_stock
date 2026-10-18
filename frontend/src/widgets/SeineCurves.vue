<template>
  <div v-if="fits">
    <div class="row" style="margin-bottom:6px">
      <el-select v-model="chosen" size="small" style="width:150px"><el-option v-for="s in list" :key="s" :label="s" :value="s" /></el-select>
      <el-select v-model="year" size="small" style="width:100px"><el-option v-for="y in years" :key="y" :label="y" :value="y" /></el-select>
      <span v-if="fit" class="small muted">
        c̄ = {{ fmt(fit.c_mean, 3) }}<template v-if="fit.j50 != null"> · j50 = {{ fmt(fit.j50, 2) }} · a = {{ fmt(fit.a, 2) }}</template>
        <template v-if="fit.peak != null"> · вершина c¹ = {{ fmt(fit.peak, 2) }}</template> · проба {{ fit.n_sample }} шт ·
        <el-tag size="small" :type="String(fit.status).includes('нарушено') ? 'warning' : 'success'">{{ fit.status }}</el-tag>
      </span>
    </div>
    <EChart v-if="fit" :option="opt" height="300px" />
    <div v-if="fit" class="small muted">{{ fit.source }}</div>
  </div>
</template>
<script setup>
import { computed, ref, watch } from 'vue'
import EChart from '../components/EChart.vue'
import { compact, fmt, PALETTE } from '../components/charts'
import { useSpecies } from './useSpecies'
const p = defineProps({ data: Object, filters: Object, options: Object })
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
  const lo = net.value ? p.data.payload.net.c_lower : p.data.payload.c_lower
  const hi = net.value ? p.data.payload.net.c_upper : p.data.payload.c_upper
  return {
    color: PALETTE,
    grid: { left: 60, right: 52, top: 56, bottom: 34 },
    tooltip: { trigger: 'axis', valueFormatter: (v) => fmt(v, 'auto') },
    legend: { top: 0 },
    xAxis: { type: 'category', data: ages, name: 'возраст, лет', nameLocation: 'middle', nameGap: 22 },
    yAxis: [{ type: 'value', name: f.observed_is_catch ? 'улов, шт' : 'проба, шт', axisLabel: { formatter: compact }, splitLine: { lineStyle: { color: '#edf1f5' } } },
      { type: 'value', name: 'c', min: 0, max: 1, splitLine: { show: false } }],
    series: [
      { type: 'bar', name: f.observed_is_catch ? 'улов по возрастам' : 'возрастная проба', data: f.observed, itemStyle: { color: '#a9c9da' }, barMaxWidth: 26 },
      ...(f.fitted ? [{ type: 'line', name: 'кривая улова (подгонка)', data: f.fitted, symbol: 'none', lineStyle: { color: '#2a9d8f' } }] : []),
      { type: 'line', name: 'уловистость c', data: f.c, yAxisIndex: 1, lineStyle: { width: 2.5, color: '#1d5c7a' }, itemStyle: { color: '#1d5c7a' },
        markLine: { silent: true, symbol: 'none', lineStyle: { type: 'dashed', color: '#c44536' }, label: { formatter: '{c}' }, data: [{ yAxis: lo }, { yAxis: hi }] } },
    ],
  }
})
</script>
