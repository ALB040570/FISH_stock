<template>
  <div v-if="loading" class="state"><el-icon class="is-loading" :size="22"><Loading /></el-icon><div>{{ $t('common.loading') }}</div></div>
  <el-alert v-else-if="error" type="error" :closable="false" show-icon :title="String(error.message || error)">
    <template v-if="error.details" #default>
      <ul style="margin:6px 0 0; padding-left:18px"><li v-for="(d, i) in details" :key="i">{{ d }}</li></ul>
    </template>
    <el-button v-if="retry" size="small" style="margin-top:6px" @click="retry">{{ $t('common.retry') }}</el-button>
  </el-alert>
  <div v-else-if="empty" class="state"><el-icon :size="22"><Box /></el-icon><div>{{ emptyText || $t('common.empty') }}</div><slot name="empty" /></div>
  <slot v-else />
</template>
<script setup>
import { computed } from 'vue'
const p = defineProps({ loading: Boolean, error: [Object, String, Error], empty: Boolean, emptyText: String, retry: Function })
const details = computed(() => {
  const d = p.error?.details
  if (!d) return []
  if (Array.isArray(d)) return d.map((x) => (typeof x === 'string' ? x : x.message || JSON.stringify(x)))
  return [typeof d === 'string' ? d : JSON.stringify(d)]
})
</script>
