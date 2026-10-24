<template>
  <!-- «Можно ли верить запасу»: каждая проверка — маленький рисунок; жёлтым — только сработавшие правила -->
  <div class="tr-wrap" :style="{ maxHeight: height }">
    <div class="tr-head">
      <b>{{ data.trust.head }}</b>
      <span class="muted small">{{ data.trust.thresholds }}
        <router-link v-if="auth.can('dashboard.edit')" to="/design/signal-rules" class="edit" @click.stop>{{ $t('trust.edit_rules') }}</router-link></span>
    </div>
    <div class="tr hd">
      <div>{{ $t('trust.species') }}</div><div>{{ $t('trust.bounds') }}</div><div>{{ $t('trust.gears') }}</div>
      <div>{{ $t('trust.cohorts') }}</div><div>{{ $t('trust.sample') }}</div><div>{{ $t('trust.verdict') }}</div>
    </div>
    <div v-for="r in data.trust.rows" :key="r._code" class="tr row" :title="r.verdict.phrase" @click="$emit('species', r._code)">
      <div class="sp"><b>{{ r.species }}</b></div>
      <!-- запас на границах -->
      <div class="cell" @click.stop="$emit('open', r._code, r.bounds.to)">
        <span :class="{ w: r.bounds.hit }">{{ r.bounds.pct == null ? '—' : fmt(r.bounds.pct, r.bounds.pct > 0 && r.bounds.pct < 10 ? 1 : 0) + ' %' }}</span>
        <div class="bar"><div class="fill" :class="{ wbg: r.bounds.hit }" :style="{ width: Math.min(100, r.bounds.pct || 0) + '%' }" />
          <div v-if="r.bounds.on" class="tick" :style="{ left: r.bounds.thr + '%' }" /></div>
        <div class="sm">{{ r.bounds.ages ? r.bounds.ages + ' · ' + r.bounds.gear : '—' }}</div>
      </div>
      <!-- невод ÷ сеть -->
      <div class="cell" @click.stop="$emit('open', r._code, r.gears.to)">
        <template v-if="r.gears.one"><span class="muted">{{ $t('trust.one_gear') }}</span></template>
        <template v-else>
          <span :class="{ w: r.gears.hit }">{{ ratioText(r.gears.ratio) }}</span>
          <div class="bar"><div class="calm" :style="calmStyle(r.gears.thr)" /><div class="tick" style="left:50%" />
            <div v-if="r.gears.ratio" class="dot" :class="{ wbg: r.gears.hit }" :style="{ left: `calc(${logPos(r.gears.ratio)}% - 5px)` }" /></div>
          <div class="scale"><span>0,1</span><span>1</span><span>10</span></div>
          <div v-if="r.gears.median" class="sm">{{ $t('trust.usually') }} {{ ratioText(r.gears.median) }}</div>
        </template>
      </div>
      <!-- поколения -->
      <div class="cell" @click.stop="$emit('open', r._code, r.cohorts.to)">
        <div v-if="r.cohorts.n" class="sqs"><span v-for="(g, i) in r.cohorts.flags" :key="i" class="sq" :class="{ on: g, wbg: g && r.cohorts.hit }" /></div>
        <div class="sm" :class="{ w: r.cohorts.hit }">{{ r.cohorts.n ? $t('trust.of', { k: r.cohorts.k, n: r.cohorts.n }) : '—' }}</div>
        <div v-if="r.cohorts.best" class="sm" :title="$t('trust.best_full', { x: fmt(r.cohorts.best.x, 1), a: r.cohorts.best.from, b: r.cohorts.best.to_age, y0: r.cohorts.best.y0, y1: r.cohorts.best.y1 })">×{{ fmt(r.cohorts.best.x, 1) }} → {{ r.cohorts.best.to_age }}</div>
      </div>
      <!-- рыбы, подвергнутые биологической обработке -->
      <div class="cell" @click.stop="$emit('open', r._code, r.sample.to)">
        <span :class="{ w: r.sample.small || r.sample.pooled }">{{ r.sample.n == null ? '—' : fmt(r.sample.n, 0) + ' ' + $t('trust.fish') }}</span>
        <div class="sm" :class="{ w: r.sample.pooled || r.sample.r2low }">{{ r.sample.pooled ? $t('trust.pooled') : r.sample.r2 != null ? 'R² ' + fmt(r.sample.r2, 2) : '' }}</div>
      </div>
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
const logPos = (v) => Math.max(0, Math.min(100, (Math.log10(v) + 1) / 2 * 100))
const calmStyle = (R) => { const a = logPos(1 / R), b = logPos(R); return { left: a + '%', width: (b - a) + '%' } }
const ratioText = (v) => (v == null ? '—' : v >= 1 ? fmt(v, 1) + '×' : t('trust.net_more', { x: fmt(1 / v, 1) }))
</script>
<style scoped>
.tr-wrap { overflow: auto; }
.tr-head { margin-bottom: 4px; font-size: 14px; display: flex; flex-wrap: wrap; gap: 4px 14px; align-items: baseline; }
.small { font-size: 12px; }
.tr { display: grid; grid-template-columns: 72px minmax(90px, 1fr) minmax(110px, 1.2fr) minmax(110px, 1fr) 72px 162px; gap: 12px; align-items: center; padding: 4px 6px;
  border-top: 1px solid var(--fs-line-soft); font-size: 13px; }
.hd { color: var(--fs-muted); font-size: 12px; border-top: none; padding-top: 2px; }
.row { cursor: pointer; }
.row:hover { background: var(--fs-hover); }
.cell { min-width: 0; border-radius: 4px; padding: 2px 4px; margin: -2px -4px; }
.cell:hover { outline: 1px dashed var(--fs-line); }
.sm { font-size: 11.5px; color: var(--fs-muted); line-height: 1.3; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.w { color: var(--fs-warning); font-weight: 600; }
.bar { position: relative; height: 6px; background: var(--fs-line-soft); border-radius: 3px; margin: 4px 0 3px; }
.fill { position: absolute; left: 0; top: 0; bottom: 0; background: var(--fs-faint); border-radius: 3px; }
.tick { position: absolute; top: -3px; bottom: -3px; width: 1px; background: var(--fs-muted); }
.calm { position: absolute; top: 0; bottom: 0; background: color-mix(in srgb, var(--fs-success) 28%, transparent); border-radius: 3px; }
.scale { display: flex; justify-content: space-between; font-size: 10.5px; color: var(--fs-muted); line-height: 1.2; }
.dot { position: absolute; top: -2px; width: 10px; height: 10px; border-radius: 50%; background: var(--fs-muted); }
.wbg { background: var(--fs-warning) !important; }
.sqs { line-height: 0; max-width: 150px; }
.sq { display: inline-block; width: 7px; height: 7px; margin: 0 2px 2px 0; border-radius: 1px; background: var(--fs-line-soft); border: 1px solid var(--fs-line); }
.sq.on { background: var(--fs-faint); }
.vd { display: flex; align-items: center; gap: 6px; font-size: 12.5px; }
.vd.ok { color: var(--fs-success); }
.vd.warning .el-icon { color: var(--fs-warning); }
.edit { margin-left: 8px; }
@media (max-width: 1100px) { .tr { grid-template-columns: 90px 1fr 1fr; } .hd { display: none; } }
</style>
