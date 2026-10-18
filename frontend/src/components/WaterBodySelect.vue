<template>
  <el-select :model-value="modelValue" filterable :placeholder="$t('common.water_body')" :clearable="clearable" style="width:260px"
             @update:model-value="$emit('update:modelValue', $event)">
    <el-option v-for="w in list" :key="w.code" :label="tr(w, 'name')" :value="w.code" />
  </el-select>
</template>
<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api'
import { tr } from '../i18n'
defineProps({ modelValue: String, clearable: Boolean })
defineEmits(['update:modelValue'])
const list = ref([])
onMounted(async () => {
  const r = await api.get('data-model', '/entities/water_bodies/records')
  list.value = r.map((x) => x.values).sort((a, b) => a.name_ru.localeCompare(b.name_ru))
})
</script>
