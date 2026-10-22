<template>
  <div>
    <div ref="el" class="geo" />
    <div class="row" style="margin-top:6px">
      <input ref="file" type="file" accept=".geojson,.json,.kml" style="display:none" @change="onFile" />
      <el-button size="small" @click="$refs.file.click()"><el-icon><Upload /></el-icon>&nbsp;{{ $t('dict.load_shape') }}</el-button>
      <el-button size="small" :disabled="!shape" @click="clearShape">{{ $t('dict.clear_shape') }}</el-button>
      <el-button size="small" :disabled="!shape" @click="toCentroid">{{ $t('dict.centroid') }}</el-button>
      <span class="muted small">{{ err }}</span>
    </div>
    <div class="muted small" style="margin-top:4px">{{ $t('dict.point_hint') }} {{ $t('dict.shape_hint') }}</div>
  </div>
</template>
<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import L from 'leaflet'
import '@geoman-io/leaflet-geoman-free'
import '@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css'
import { api } from '../api'
import { MAP, themeMode } from '../theme'

const p = defineProps({ point: Array, shape: Object })
const emit = defineEmits(['update:point', 'update:shape'])
const el = ref(null)
const err = ref('')
let map, marker, shapeLayer

function drawShape(g) {
  if (shapeLayer) { shapeLayer.remove(); shapeLayer = null }
  if (!g) return
  shapeLayer = L.geoJSON(g, { style: { color: MAP.shape, weight: 2, fillOpacity: 0.25 } }).addTo(map)
  shapeLayer.eachLayer((l) => l.on('pm:edit', () => emit('update:shape', shapeLayer.toGeoJSON().features[0].geometry)))
}
function drawPoint(pt) {
  if (marker) marker.remove()
  if (!pt) return
  marker = L.marker([pt[0], pt[1]], { draggable: true }).addTo(map)
  marker.on('dragend', () => { const ll = marker.getLatLng(); emit('update:point', [+ll.lat.toFixed(5), +ll.lng.toFixed(5)]) })
}
watch(themeMode, () => shapeLayer && shapeLayer.setStyle({ color: MAP.shape }))
function clearShape() { emit('update:shape', null) }
function toCentroid() {
  const c = shapeLayer.getBounds().getCenter()
  emit('update:point', [+c.lat.toFixed(5), +c.lng.toFixed(5)])
}
async function onFile(e) {
  err.value = ''
  try {
    const j = await api.upload('data-model', '/geo/parse', { file: e.target.files[0] })
    emit('update:shape', j.shape)
    if (!p.point) emit('update:point', j.point)
  } catch (x) { err.value = x.message }
  e.target.value = ''
}
onMounted(async () => {
  await nextTick()
  map = L.map(el.value).setView(p.point || [48.2, 67.5], p.point ? 7 : 4)
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 15, attribution: '© OpenStreetMap' }).addTo(map)
  map.pm.addControls({ position: 'topleft', drawMarker: false, drawCircleMarker: false, drawPolyline: false, drawRectangle: false,
    drawCircle: false, drawText: false, cutPolygon: false, rotateMode: false, dragMode: false })
  map.pm.setLang('ru')
  map.on('pm:create', (e) => { const g = e.layer.toGeoJSON().geometry; e.layer.remove(); emit('update:shape', g) })
  map.on('click', (e) => emit('update:point', [+e.latlng.lat.toFixed(5), +e.latlng.lng.toFixed(5)]))
  drawShape(p.shape); drawPoint(p.point)
  if (shapeLayer) map.fitBounds(shapeLayer.getBounds(), { maxZoom: 9 })
  setTimeout(() => map.invalidateSize(), 200)
})
watch(() => p.shape, drawShape)
watch(() => p.point, drawPoint)
onBeforeUnmount(() => map && map.remove())
</script>
<style scoped>
.geo { height: 380px; border-radius: 6px; border: 1px solid var(--fs-line); }
</style>
