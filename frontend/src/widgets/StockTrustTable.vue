<template>
  <!-- «Сходятся ли оценки запаса»: три оценки на одной шкале, отношения, динамика, сходимость; жёлтым — только сработавшие правила -->
  <div class="tr-wrap" :style="{ maxHeight: height }">
    <div class="tr-head">
      <b>{{ data.stock_trust.head }}</b>
      <span class="muted small">{{ data.stock_trust.thresholds }}
        <router-link v-if="auth.can('dashboard.edit')" to="/design/signal-rules" class="edit" @click.stop>{{ $t('trust.edit_rules') }}</router-link></span>
    </div>
    <div class="legend small muted">
      <span><i class="mk band" /><i class="mk med" /> {{ $t('strust.model') }}</span>
      <span><i class="mk dia" /> {{ $t('strust.catch') }}</span>
      <span><i class="mk sq" /> {{ $t('strust.npc') }}</span>
    </div>
    <div class="tr hd">
      <div>{{ $t('trust.species') }}</div><div>{{ $t('strust.estimates') }}</div><div>{{ $t('strust.ratio') }}</div>
      <div>{{ $t('strust.change', { y: data.stock_trust.y0 }) }}</div><div>{{ $t('strust.conv') }}</div><div>{{ $t('trust.verdict') }}</div>
    </div>
    <div v-for="r in data.stock_trust.rows" :key="r._code" class="tr row" :title="r.verdict.phrase" @click="$emit('species', r._code)">
      <div class="sp"><b>{{ r.species }}</b></div>
      <template v-if="r.skipped">
        <div class="muted span4">{{ $t('strust.skipped') }}</div>
      </template>
      <template v-else>
        <!-- три оценки на логарифмической шкале -->
        <div class="cell" :title="r.est.text" @click.stop="$emit('open', r._code, r.est.to)">
          <div class="scale-l">
            <div v-if="r.est.lo && r.est.hi" class="band" :style="segStyle(r, r.est.lo, r.est.hi)" />
            <div v-if="r.est.median" class="mk med abs" :style="ptStyle(r, r.est.median)" />
            <div v-if="r.est.catch" class="mk dia abs" :class="{ wbg: r.ratio.hit_c }" :style="ptStyle(r, r.est.catch)" />
            <div v-if="r.est.npc" class="mk sq abs" :class="{ wbg: r.ratio.hit_n }" :style="ptStyle(r, r.est.npc)" />
          </div>
          <div class="sm">{{ $t('strust.model_short') }} {{ big(r.est.median) }}<template v-if="r.est.lo"> ({{ big(r.est.lo) }}–{{ big(r.est.hi) }})</template></div>
        </div>
        <!-- отношения -->
        <div class="cell" @click.stop="$emit('open', r._code, r.ratio.to)">
          <span :class="{ w: r.ratio.hit_c }">{{ ratioText(r.ratio.catch) }}</span>
          <div class="sm" :class="{ w: r.ratio.hit_n }">{{ $t('strust.npc_ratio') }} {{ ratioText(r.ratio.npc) }}</div>
        </div>
        <!-- динамика -->
        <div class="cell" :title="$t('strust.trend_tip', { m: mult(r.trend.model), c: mult(r.trend.catch), n: mult(r.trend.npc), y: data.stock_trust.y0 })" @click.stop="$emit('open', r._code, r.trend.to)">
          <svg class="spark" viewBox="0 0 100 28" preserveAspectRatio="none" aria-hidden="true">
            <polyline v-for="k in ['npc', 'catch', 'model']" :key="k" :points="sparkPoints(r.trend.spark, k)" :class="['ln', k, { wst: k === 'model' && r.trend.hit }]" />
          </svg>
          <div class="sm" :class="{ w: r.trend.hit }">{{ $t('strust.model_short') }} {{ mult(r.trend.model) }}</div>
        </div>
        <!-- модель: сходимость и (объяснение, без цвета) доля вылова в убыли -->
        <div class="cell" @click.stop="$emit('open', r._code, r.conv.ok ? r.fishing.to : r.conv.to)">
          <span :class="{ w: !r.conv.ok, ok: r.conv.ok }" :title="r.conv.all.join(', ')">{{ r.conv.text }}</span>
          <div v-if="r.conv.detail" class="sm w" :title="r.conv.detail">{{ r.conv.detail }}</div>
          <div v-if="r.fishing.pct != null" class="sm" :title="$t('strust.fishing_tip', { p: fmt(r.fishing.pct, 0), m: fmt(r.fishing.mean, 0) })">
            {{ $t('strust.fishing_short', { p: fmt(r.fishing.pct, 0) }) }}</div>
        </div>
      </template>
      <!-- вывод -->
      <div class="vd" :class="r.verdict.level">
        <el-icon v-if="r.verdict.level === 'ok'"><CircleCheck /></el-icon>
        <el-icon v-else-if="r.verdict.level === 'warning'"><WarningFilled /></el-icon>
        <span>{{ r.verdict.label }}</span>
      </div>
    </div>
  </div>
