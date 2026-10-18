<template>
  <div v-if="rows.length">
    <div class="grid12">
      <div style="grid-column: span 7">
        <el-table :data="rows" size="small" border>
          <el-table-column prop="species" :label="$t('common.species')" min-width="90" />
          <el-table-column :label="`${$t('w.pdu')} ${rows[0].year_first_fc}, т (F = k·M)`" align="right" min-width="150">
            <template #default="{ row }"><b>{{ fmt(row.pdu_next_t, 1) }}</b></template></el-table-column>
          <el-table-column :label="$t('w.ci95_t')" align="right" min-width="130">
            <template #default="{ row }">{{ fmt(row.pdu_next_t_q025, 1) }} – {{ fmt(row.pdu_next_t_q975, 1) }}</template></el-table-column>
          <el-table-column label="F" align="right"><template #default="{ row }">{{ fmt(row.F_next, 3) }}</template></el-table-column>
          <el-table-column :label="`${$t('w.pdu_npc')} ${rows[0].year_last}, т`" align="right" min-width="110"><template #default="{ row }">{{ fmt(row.npc_last_t, 1) }}</template></el-table-column>
          <el-table-column :label="$t('w.p_decline')" align="right" min-width="120"><template #default="{ row }">{{ fmt(row.p_decline_baranov * 100, 0) }} %</template></el-table-column>
        </el-table>
      </div>
      <div style="grid-column: span 5"><EChart :option="opt" height="260px" /></div>
    </div>
    <div class="small muted" style="margin-top:6px">k = {{ fmt(data.payload.k, 2) }}; {{ $t('w.horizon') }} {{ data.payload.horizon }}. {{ $t('w.p_decline_hint') }}</div>
  </div>
</template>
<script setup>
import { useI18n } from 'vue-i18n'
import { computed } from 'vue'
import EChart from '../components/EChart.vue'
import { base, fmt } from '../components/charts'
const p = defineProps({ data: Object })
const { t } = useI18n()
const rows = computed(() => p.data?.payload?.summary || [])
const opt = computed(() => {
  const o = base({ x: rows.value.map((r) => r.species), type: 'bar', yName: 'т', series: [
    { name: t('w.pdu_baranov'), values: rows.value.map((r) => r.pdu_next_t) },
    { name: t('w.pdu_npc_last'), values: rows.value.map((r) => r.npc_last_t) }] })
  return o
})
</script>
