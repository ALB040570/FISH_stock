<template><div ref="el" :style="{ width: '100%', height: height }" /></template>
<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
const p = defineProps({ option: Object, height: { type: String, default: '320px' } })
const el = ref(null)
let chart = null
let ro = null
function render() { if (chart && p.option) chart.setOption(p.option, true) }
onMounted(() => {
  chart = echarts.init(el.value, null, { renderer: 'canvas' })
  render()
  ro = new ResizeObserver(() => chart && chart.resize())
  ro.observe(el.value)
})
watch(() => p.option, render, { deep: true })
onBeforeUnmount(() => { ro && ro.disconnect(); chart && chart.dispose() })
</script>
