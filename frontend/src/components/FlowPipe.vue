<template>
  <!-- «Труба» между плитками «Потока» (замечание заказчика 24.10.2026): только стрелка и кружки водоёмов цвета легенды;
       подпись и названия водоёмов — во всплывающей подсказке; кружок открывает водоём. На узком экране подпись видна. -->
  <div class="pipe" :data-pipe="stage">
    <el-tooltip placement="top" :show-after="120" popper-class="fs-pipe-tip" :disabled="!loaded">
      <template #content>
        <div class="tip-h">{{ label }}<template v-if="items.length">: {{ items.length }}</template></div>
        <div v-for="w in items" :key="w.code" class="tip-r"><i class="tip-dot" :style="{ background: color(w) }" /><span><b>{{ w.name }}</b> — {{ hint(w) }}</span></div>
        <div v-if="!items.length" class="tip-free">{{ $t('flow.free') }}</div>
      </template>
      <div class="pbody" tabindex="0" :aria-label="label + (items.length ? ': ' + items.length : '')">
        <span class="plabel">{{ label }}</span>
        <span v-if="items.length" class="pdots">
          <a v-for="w in items" :key="w.code" class="pdot" :href="href(w)"
            :aria-label="w.name + ' — ' + hint(w)" :style="{ background: color(w) }" />
        </span>
      </div>
    </el-tooltip>
    <div class="pline" aria-hidden="true"><el-icon><ArrowRight /></el-icon></div>
  </div>
</template>
<script setup>
defineProps({
  stage: { type: String, required: true },
  label: { type: String, required: true },
  items: { type: Array, default: () => [] },
  loaded: { type: Boolean, default: false },
  color: { type: Function, required: true },
  hint: { type: Function, required: true },
  href: { type: Function, required: true },
})
</script>
<style scoped>
.pipe { position: relative; display: flex; align-items: center; justify-content: center; padding: 0 6px; min-width: 0; }
.pipe::before { content: ''; position: absolute; left: 0; right: 0; top: 50%; border-top: 2px dashed var(--fs-primary-2); opacity: .6; z-index: 0; }
.pbody { position: relative; z-index: 1; display: flex; align-items: center; justify-content: center; width: 100%; min-height: 44px;
  outline: none; border-radius: 12px; }
.pbody:focus-visible { box-shadow: 0 0 0 2px var(--fs-primary-2); }
.plabel { display: none; }
.pdots { display: flex; flex-wrap: wrap; justify-content: center; gap: 6px; max-width: 100%; padding: 4px 6px; }
.pdot { width: 14px; height: 14px; border-radius: 50%; display: block; flex: none; box-sizing: border-box;
  border: 2px solid var(--fs-bg); box-shadow: 0 0 0 1px var(--fs-line); transition: transform .12s; }
.pdot:hover, .pdot:focus-visible { transform: scale(1.35); outline: none; }
.pline { position: absolute; right: -4px; top: 50%; transform: translateY(-50%); color: var(--fs-primary-2); z-index: 2; display: flex; }
@media (max-width: 900px) {
  .pipe { padding: 12px 0 18px; }
  .pipe::before { left: 50%; right: auto; top: 0; bottom: 0; border-top: none; border-left: 2px dashed var(--fs-line); }
  .pbody { flex-direction: column; gap: 6px; width: auto; padding: 6px 12px; background: var(--fs-bg); }
  .plabel { display: block; font-size: 12px; color: var(--fs-muted); text-align: center; }
  .pline { right: auto; left: 50%; top: auto; bottom: -2px; transform: translateX(-50%) rotate(90deg); }
}
</style>
<style>
.fs-pipe-tip { max-width: 340px; }
.fs-pipe-tip .tip-h { font-weight: 600; margin-bottom: 4px; }
.fs-pipe-tip .tip-h::first-letter { text-transform: uppercase; }
.fs-pipe-tip .tip-r { display: flex; gap: 6px; align-items: baseline; line-height: 1.4; margin-top: 2px; }
.fs-pipe-tip .tip-dot { width: 8px; height: 8px; border-radius: 50%; flex: none; display: inline-block; }
.fs-pipe-tip .tip-free { opacity: .8; }
</style>
