<template><div ref="el" :style="{ width: '100%', height: height }" /></template>
<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { ECHARTS_THEME } from '../theme'
echarts.registerTheme('fishstock', ECHARTS_THEME)
const p = defineProps({ option: Object, height: { type: String, default: '320px' } })
const emit = defineEmits(['pick'])
const el = ref(null)
let chart = null
let ro = null
function render() { if (chart && p.option) chart.setOption(p.option, true) }
onMounted(() => {
  chart = echarts.init(el.value, 'fishstock', { renderer: 'canvas' })
  render()
  chart.on('click', (e) => emit('pick', e))
  ro = new ResizeObserver(() => chart && chart.resize())
  ro.observe(el.value)
})
watch(() => p.option, render, { deep: true })
// снимок графика для выгрузки PNG/PDF
function image() { return chart ? chart.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: '#fff' }) : null }
defineExpose({ image })
onBeforeUnmount(() => { ro && ro.disconnect(); chart && chart.dispose() })
</script>
