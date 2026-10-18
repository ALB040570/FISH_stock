<template>
  <div v-if="rows.length">
    <div class="grid12">
      <div style="grid-column: span 7">
        <el-table :data="rows" size="small" border>
          <el-table-column prop="species" label="Вид" min-width="90" />
          <el-table-column :label="`ПДУ ${rows[0].year_first_fc}, т (F = k·M)`" align="right" min-width="120">
            <template #default="{ row }"><b>{{ fmt(row.pdu_next_t, 1) }}</b></template></el-table-column>
          <el-table-column label="95 % интервал, т" align="right" min-width="130">
            <template #default="{ row }">{{ fmt(row.pdu_next_t_q025, 1) }} – {{ fmt(row.pdu_next_t_q975, 1) }}</template></el-table-column>
          <el-table-column label="F" align="right"><template #default="{ row }">{{ fmt(row.F_next, 3) }}</template></el-table-column>
          <el-table-column :label="`ПДУ НПЦ ${rows[0].year_last}, т`" align="right" min-width="110"><template #default="{ row }">{{ fmt(row.npc_last_t, 1) }}</template></el-table-column>
          <el-table-column label="P(снижение)" align="right"><template #default="{ row }">{{ fmt(row.p_decline_baranov * 100, 0) }} %</template></el-table-column>
        </el-table>
      </div>
      <div style="grid-column: span 5"><EChart :option="opt" height="260px" /></div>
    </div>
    <div class="small muted" style="margin-top:6px">k = {{ fmt(data.payload.k, 2) }}; горизонт прогноза {{ data.payload.horizon }} лет. P(снижение) — доля траекторий, в которых численность к концу прогноза ниже последнего года истории.</div>
  </div>
</template>
<script setup>
import { computed } from 'vue'
import EChart from '../components/EChart.vue'
import { base, fmt } from '../components/charts'
const p = defineProps({ data: Object })
const rows = computed(() => p.data?.payload?.summary || [])
const opt = computed(() => {
  const o = base({ x: rows.value.map((r) => r.species), type: 'bar', yName: 'т', series: [
    { name: 'ПДУ (F = k·M), медиана', values: rows.value.map((r) => r.pdu_next_t) },
    { name: 'ПДУ НПЦ последнего года', values: rows.value.map((r) => r.npc_last_t) }] })
  return o
})
</script>
