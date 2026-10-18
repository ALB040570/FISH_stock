<template>
  <div>
    <el-tabs v-if="tabs.length > 1 || editing" v-model="tab" class="dtabs">
      <el-tab-pane v-for="t in tabs" :key="t.code" :name="t.code" :label="tr(t, 'title')" />
    </el-tabs>
    <div class="grid12">
      <Widget v-for="w in visible" :key="w.id + JSON.stringify(w.source) + JSON.stringify(w.options)" :widget="w" :filters="filters" :species="species">
        <template v-if="editing" #tools>
          <span>
            <el-button size="small" text @click="$emit('edit-widget', w)"><el-icon><Edit /></el-icon></el-button>
            <el-button size="small" text @click="$emit('move', w, -1)"><el-icon><Top /></el-icon></el-button>
            <el-button size="small" text @click="$emit('move', w, 1)"><el-icon><Bottom /></el-icon></el-button>
            <el-button size="small" text type="danger" @click="$emit('remove', w)"><el-icon><Delete /></el-icon></el-button>
          </span>
        </template>
      </Widget>
      <div v-if="!visible.length" class="card state" style="grid-column: span 12">{{ $t('common.empty') }}</div>
    </div>
  </div>
</template>
<script setup>
import { computed, ref, watch } from 'vue'
import { tr } from '../i18n'
import Widget from './Widget.vue'
const p = defineProps({ board: Object, filters: Object, species: Object, editing: Boolean, modelValue: String })
const emit = defineEmits(['edit-widget', 'move', 'remove', 'update:modelValue'])
const tabs = computed(() => (p.board?.tabs?.length ? p.board.tabs : [{ code: 'main', title_ru: 'Главная' }]))
const tab = ref(p.modelValue || tabs.value[0]?.code)
watch(tab, (v) => emit('update:modelValue', v))
watch(tabs, (t) => { if (!t.find((x) => x.code === tab.value)) tab.value = t[0]?.code })
const visible = computed(() => (p.board?.widgets || []).filter((w) => (w.tab || tabs.value[0].code) === tab.value))
</script>
<style scoped>
.dtabs { margin-bottom: 6px; }
</style>
