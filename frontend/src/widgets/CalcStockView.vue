<template>
  <!-- Представления результатов алгоритмов c–g на странице расчёта (решение № 70): любой расчёт, в том числе
       альтернативный. kind: likelihood — оценки запаса по ловам (c, d); gear_stock — годовой запас одним орудием (e, f);
       combined — окончательный запас, усреднённый по неводу и сети (g). -->
  <div v-if="list.length" class="csv">
    <div class="row bar">
      <el-select v-model="chosen" size="small" style="width:150px" data-test="csv-species"><el-option v-for="s in list" :key="s" :label="s" :value="s" /></el-select>
      <el-radio-group v-if="kind === 'likelihood'" v-model="scale" size="small">
        <el-radio-button value="log">{{ $t('csv.log') }}</el-radio-button>
        <el-radio-button value="linear">{{ $t('csv.linear') }}</el-radio-button>
      </el-radio-group>
      <el-radio-group v-else v-model="unit" size="small" data-test="csv-unit">
        <el-radio-button value="pcs">{{ $t('csv.u_pcs') }}</el-radio-button>
        <el-radio-button value="all">{{ $t('csv.u_all') }}</el-radio-button>
        <el-radio-button value="fishable">{{ $t('csv.u_fishable') }}</el-radio-button>
      </el-radio-group>
      <div class="grow" />
      <span v-if="methodTitle" class="muted small">{{ $t('csv.method') }}: {{ methodTitle }}</span>
    </div>

    <template v-if="kind === 'likelihood'">
      <EChart :option="dotsOpt" height="340px" />
      <div class="muted small note">
        {{ $t('csv.lk_note', { gear: gearName }) }}
        <template v-if="zeros && scale === 'log'"> {{ $t('csv.lk_zeros', { n: zeros }) }}</template>
      </div>
    </template>

    <template v-else>
      <EChart :option="yearsOpt" height="300px" />
      <div class="row bar" style="margin-top:10px">
        <b class="small">{{ $t('csv.structure') }}</b>
        <el-select v-model="yi" size="small" style="width:100px"><el-option v-for="(y, i) in years" :key="y" :label="y" :value="i" /></el-select>
      </div>
      <EChart :option="ageOpt" height="260px" />
      <div class="muted small note">{{ kind === 'combined' ? $t('csv.g_note') : $t('csv.st_note', { gear: gearName }) }}</div>
    </template>
  </div>
  <div v-else class="muted">{{ $t('csv.empty') }}</div>
</template>
<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import EChart from '../components/EChart.vue'
import { PALETTE, base, dotsChart } from '../components/charts'
import { CHART } from '../theme'
import { useSpecies } from './useSpecies'

const p = defineProps({ data: Object, filters: Object, options: Object })
const { t } = useI18n()
const kind = computed(() => (p.options?.kind || 'calc_likelihood').replace(/^calc_/, ''))
const pl = computed(() => p.data?.payload || {})
const st = computed(() => pl.value.stock || {})                      // g: stock_payload
const years = computed(() => (kind.value === 'combined' ? st.value.years : pl.value.years) || [])
const speciesList = () => {
  if (kind.value === 'likelihood') return pl.value.species || []
  if (kind.value === 'combined') return st.value.species_list || []
  return Object.keys(pl.value.species || {})
}
const { list, chosen } = useSpecies(p, speciesList)
const scale = ref('log')
const unit = ref('pcs')
const yi = ref(0)
watch(years, (y) => { yi.value = Math.max(0, (y?.length || 1) - 1) }, { immediate: true })

const GEAR = { 'невод': 'csv.g_seine', 'сеть': 'csv.g_net' }
const gearName = computed(() => t(GEAR[pl.value.gear] || 'csv.g_seine'))
const methodTitle = computed(() => {
  if (kind.value === 'gear_stock') return pl.value.method_title
  if (kind.value === 'combined') return st.value.method_titles?.[st.value.method] || st.value.method
  return ''
})
const ageLabel = (a) => `${a - 1}–${a}`
const TYPES = { scientific: 'csv.t_scientific', commercial: 'csv.t_commercial' }

