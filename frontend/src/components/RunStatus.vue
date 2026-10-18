<template><el-tag size="small" :type="types[status] || 'info'" :effect="status === 'running' ? 'dark' : 'light'">{{ $t('runs.st_' + status) }}</el-tag></template>
<script setup>
defineProps({ status: String })
const types = { queued: 'info', running: 'primary', done: 'success', failed: 'danger', cancelled: 'warning', pending: 'info', skipped: 'info', reused: 'success' }
</script>
