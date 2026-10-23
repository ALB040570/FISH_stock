<template>
  <div v-if="sp">
    <div class="row" style="margin-bottom:8px">
      <el-select v-model="chosen" size="small" style="width:150px"><el-option v-for="s in list" :key="s" :label="s" :value="s" /></el-select>
      <el-select v-model="yi" size="small" style="width:100px"><el-option v-for="(y, i) in years" :key="y" :label="y" :value="i" /></el-select>
      <div class="grow" />
      <router-link :to="helpPath('method-pdu-age')" class="small" style="color:var(--fs-primary)">{{ $t('help.how_pdu') }}</router-link>
    </div>
    <div class="flow">
      <div class="step"><div class="n">1</div><div><div class="v">{{ fmt(stockTotal) }} {{ $t('w.pcs') }}</div><div class="l">{{ $t('w.step1', { a: ageLabel(sp.m0), b: ageLabel(sp.m1) }) }}</div></div></div>
      <div class="arrow">→</div>
      <div class="step"><div class="n">2</div><div><div class="v">{{ fmt(sp.biomass_t[yi], 1) }} т</div><div class="l">{{ $t('w.step2') }}</div></div></div>
      <div class="arrow">→</div>
      <div class="step"><div class="n">3</div><div><div class="v">{{ fmt(sp.pdu_t[yi], 1) }} т</div><div class="l">{{ $t('w.step3', { t: fmt(sp.distributed_t[yi], 1), n: sp.iterations[yi] }) }}</div></div></div>
      <div class="arrow">→</div>
      <div class="step hi"><div class="n">4</div><div><div class="v">{{ fmt(sp.pieces_total[yi]) }} {{ $t('w.pcs') }}</div><div class="l">{{ $t('w.step4') }} · {{ sp.stop_reason[yi] }}</div></div></div>
    </div>
    <div class="grid12" style="margin-top:10px">
      <div style="grid-column: span 6"><EChart :option="opt" height="280px" /></div>
      <div style="grid-column: span 6">
        <el-table :data="rows" size="small" border max-height="290">
          <el-table-column prop="age" :label="$t('w.age')" width="72" />
          <el-table-column :label="$t('w.stock_pcs')" align="right"><template #default="{ row }">{{ fmt(row.stock) }}</template></el-table-column>
          <el-table-column :label="$t('w.weight_g')" align="right"><template #default="{ row }">{{ fmt(row.weight, 1) }}<sup v-if="row.filled" :title="$t('w.weight_filled')">*</sup></template></el-table-column>
          <el-table-column :label="$t('w.pdu_pcs')" align="right"><template #default="{ row }">{{ fmt(row.pieces) }}</template></el-table-column>
          <el-table-column :label="$t('w.pdu_t')" align="right"><template #default="{ row }">{{ fmt(row.tonnes, 2) }}</template></el-table-column>
          <el-table-column :label="$t('w.exploitation')" align="right"><template #default="{ row }">{{ row.exploitation == null ? '—' : fmt(row.exploitation * 100, 1) + ' %' }}<el-tag v-if="row.capped" size="small" type="warning" style="margin-left:4px">75 %</el-tag></template></el-table-column>
        </el-table>
      </div>
    </div>
    <div class="small muted" style="margin-top:6px">{{ $t('w.pdu_hint', { cap: fmt((data.payload.cap || 0.75) * 100, 0) }) }}</div>
  </div>
</template>
<script setup>
import { useI18n } from 'vue-i18n'
import { computed, ref, watch } from 'vue'
import EChart from '../components/EChart.vue'
import { CHART } from '../theme'
import { base, fmt } from '../components/charts'
import { useSpecies } from './useSpecies'
import { helpPath } from '../cabinets'
const p = defineProps({ data: Object, filters: Object })
const { t } = useI18n()
const all = computed(() => p.data?.payload?.species || {})
const years = computed(() => p.data?.payload?.years || [])
const { list, chosen } = useSpecies(p, () => Object.keys(all.value))
const sp = computed(() => all.value[chosen.value])
const yi = ref(0)
watch(years, (y) => { yi.value = Math.max(0, y.length - 1) }, { immediate: true })
const ageLabel = (a) => `${a - 1}–${a}`
const rows = computed(() => {
  const b = sp.value.by_year[yi.value]
  return sp.value.ages.map((a, i) => ({ age: ageLabel(a), stock: b.stock[i], weight: b.weight[i], pieces: b.pieces[i], tonnes: b.tonnes[i],
    exploitation: b.exploitation[i], capped: b.capped[i], filled: sp.value.weight_filled[i], mature: a >= sp.value.m0 }))
})
const stockTotal = computed(() => rows.value.filter((r) => r.mature).reduce((a, r) => a + (r.stock || 0), 0))
const opt = computed(() => {
  const b = sp.value.by_year[yi.value]
  const bio = sp.value.ages.map((a, i) => (b.stock[i] == null || b.weight[i] == null ? null : (b.stock[i] * b.weight[i]) / 1e6))
  return base({ x: rows.value.map((r) => r.age), type: 'bar', yName: 'т', xName: t('w.age_years'), series: [
    { name: t('w.biomass'), values: bio, extra: { itemStyle: { color: CHART.background } } },
    { name: t('w.pdu'), values: b.tonnes, extra: { itemStyle: { color: CHART.highlight } } }] })
})
</script>
<style scoped>
.flow { display: flex; align-items: stretch; gap: 6px; flex-wrap: wrap; }
.step { flex: 1; min-width: 170px; display: flex; gap: 8px; border: 1px solid var(--fs-line); border-radius: 8px; padding: 8px 10px; background: var(--fs-card-soft); }
.step.hi { background: var(--fs-selected); border-color: var(--fs-primary-soft); }
.step .n { width: 22px; height: 22px; border-radius: 50%; background: var(--fs-primary); color: var(--fs-on-primary); display: grid; place-items: center; font-size: 12px; flex: none; }
.step .v { font-weight: 650; font-size: 16px; font-variant-numeric: tabular-nums; }
.step .l { color: var(--fs-muted); font-size: 12px; line-height: 1.3; }
.arrow { align-self: center; color: var(--fs-muted); font-size: 18px; }
</style>
