<template>
  <div>
    <el-table :data="modelValue" size="small" border>
      <el-table-column :label="$t('common.code')" width="150">
        <template #default="{ row }"><el-input v-model="row.code" size="small" :disabled="row.system" /></template></el-table-column>
      <el-table-column :label="$t('dict.title_ru')" min-width="170"><template #default="{ row }"><el-input v-model="row.title_ru" size="small" /></template></el-table-column>
      <el-table-column :label="$t('dict.title_kk')" min-width="150"><template #default="{ row }"><el-input v-model="row.title_kk" size="small" /></template></el-table-column>
      <el-table-column :label="$t('common.type')" width="170">
        <template #default="{ row }">
          <el-select v-model="row.type" size="small" :disabled="row.system">
            <el-option v-for="t in types" :key="t.code" :label="t.title" :value="t.code" />
          </el-select>
        </template></el-table-column>
      <el-table-column :label="$t('common.unit')" width="90"><template #default="{ row }"><el-input v-model="row.unit" size="small" /></template></el-table-column>
      <el-table-column :label="$t('common.required')" width="70" align="center"><template #default="{ row }"><el-checkbox v-model="row.required" /></template></el-table-column>
      <el-table-column :label="$t('common.details')" min-width="220">
        <template #default="{ row }">
          <div v-if="row.type === 'integer' || row.type === 'number'" class="row" style="gap:4px">
            <el-input-number v-model="row.min" size="small" :controls="false" :placeholder="$t('dict.min')" style="width:80px" />
            <el-input-number v-model="row.max" size="small" :controls="false" :placeholder="$t('dict.max')" style="width:80px" />
          </div>
          <el-select v-else-if="row.type === 'ref' || row.type === 'ref_list'" v-model="row.ref_entity" size="small" :placeholder="$t('dict.ref_entity')">
            <el-option v-for="e in entities" :key="e.code" :label="e.title_ru" :value="e.code" />
          </el-select>
          <el-input v-else-if="row.type === 'enum'" type="textarea" :rows="2" size="small" :model-value="enumText(row)"
                    :placeholder="$t('dict.enum_values')" @update:model-value="setEnum(row, $event)" />
          <el-checkbox v-if="allowUnique && row.type === 'string'" v-model="row.unique">{{ $t('dict.unique') }}</el-checkbox>
          <el-tag v-if="row.system" size="small" type="info" :title="$t('dict.system_hint')">{{ $t('dict.system') }}</el-tag>
        </template></el-table-column>
      <el-table-column width="50"><template #default="{ $index, row }">
        <el-button v-if="!row.system" text type="danger" size="small" @click="modelValue.splice($index, 1)"><el-icon><Delete /></el-icon></el-button>
      </template></el-table-column>
    </el-table>
    <el-button size="small" style="margin-top:8px" @click="modelValue.push({ code: '', title_ru: '', title_kk: '', type: 'string', required: false })">
      <el-icon><Plus /></el-icon>&nbsp;{{ $t('dict.new_field') }}</el-button>
    <span class="muted small" style="margin-left:10px">{{ $t('dict.system_hint') }}</span>
  </div>
</template>
<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api'
defineProps({ modelValue: Array, allowUnique: { type: Boolean, default: true } })
const types = ref([])
const entities = ref([])
function enumText(row) { return (row.enum || []).map((e) => (e.title_ru && e.title_ru !== e.value ? `${e.value} | ${e.title_ru}` : e.value)).join('\n') }
function setEnum(row, txt) {
  row.enum = txt.split('\n').map((s) => s.trim()).filter(Boolean).map((s) => {
    const [v, t] = s.split('|').map((x) => x.trim())
    return { value: v, title_ru: t || v }
  })
}
onMounted(async () => {
  const [t, e] = await Promise.all([api.get('data-model', '/field-types'), api.get('data-model', '/entities')])
  types.value = t; entities.value = e
})
</script>