// ---- c, d: оценки по ловам
const lk = computed(() => {
  const vals = pl.value.totals?.[chosen.value] || []
  const H = pl.value.hauls || {}
  const ys = years.value
  const pts = []
  const sum = ys.map(() => 0); const cnt = ys.map(() => 0)
  let zeros = 0
  vals.forEach((v, h) => {
    const k = ys.indexOf(H.year?.[h])
    if (v === null || v === undefined || k < 0) return
    sum[k] += v; cnt[k] += 1
    if (v <= 0) zeros += 1
    const type = H.type?.[h]
    pts.push([k, v, `${H.date?.[h] ?? ''}, ${H.place?.[h] ?? ''} (${TYPES[type] ? t(TYPES[type]) : type ?? ''})`])
  })
  return { pts, mean: sum.map((s, k) => (cnt[k] ? s / cnt[k] : null)), zeros }
})
const zeros = computed(() => lk.value.zeros)
const dotsOpt = computed(() => dotsChart({
  x: years.value, x_title: t('csv.year'), y_title: t('csv.pcs'),
  dots: [{ name: t('csv.haul_est'), points: lk.value.pts, c: 0 }],
  lines: [{ name: t('csv.haul_mean'), values: lk.value.mean, c: 1 }],
}, scale.value))

// ---- e, f, g: годовой запас
const sp = computed(() => (kind.value === 'combined' ? st.value.species?.[chosen.value] : pl.value.species?.[chosen.value]) || null)
const gBlock = computed(() => {                                      // g: блок способа расчёта (вариант «с учётом возрастов»)
  const v = sp.value?.variants?.with_ages || Object.values(sp.value?.variants || {})[0] || {}
  return v[st.value.method] || v.on_stock || {}
})
const MEAN = 'сеть+невод'
function seriesFor(gear) {
  if (kind.value !== 'combined') {
    if (unit.value === 'pcs') return sp.value?.totals || []
    return (unit.value === 'all' ? sp.value?.tonnes_all : sp.value?.tonnes_fishable) || []
  }
  if (unit.value === 'pcs') return gBlock.value.totals?.[gear] || []
  return pl.value.tonnes?.[chosen.value]?.[gear]?.[unit.value] || []
}
const yName = computed(() => (unit.value === 'pcs' ? t('csv.pcs') : t('csv.t')))
const yearsOpt = computed(() => {
  if (!sp.value) return {}
  if (kind.value !== 'combined') {
    return base({ x: years.value.map(String), type: 'bar', yName: yName.value, xName: t('csv.year'),
      series: [{ name: t('csv.stock_gear', { gear: gearName.value }), values: seriesFor(), extra: { itemStyle: { color: CHART.main } } }] })
  }
  const s = [
    { name: t('csv.stock_final'), values: seriesFor(MEAN), extra: { type: 'bar', itemStyle: { color: CHART.main } } },
    { name: t('csv.g_seine'), values: seriesFor('невод'), extra: { type: 'line', symbol: 'circle', lineStyle: { color: PALETTE[6] }, itemStyle: { color: PALETTE[6] } } },
    { name: t('csv.g_net'), values: seriesFor('сеть'), extra: { type: 'line', symbol: 'circle', lineStyle: { color: PALETTE[3] }, itemStyle: { color: PALETTE[3] } } },
  ]
  if (unit.value === 'pcs' && sp.value.npc) s.push({ name: t('csv.npc'), values: sp.value.npc, extra: { type: 'line', symbol: 'diamond', lineStyle: { type: 'dashed', color: CHART.highlight }, itemStyle: { color: CHART.highlight } } })
  return base({ x: years.value.map(String), type: 'bar', yName: yName.value, xName: t('csv.year'), series: s })
})
const ageOpt = computed(() => {
  if (!sp.value) return {}
  const ages = sp.value.ages || []
  const row = kind.value === 'combined' ? gBlock.value.by_age?.[MEAN]?.[yi.value] : sp.value.by_age?.[yi.value]
  return base({ x: ages.map(ageLabel), type: 'bar', yName: t('csv.pcs'), xName: t('csv.age_years'), legend: false,
    series: [{ name: t('csv.stock_pcs'), values: row || [], extra: { itemStyle: { color: CHART.background } } }] })
})
</script>
<style scoped>
.bar { gap: 10px; flex-wrap: wrap; margin-bottom: 8px; align-items: center; }
.note { margin-top: 6px; line-height: 1.45; }
</style>
