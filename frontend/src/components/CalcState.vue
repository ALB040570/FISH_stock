<template>
  <span class="cs">
    <el-tag size="small" :type="types[calc.state] || 'info'" :effect="calc.state === 'running' ? 'dark' : 'light'">
      {{ $t('calcs.st_' + (calc.state || 'new')) }}<template v-if="calc.state === 'running' && pct !== null"> · {{ pct }} %</template>
    </el-tag>
    <el-tooltip v-if="calc.stale?.length" :content="calc.stale.join('; ')" placement="top">
      <el-tag size="small" type="warning" effect="plain" data-test="stale">{{ $t('calcs.stale') }}</el-tag>
    </el-tooltip>
  </span>
</template>
<script setup>
import { computed } from 'vue'
const p = defineProps({ calc: Object })
const types = { new: 'info', queued: 'info', running: 'primary', done: 'success', failed: 'danger', cancelled: 'warning' }
const pct = computed(() => (typeof p.calc?.progress?.fraction === 'number' ? Math.round(p.calc.progress.fraction * 100) : null))
</script>
<style scoped>
.cs { display: inline-flex; gap: 4px; flex-wrap: wrap; }
</style>
