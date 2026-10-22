<template>
  <div class="tt-wrap" :style="{ maxHeight: height }">
    <table class="tt">
      <thead><tr><th v-for="c in data.columns" :key="c.code" :class="{ num: c.type !== 'string' && c.type !== 'spark' }">{{ c.title }}</th></tr></thead>
      <tbody>
        <tr v-for="r in data.rows" :key="r._code" @click="$emit('species', r._code)">
          <td class="sp"><b>{{ r.species }}</b></td>
          <td class="spark"><svg v-if="r.spark?.length > 1" viewBox="0 0 120 30" preserveAspectRatio="none">
            <polyline :points="line(r.spark)" fill="none" stroke="currentColor" stroke-width="1.8" vector-effect="non-scaling-stroke" />
            <circle :cx="120" :cy="lastY(r.spark)" r="2.6" fill="currentColor" />
          </svg><span v-else class="muted">—</span></td>
          <td class="num" :class="r._levels?.cpue_change">{{ signed(r.cpue_change) }}</td>
          <td class="num">{{ val(r.share) }}</td>
          <td class="num">{{ val(r.mature) }}</td>
          <td class="num" :class="r._levels?.weight">{{ signed(r.weight) }}</td>
          <td class="num" :class="r._levels?.quota">{{ signed(r.quota) }}</td>
          <td class="num"><span v-if="r.signals" class="badge">{{ r.signals }}</span><span v-else class="muted">0</span></td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
<script setup>
import { fmt } from '../components/charts'
defineProps({ data: Object, height: String })
defineEmits(['species'])
function scale(a) {
  const lo = Math.min(...a), hi = Math.max(...a)
  return (v) => (hi === lo ? 15 : 27 - ((v - lo) / (hi - lo)) * 24)
}
function line(a) { const y = scale(a); return a.map((v, i) => `${(i / (a.length - 1)) * 120},${y(v)}`).join(' ') }
function lastY(a) { return scale(a)(a[a.length - 1]) }
const val = (v) => (v === null || v === undefined ? '—' : fmt(v, 'auto'))
const signed = (v) => (v === null || v === undefined ? '—' : (v > 0 ? '+' : '') + fmt(v, 0))
</script>
<style scoped>
.tt-wrap { overflow: auto; }
.tt { width: 100%; border-collapse: collapse; font-size: 13.5px; }
th { text-align: left; font-weight: 600; font-size: 12px; color: var(--fs-muted); padding: 6px 10px; border-bottom: 1px solid var(--fs-line);
  position: sticky; top: 0; background: var(--fs-card); }
td { padding: 7px 10px; border-bottom: 1px solid var(--fs-line-soft); }
tbody tr { cursor: pointer; }
tbody tr:hover td { background: var(--fs-hover); }
.num { text-align: right; white-space: nowrap; }
.spark { width: 150px; color: var(--fs-primary-2); }
.spark svg { width: 130px; height: 30px; display: block; overflow: visible; }
.down { color: var(--fs-danger); font-weight: 600; }
.up { color: var(--fs-success); font-weight: 600; }
.badge { display: inline-block; min-width: 20px; padding: 0 6px; border-radius: 10px; background: var(--fs-warning); color: var(--fs-on-primary);
  font-size: 12px; text-align: center; }
</style>
