<template>
  <div class="widget card" :style="{ gridColumn: 'span ' + (widget.w || 6) }">
    <div class="wh">
      <div class="wt">{{ tr(widget, 'title') }}</div>
      <slot name="tools" />
    </div>
    <StateBlock :loading="loading" :error="error" :empty="!!data?.empty" :empty-text="emptyText" :retry="load">
      <template v-if="data">
        <div v-if="widget.type === 'text'" class="txt">{{ widget.options?.text }}</div>
        <div v-else-if="widget.type === 'kpi'" class="kpis">
          <div v-for="s in kpiValues" :key="s.name" class="kpi"><div class="v">{{ fmt(s.value, 'auto') }}</div><div class="l">{{ s.name || data.y_title }}</div></div>
        </div>
        <EChart v-else-if="widget.type === 'line' || widget.type === 'bar'" :option="chart" :height="(widget.h || 4) * 62 + 'px'" />
        <div v-else-if="widget.type === 'table'">
          <el-table :data="data.rows" size="small" :max-height="(widget.h || 5) * 62" border>
            <el-table-column v-for="c in visibleCols" :key="c.code" :prop="c.code" :label="c.title + (c.unit && !String(c.title).includes(c.unit) ? ', ' + c.unit : '')"
                             :min-width="c.type === 'number' ? 110 : 120" :align="c.type === 'number' || c.type === 'integer' ? 'right' : 'left'">
              <template #default="{ row }">{{ cell(row[c.code], c) }}</template>
            </el-table-column>
          </el-table>
          <div v-if="data.total > data.rows.length" class="muted small" style="margin-top:4px">{{ data.rows.length }} / {{ data.total }}</div>
        </div>
        <component :is="special" v-else-if="widget.type === 'special' && special" :data="data" :filters="filters" :options="widget.options" />
        <div v-if="data.meta?.run_id" class="muted small foot">
          <router-link :to="'/runs/' + data.meta.run_id">{{ data.meta.calculation_title }}</router-link>
          <span v-if="data.meta.is_main === false"> · {{ $t('monitoring.run_last') }}</span>
        </div>
      </template>
    </StateBlock>
  </div>
</template>
<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api'
import { tr } from '../i18n'
import EChart from '../components/EChart.vue'
import StateBlock from '../components/StateBlock.vue'
import { base, fmt } from '../components/charts'
import specials from './specials'

const p = defineProps({ widget: Object, filters: Object, species: Object })
const data = ref(null)
const loading = ref(false)
const error = ref(null)
const special = computed(() => specials[p.widget.options?.kind])
const { t, te } = useI18n()
const emptyText = computed(() => (data.value?.reason && te('w.reason_' + data.value.reason) ? t('w.reason_' + data.value.reason) : data.value?.message))

async function load() {
  if (p.widget.type === 'text') { data.value = {}; return }
  loading.value = true; error.value = null
  try {
    data.value = await api.post('dashboards', '/widgets/data', {
      source: p.widget.source, filters: p.filters, options: { ...(p.widget.options || {}), raw: p.widget.type === 'table' },
    })
  } catch (e) { error.value = e } finally { loading.value = false }
}
watch(() => [p.filters, p.widget], load, { deep: true, immediate: true })

const spName = (c) => p.species?.[c] || c
const chart = computed(() => {
  const d = data.value
  if (!d?.series) return null
  const series = d.series.map((s) => ({ ...s, name: s.name == null ? d.y_title : spName(s.name) }))
  return base({ x: d.x, series, type: p.widget.type, legend: series.length > 1, yName: p.widget.options?.unit || '' })
})
const kpiValues = computed(() => (data.value?.series || []).map((s) => ({ name: s.name, value: [...s.values].reverse().find((v) => v != null) })))
const visibleCols = computed(() => (data.value?.columns || []).filter((c) => !String(c.code).startsWith('_')).slice(0, 30))
function cell(v, c) {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'boolean') return v ? 'да' : 'нет'
  if (typeof v === 'number') return c.type === 'integer' || c.code === 'year' ? v : fmt(v, 'auto')
  return v
}
</script>
<style scoped>
.widget { min-width: 0; }
.wh { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; gap: 8px; }
.wt { font-weight: 600; }
.txt { white-space: pre-wrap; line-height: 1.5; }
.foot { margin-top: 6px; text-align: right; }
</style>
