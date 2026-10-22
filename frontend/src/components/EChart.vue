<template><div ref="el" :style="{ width: '100%', height: height }" /></template>
<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { CSS, echartsTheme, themeMode } from '../theme'
// обе схемы регистрируются один раз; при переключении схемы график пересоздаётся с другой темой
echarts.registerTheme('fishstock-light', echartsTheme('light'))
echarts.registerTheme('fishstock-dark', echartsTheme('dark'))
const p = defineProps({ option: Object, height: { type: String, default: '320px' } })
const emit = defineEmits(['pick'])
const el = ref(null)
let chart = null
let ro = null
function render() { if (chart && p.option) chart.setOption(p.option, true) }
function create() {
  chart = echarts.init(el.value, 'fishstock-' + themeMode.value, { renderer: 'canvas' })
  render()
  chart.on('click', (e) => emit('pick', e))
}
onMounted(() => {
  create()
  ro = new ResizeObserver(() => chart && chart.resize())
  ro.observe(el.value)
})
watch(() => p.option, render, { deep: true })
watch(themeMode, () => { if (!chart) return; chart.dispose(); create() })
// снимок графика для выгрузки PNG/PDF
function image() { return chart ? chart.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: CSS.card }) : null }
defineExpose({ image })
onBeforeUnmount(() => { ro && ro.disconnect(); chart && chart.dispose() })
</script>
