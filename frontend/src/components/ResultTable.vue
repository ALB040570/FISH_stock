<template>
  <div>
    <div class="row" style="margin-bottom:6px">
      <el-input v-model="q" size="small" :placeholder="$t('common.search')" clearable style="width:260px" />
      <span class="muted small">{{ filtered.length }} / {{ table.rows.length }}</span>
      <div class="grow" />
      <el-button size="small" @click="csv">CSV</el-button>
    </div>
    <el-table :data="page" size="small" border max-height="560">
      <el-table-column v-for="c in table.columns" :key="c.code" :prop="c.code" :label="c.title + (c.unit && !String(c.title).includes(c.unit) ? ', ' + c.unit : '')" sortable
                       :min-width="110" :align="c.type === 'number' || c.type === 'integer' ? 'right' : 'left'">
        <template #default="{ row }">{{ cell(row[c.code], c) }}</template>
      </el-table-column>
    </el-table>
    <el-pagination v-model:current-page="pg" :page-size="100" :total="filtered.length" layout="prev, pager, next" style="margin-top:6px" />
  </div>
</template>
<script setup>
import { computed, ref, watch } from 'vue'
import { fmt } from './charts'
const p = defineProps({ table: Object })
const q = ref('')
const pg = ref(1)
watch(() => p.table, () => { pg.value = 1; q.value = '' })
const filtered = computed(() => (q.value ? p.table.rows.filter((r) => JSON.stringify(r).toLowerCase().includes(q.value.toLowerCase())) : p.table.rows))
const page = computed(() => filtered.value.slice((pg.value - 1) * 100, pg.value * 100))
function cell(v, c) {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'boolean') return v ? 'да' : 'нет'
  if (typeof v === 'number') return c.type === 'integer' || c.code === 'year' || /год/.test(c.title) ? v : fmt(v, 'auto')
  return v
}
function csv() {
  const head = p.table.columns.map((c) => c.title + (c.unit && !String(c.title).includes(c.unit) ? ', ' + c.unit : ''))
  const lines = [head, ...filtered.value.map((r) => p.table.columns.map((c) => r[c.code] ?? ''))]
  const txt = '﻿' + lines.map((l) => l.map((x) => `"${String(x).replace(/"/g, '""')}"`).join(';')).join('\n')
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob([txt], { type: 'text/csv;charset=utf-8' }))
  a.download = (p.table.title || 'table') + '.csv'; a.click()
}
</script>
