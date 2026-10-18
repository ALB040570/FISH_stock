<template>
  <div class="pf">
    <el-input-number v-if="p.type === 'integer' || p.type === 'number'" :model-value="modelValue" :min="p.min ?? undefined" :max="p.max ?? undefined"
                     :step="p.type === 'integer' ? 1 : 0.01" :precision="p.type === 'integer' ? 0 : undefined" :disabled="disabled" controls-position="right"
                     :placeholder="placeholder" style="width:180px" @update:model-value="emit('update:modelValue', $event ?? null)" />
    <el-select v-else-if="p.type === 'enum'" :model-value="modelValue" :disabled="disabled" style="width:360px" @update:model-value="emit('update:modelValue', $event)">
      <el-option v-for="e in p.enum" :key="e.value" :label="tr(e, 'title') || e.value" :value="e.value" />
    </el-select>
    <el-switch v-else-if="p.type === 'boolean'" :model-value="!!modelValue" :disabled="disabled" @update:model-value="emit('update:modelValue', $event)" />
    <el-select v-else-if="p.type === 'species_list'" :model-value="modelValue || []" multiple clearable :disabled="disabled" style="width:420px"
               :placeholder="placeholder || $t('common.all_species')" @update:model-value="emit('update:modelValue', $event)">
      <el-option v-for="s in species" :key="s.code" :label="s.name_ru" :value="s.code" />
    </el-select>
    <div v-else-if="p.type === 'year_map'">
      <div v-for="(row, i) in pairs" :key="i" class="row" style="margin-bottom:4px">
        <el-input-number v-model="row.k" :controls="false" placeholder="год" style="width:90px" @change="emitPairs" />
        <el-input-number v-model="row.v" :controls="false" :placeholder="p.unit || 'значение'" style="width:120px" @change="emitPairs" />
        <el-button text type="danger" size="small" @click="pairs.splice(i, 1); emitPairs()"><el-icon><Delete /></el-icon></el-button>
      </div>
      <el-button size="small" :disabled="disabled" @click="pairs.push({ k: null, v: null })"><el-icon><Plus /></el-icon>&nbsp;год</el-button>
    </div>
    <div v-else-if="p.type === 'species_map'" class="grid-sp">
      <div v-for="s in species" :key="s.code" class="row" style="gap:6px">
        <span style="width:90px">{{ s.name_ru }}</span>
        <el-input-number :model-value="(modelValue || {})[s.code] ?? null" :controls="false" :min="0" style="width:120px" :disabled="disabled"
                         @update:model-value="setSp(s.code, $event)" />
      </div>
    </div>
    <div v-else-if="p.type === 'species_year_map'">
      <div v-for="s in species" :key="s.code" class="row" style="gap:6px; margin-bottom:4px">
        <span style="width:90px">{{ s.name_ru }}</span>
        <el-input :model-value="syText(s.code)" placeholder="2025: 0.3; 2026: 0.25" style="width:340px" :disabled="disabled" @change="setSy(s.code, $event)" />
      </div>
    </div>
    <el-input v-else-if="p.type === 'profile'" type="textarea" :rows="3" :model-value="JSON.stringify(modelValue)" disabled />
    <el-input v-else :model-value="modelValue" :disabled="disabled" style="width:360px" @update:model-value="emit('update:modelValue', $event)" />
    <div v-if="p.description" class="muted small">{{ p.description }}</div>
  </div>
</template>
<script setup>
import { ref, watch } from 'vue'
import { tr } from '../i18n'
const props = defineProps({ p: Object, modelValue: [Number, String, Boolean, Array, Object], species: Array, disabled: Boolean, placeholder: String })
const emit = defineEmits(['update:modelValue'])
const pairs = ref([])
watch(() => props.modelValue, (v) => {
  if (props.p.type === 'year_map') pairs.value = Object.entries(v || {}).map(([k, x]) => ({ k: +k, v: x }))
}, { immediate: true })
function emitPairs() { emit('update:modelValue', Object.fromEntries(pairs.value.filter((r) => r.k && r.v != null).map((r) => [String(r.k), r.v]))) }
function setSp(code, v) { const o = { ...(props.modelValue || {}) }; if (v == null) delete o[code]; else o[code] = v; emit('update:modelValue', o) }
function syText(code) { return Object.entries((props.modelValue || {})[code] || {}).map(([y, v]) => `${y}: ${v}`).join('; ') }
function setSy(code, txt) {
  const o = { ...(props.modelValue || {}) }
  const m = {}
  for (const part of String(txt).split(/[;\n]/)) {
    const [y, v] = part.split(':').map((x) => x && x.trim().replace(',', '.'))
    if (y && v && !Number.isNaN(+v)) m[y] = +v
  }
  if (Object.keys(m).length) o[code] = m; else delete o[code]
  emit('update:modelValue', o)
}
</script>
<style scoped>
.grid-sp { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 4px 12px; }
</style>
