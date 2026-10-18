<template>
  <el-form label-width="190px">
    <template v-for="f in fields" :key="f.code">
      <el-form-item v-if="f.type !== 'geo_shape' && f.type !== 'geo_point'" :label="tr(f, 'title') + (f.unit ? ', ' + f.unit : '')" :required="f.required"
                    :error="errs[f.code]">
        <el-select v-if="f.type === 'enum'" v-model="v[f.code]" clearable style="width:100%">
          <el-option v-for="e in f.enum" :key="e.value" :label="tr(e, 'title') || e.value" :value="e.value" />
        </el-select>
        <el-select v-else-if="f.type === 'ref'" v-model="v[f.code]" clearable filterable style="width:100%">
          <el-option v-for="r in refs[f.ref_entity] || []" :key="r.key" :label="r.label" :value="r.key" />
        </el-select>
        <el-switch v-else-if="f.type === 'boolean'" v-model="v[f.code]" />
        <el-date-picker v-else-if="f.type === 'date'" v-model="v[f.code]" type="date" value-format="YYYY-MM-DD" format="DD.MM.YYYY" />
        <el-input v-else-if="f.type === 'text'" v-model="v[f.code]" type="textarea" :rows="3" />
        <el-input v-else v-model="v[f.code]" :disabled="f.code === 'code' && !isNew && locked" />
        <div v-if="f.hint" class="muted small">{{ f.hint }}</div>
      </el-form-item>
    </template>
    <el-form-item v-if="pointField" :label="tr(pointField, 'title')" :required="pointField.required" :error="errs[pointField.code]">
      <el-input :model-value="pointText" placeholder="48.73, 83.78" style="width:240px" @change="setPoint" />
    </el-form-item>
    <el-form-item v-if="pointField" label=" ">
      <GeoEditor :point="v[pointField.code]" :shape="shapeField ? v[shapeField.code] : null" style="width:100%"
                 @update:point="v[pointField.code] = $event" @update:shape="shapeField && (v[shapeField.code] = $event)" />
    </el-form-item>
  </el-form>
</template>
<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import { tr } from '../i18n'
import GeoEditor from './GeoEditor.vue'
const p = defineProps({ fields: Array, v: Object, errs: { type: Object, default: () => ({}) }, isNew: Boolean, locked: Boolean })
const refs = ref({})
const pointField = computed(() => p.fields.find((f) => f.type === 'geo_point'))
const shapeField = computed(() => p.fields.find((f) => f.type === 'geo_shape'))
const pointText = computed(() => { const pt = p.v[pointField.value?.code]; return pt ? `${pt[0]}, ${pt[1]}` : '' })
function setPoint(s) {
  const m = String(s).replace(/;/g, ',').split(/[,\s]+/).filter(Boolean).map(Number)
  p.v[pointField.value.code] = m.length === 2 && m.every((x) => !Number.isNaN(x)) ? m : s
}
onMounted(async () => {
  for (const f of p.fields.filter((x) => x.type === 'ref')) {
    const rs = await api.get('data-model', `/entities/${f.ref_entity}/records`)
    refs.value[f.ref_entity] = rs.map((r) => ({ key: r.values.code || r.id, label: r.values.name_ru || r.values.name || r.values.code || r.id }))
  }
})
</script>
