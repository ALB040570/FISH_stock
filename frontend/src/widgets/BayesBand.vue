<template>
  <div v-if="sp">
    <div class="row" style="margin-bottom:6px">
      <el-select v-model="chosen" size="small" style="width:150px"><el-option v-for="s in list" :key="s" :label="s" :value="s" /></el-select>
      <span class="small muted">
        модель: {{ sp.meta?.mode_title }} · R̂ max {{ fmt(sp.meta?.rhat_X_max, 3) }} · расходимостей {{ sp.meta?.divergences ?? '—' }}
      </span>
      <el-tag v-if="sp.meta?.rhat_X_max > 1.05" type="warning" size="small">R̂ &gt; 1,05 — цепи не сошлись</el-tag>
    </div>
    <EChart :option="opt" height="330px" />
    <div class="small muted">Численность рыб 1–2 лет и старше, шт: медиана и интервалы 50 % / 95 % апостериорного распределения; точки — независимые оценки.</div>
  </div>
</template>
<script setup>
import { computed } from 'vue'
import EChart from '../components/EChart.vue'
import { band, fmt } from '../components/charts'
import { useSpecies } from './useSpecies'
const p = defineProps({ data: Object, filters: Object })
const all = computed(() => p.data?.payload?.species || {})
const { list, chosen } = useSpecies(p, () => Object.keys(all.value))
const sp = computed(() => all.value[chosen.value])
const opt = computed(() => band({
  x: sp.value.years, q: sp.value.total_obs_q, name: 'байесовская модель, медиана', yName: 'шт',
  obs: [{ name: 'окончательный запас по уловам', values: sp.value.data.final_total },
    { name: 'оценка НПЦ', values: sp.value.data.npc_total }],
}))
</script>
