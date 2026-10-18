<template>
  <div v-if="sp">
    <div class="row" style="margin-bottom:6px">
      <el-select v-model="chosen" size="small" style="width:150px"><el-option v-for="s in list" :key="s" :label="s" :value="s" /></el-select>
      <el-radio-group v-model="sc" size="small">
        <el-radio-button v-for="(t, k) in sp.scenario_titles" :key="k" :value="k">{{ t }}</el-radio-button>
      </el-radio-group>
    </div>
    <div class="grid12">
      <div style="grid-column: span 6"><EChart :option="totalOpt" height="290px" /></div>
      <div style="grid-column: span 6"><EChart :option="pduOpt" height="290px" /></div>
    </div>
    <el-table :data="ageRows" size="small" border style="margin-top:8px" max-height="240">
      <el-table-column prop="year" :label="$t('common.year')" width="70" />
      <el-table-column :label="$t('w.pdu_t_median')" align="right" min-width="110"><template #default="{ row }"><b>{{ fmt(row.t, 1) }}</b></template></el-table-column>
      <el-table-column v-for="a in matureAges" :key="a" :label="`${a - 1}–${a}, ${$t('w.pcs')}`" align="right" min-width="90">
        <template #default="{ row }">{{ fmt(row.pcs[a]) }}</template></el-table-column>
    </el-table>
    <div class="small muted" style="margin-top:6px">{{ $t('w.p_decline_to', { y: sp.years_fc[sp.years_fc.length - 1], p: fmt(sp.scenarios[sc].p_decline * 100, 0) }) }}
      <span v-for="n in sp.notes" :key="n"> {{ n }}</span></div>
  </div>
</template>
<script setup>
import { useI18n } from 'vue-i18n'
import { computed, ref } from 'vue'
import EChart from '../components/EChart.vue'
import { band, base, fmt } from '../components/charts'
import { useSpecies } from './useSpecies'
const p = defineProps({ data: Object, filters: Object })
const { t } = useI18n()
const all = computed(() => p.data?.payload?.species || {})
const { list, chosen } = useSpecies(p, () => Object.keys(all.value))
const sp = computed(() => all.value[chosen.value])
const sc = ref('baranov')
const years = computed(() => [...sp.value.years_hist, ...sp.value.years_fc])
const totalOpt = computed(() => {
  const nh = sp.value.years_hist.length
  const pad = (arr, pre) => (pre ? [...arr, ...Array(sp.value.years_fc.length).fill(null)] : [...Array(nh).fill(null), ...arr])
  const qh = sp.value.hist.total_q.map((r) => pad(r, true))
  const qf = sp.value.scenarios[sc.value].total_q
  const q = qh.map((r, k) => r.map((v, i) => (i < nh ? v : qf[k][i - nh])))
  const o = band({ x: years.value, q, name: t('w.total_median'), yName: 'шт' })
  o.series.push({ type: 'line', name: t('w.fc_start'), data: [], markLine: { symbol: 'none', silent: true, lineStyle: { color: '#e08a1e', type: 'dashed' },
    data: [{ xAxis: String(sp.value.years_fc[0]) }] } })
  return o
})
const pduOpt = computed(() => {
  const s = sp.value.scenarios
  const nh = sp.value.years_hist.length
  return base({ x: years.value, type: 'bar', yName: 'т', series: [
    { name: t('w.pdu_npc_hist'), values: [...sp.value.hist.npc_pdu_t, ...Array(sp.value.years_fc.length).fill(null)], extra: { itemStyle: { color: '#a9c9da' } } },
    { name: `${t('w.pdu')}: ${sp.value.scenario_titles[sc.value]}`, values: [...Array(nh).fill(null), ...s[sc.value].pdu_t_q[2]], extra: { itemStyle: { color: '#1d5c7a' } } }] })
})
const matureAges = computed(() => sp.value.ages.filter((a) => a >= sp.value.m0))
const ageRows = computed(() => sp.value.years_fc.map((y, h) => {
  const pcs = {}
  sp.value.ages.forEach((a, i) => { pcs[a] = sp.value.scenarios[sc.value].pdu_pcs_median[h][i] })
  return { year: y, t: sp.value.scenarios[sc.value].pdu_t_q[2][h], pcs }
}))
</script>