</template>
<script setup>
import { fmt } from '../components/charts'
import { useAuth } from '../store/auth'
import { useI18n } from 'vue-i18n'
defineProps({ data: Object, height: String })
defineEmits(['species', 'open'])
const auth = useAuth()
const { t } = useI18n()
const lg = (v) => Math.log10(v)
const pos = (r, v) => {
  const [a, b] = r.est.span || [1, 10]
  return Math.max(0, Math.min(100, ((lg(v) - lg(a)) / (lg(b) - lg(a))) * 100))
}
const ptStyle = (r, v) => ({ left: `calc(${pos(r, v)}% - 5px)` })
const segStyle = (r, lo, hi) => { const a = pos(r, lo), b = pos(r, hi); return { left: a + '%', width: Math.max(1.5, b - a) + '%' } }
const ratioText = (v) => (v == null ? '—' : fmt(v, v < 10 ? 2 : v < 100 ? 1 : 0) + '×')
const big = (v) => (v == null ? '—' : v >= 1e6 ? fmt(v / 1e6, v >= 1e8 ? 0 : 1) + ' ' + t('strust.mln') : v >= 1e3 ? fmt(v / 1e3, 0) + ' ' + t('strust.ths') : fmt(v, 0))
const mult = (v) => (v == null ? '—' : '×' + fmt(v, v < 10 ? 2 : v < 100 ? 1 : 0))
// мини-линии: все три ряда нормированы на свой первый год, общая логарифмическая ось
function sparkPoints(sp, key) {
  const all = ['model', 'catch', 'npc'].flatMap((k) => (sp[k] || []).filter((v) => v > 0))
  if (!all.length) return ''
  const lo = Math.min(...all.map(lg)), hi = Math.max(...all.map(lg))
  const vals = sp[key] || []
  const n = vals.length
  return vals.map((v, i) => (v > 0 ? `${(i / Math.max(1, n - 1)) * 100},${26 - ((lg(v) - lo) / Math.max(1e-9, hi - lo)) * 24}` : null))
    .filter(Boolean).join(' ')
}
</script>
<style scoped>
.tr-wrap { overflow: auto; }
.tr-head { margin-bottom: 2px; font-size: 14px; display: flex; flex-wrap: wrap; gap: 4px 14px; align-items: baseline; }
.legend { display: flex; gap: 14px; margin-bottom: 4px; align-items: center; }
.legend .mk { position: relative; display: inline-block; vertical-align: middle; margin-right: 2px; }
.small { font-size: 12px; }
.tr { display: grid; grid-template-columns: 64px minmax(130px, 1.5fr) 78px minmax(84px, 0.9fr) minmax(92px, 0.9fr) 124px; gap: 10px;
  align-items: center; padding: 5px 6px; border-top: 1px solid var(--fs-line-soft); font-size: 13px; }
.hd { color: var(--fs-muted); font-size: 12px; border-top: none; padding-top: 2px; }
.row { cursor: pointer; }
.row:hover { background: var(--fs-hover); }
.span4 { grid-column: span 4; }
.cell { min-width: 0; border-radius: 4px; padding: 2px 4px; margin: -2px -4px; }
.cell:hover { outline: 1px dashed var(--fs-line); }
.sm { font-size: 11.5px; color: var(--fs-muted); line-height: 1.3; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.w { color: var(--fs-warning); font-weight: 600; }
.ok { color: var(--fs-success); }
.scale-l { position: relative; height: 12px; background: var(--fs-line-soft); border-radius: 3px; margin: 3px 0 3px; }
.band { position: absolute; top: 2px; bottom: 2px; background: color-mix(in srgb, var(--fs-primary) 35%, transparent); border-radius: 3px; }
.mk { width: 10px; height: 10px; }
.mk.abs { position: absolute; top: 1px; }
.mk.med { border-radius: 50%; background: var(--fs-primary); }
.mk.dia { transform: rotate(45deg) scale(0.85); background: var(--fs-text); }
.mk.sq { background: var(--fs-muted); border: 1px solid var(--fs-card); }
.mk.band { width: 16px; height: 6px; border-radius: 3px; background: color-mix(in srgb, var(--fs-primary) 35%, transparent); }
.wbg { background: var(--fs-warning) !important; }
.spark { width: 100%; height: 26px; display: block; }
.ln { fill: none; stroke-width: 1.6; vector-effect: non-scaling-stroke; }
.ln.model { stroke: var(--fs-primary); stroke-width: 2.2; }
.ln.catch { stroke: var(--fs-text); }
.ln.npc { stroke: var(--fs-muted); stroke-dasharray: 3 2; }
.ln.wst { stroke: var(--fs-warning); }
.vd { display: flex; align-items: center; gap: 6px; font-size: 12.5px; }
.vd.ok { color: var(--fs-success); }
.vd.warning .el-icon { color: var(--fs-warning); }
.edit { margin-left: 8px; }
@media (max-width: 1100px) { .tr { grid-template-columns: 90px 1fr 1fr; } .hd { display: none; } .span4 { grid-column: span 2; } }
</style>
