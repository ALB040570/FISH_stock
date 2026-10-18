<template>
  <div v-if="sp">
    <div class="row" style="margin-bottom:6px">
      <el-select v-model="chosen" size="small" style="width:150px"><el-option v-for="s in list" :key="s" :label="s" :value="s" /></el-select>
      <span class="small muted">
        {{ $t('w.model') }}: {{ sp.meta?.mode_title }} · R̂ max {{ fmt(sp.meta?.rhat_X_max, 3) }} · {{ $t('w.divergences') }} {{ sp.meta?.divergences ?? '—' }}
      </span>
      <el-tag v-if="sp.meta?.rhat_X_max > 1.05" type="warning" size="small">{{ $t('w.not_converged') }}</el-tag>
    </div>
    <EChart :option="opt" height="330px" />
    <div class="small muted">{{ $t('w.band_hint') }}</div>
  </div>
</template>
<script setup>
import { useI18n } from 'vue-i18n'
import { computed } from 'vue'
import EChart from '../components/EChart.vue'
import { band, fmt } from '../components/charts'
import { useSpecies } from './useSpecies'
const p = defineProps({ data: Object, filters: Object })
const { t } = useI18n()
const all = computed(() => p.data?.payload?.species || {})
const { list, chosen } = useSpecies(p, () => Object.keys(all.value))
const sp = computed(() => all.value[chosen.value])
const opt = computed(() => band({
  x: sp.value.years, q: sp.value.total_obs_q, name: t('w.bayes_median'), yName: 'шт',
  obs: [{ name: t('w.final_stock'), values: sp.value.data.final_total },
    { name: t('w.npc'), values: sp.value.data.npc_total }],
}))
</script>
