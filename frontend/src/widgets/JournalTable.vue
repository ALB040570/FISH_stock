<template>
  <div class="jr">
    <div class="jf">
      <el-select v-model="f.years" multiple collapse-tags clearable size="small" :placeholder="$t('mon.j_years')" style="width:150px">
        <el-option v-for="y in [...data.journal.years].reverse()" :key="y" :label="y" :value="y" />
      </el-select>
      <el-select v-model="f.months" multiple collapse-tags clearable size="small" :placeholder="$t('mon.j_months')" style="width:140px">
        <el-option v-for="m in data.journal.months" :key="m" :label="MONTHS[m - 1]" :value="m" />
      </el-select>
      <el-select v-model="f.gears" multiple collapse-tags clearable size="small" :placeholder="$t('mon.j_gear')" style="width:140px">
        <el-option v-for="g in data.journal.gears" :key="g" :label="g" :value="g" />
      </el-select>
      <el-select v-model="f.types" multiple collapse-tags clearable size="small" :placeholder="$t('mon.j_type')" style="width:170px">
        <el-option v-for="g in data.journal.types" :key="g" :label="g" :value="g" />
      </el-select>
      <el-select v-model="f.places" multiple collapse-tags filterable clearable size="small" :placeholder="$t('mon.j_places')" style="width:190px">
        <el-option v-for="g in data.journal.places" :key="g" :label="g" :value="g" />
      </el-select>
      <el-input v-model="f.q" size="small" clearable :placeholder="$t('mon.j_search')" prefix-icon="Search" style="width:150px" />
      <el-button size="small" link @click="resetF">{{ $t('mon.j_reset') }}</el-button>
      <span class="grow" />
      <el-button size="small" @click="exportX"><el-icon><Download /></el-icon>&nbsp;{{ $t('mon.j_export') }}</el-button>
    </div>
    <div class="muted small" style="margin:4px 0">{{ $t('mon.j_shown', { n: rows.length, m: data.rows.length }) }}</div>
    <el-table :data="page" size="small" border :max-height="height" :summary-method="summary" show-summary
              :default-sort="{ prop: 'date', order: null }" @sort-change="onSort">
      <el-table-column v-for="c in data.columns" :key="c.code" :prop="c.code" :label="c.title" sortable="custom"
                       :min-width="c.code === 'place' ? 150 : c.code === 'catch_type' ? 130 : c.species ? 82 : 92"
                       :align="['number', 'integer'].includes(c.type) ? 'right' : 'left'" :class-name="c.selected ? 'selcol' : ''"
                       :label-class-name="c.selected ? 'selcol' : ''" :fixed="c.code === 'year' ? 'left' : false">
        <template #default="{ row }">{{ cell(row[c.code], c) }}</template>
      </el-table-column>
    </el-table>
    <el-pagination v-if="rows.length > size" v-model:current-page="pageNo" :page-size="size" :total="rows.length" layout="prev, pager, next"
                   small style="margin-top:8px" />
  </div>
</template>
<script setup>
import { computed, inject, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { downloadPost } from '../api'
import { fmt } from '../components/charts'
const p = defineProps({ data: Object, height: String, title: String })
const { t, locale } = useI18n()
const board = inject('board', null)
const MONTHS_RU = ['январь', 'февраль', 'март', 'апрель', 'май', 'июнь', 'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь']
const MONTHS_KK = ['қаңтар', 'ақпан', 'наурыз', 'сәуір', 'мамыр', 'маусым', 'шілде', 'тамыз', 'қыркүйек', 'қазан', 'қараша', 'желтоқсан']
const MONTHS = computed(() => (locale.value === 'kk' ? MONTHS_KK : MONTHS_RU))
const f = reactive({ years: [], months: [], gears: [], types: [], places: [], q: '' })
function resetF() { Object.assign(f, { years: [], months: [], gears: [], types: [], places: [], q: '' }) }
// фильтр из графика («Показать строки данных»)
if (board?.journalPreset) {
  watch(board.journalPreset, (w) => {
    if (!w) return
    resetF()
    if (w.year != null) f.years = [Number(w.year)]
    if (w.month != null) f.months = [Number(w.month)]
    if (w.place) f.places = [w.place]
    if (w.gear_kind) f.gears = [...new Set(p.data.rows.filter((r) => r._gear_kind === w.gear_kind).map((r) => r.gear))]
    if (w.catch_type) f.types = [...new Set(p.data.rows.filter((r) => r._catch_type === w.catch_type).map((r) => r.catch_type))]
    board.journalPreset.value = null
  }, { immediate: true })
}
const sort = ref({ prop: null, order: null })
function onSort(s) { sort.value = { prop: s.prop, order: s.order } }
const rows = computed(() => {
  const q = f.q.trim().toLowerCase()
  let r = p.data.rows.filter((x) => (!f.years.length || f.years.includes(x.year)) && (!f.months.length || f.months.includes(x.month)) &&
    (!f.gears.length || f.gears.includes(x.gear)) && (!f.types.length || f.types.includes(x.catch_type)) &&
    (!f.places.length || f.places.includes(x.place)) && (!q || `${x.place} ${x.date} ${x.gear} ${x.catch_type}`.toLowerCase().includes(q)))
  const { prop, order } = sort.value
  if (prop && order) {
    const k = prop === 'date' ? '_iso' : prop
    const dir = order === 'ascending' ? 1 : -1
    r = [...r].sort((a, b) => ((a[k] ?? -Infinity) > (b[k] ?? -Infinity) ? dir : (a[k] ?? -Infinity) < (b[k] ?? -Infinity) ? -dir : 0))
  }
  return r
})
const size = 50
const pageNo = ref(1)
watch(rows, () => { pageNo.value = 1 })
const page = computed(() => rows.value.slice((pageNo.value - 1) * size, pageNo.value * size))
function summary({ columns }) {
  return columns.map((col, i) => {
    if (i === 0) return t('mon.j_total')
    const c = p.data.columns.find((x) => x.code === col.property)
    if (!c) return ''
    if (c.code === 'date') return `${rows.value.length} ${t('mon.j_hauls')}`
    if (!c.species) return ''
    const s = rows.value.reduce((a, r) => a + (r[c.code] || 0), 0)
    return fmt(s, 0)
  })
}
function cell(v, c) {
  if (v === null || v === undefined || v === '') return '—'
  if (typeof v === 'number') return c.type === 'integer' || c.code === 'year' ? v : fmt(v, 'auto')
  return v
}
async function exportX() {
  try {
    const cols = p.data.columns
    await downloadPost('dashboards', '/widgets/export.xlsx', { title: p.title || 'Журнал ловов', columns: cols, rows: rows.value,
      sources: p.data.sources || [], notes: [], filter_label: '' }, `${(p.title || 'journal').replace(/[^\p{L}\p{N}]+/gu, '_')}.xlsx`)
  } catch (e) { ElMessage.error(e.message || String(e)) }
}
</script>
<style scoped>
.jf { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.grow { flex: 1; }
:deep(.selcol) { background: var(--fs-selected) !important; font-weight: 600; }
</style>
