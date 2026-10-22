<template>
  <div>
    <el-tabs v-if="tabs.length > 1 || editing" v-model="tab" class="dtabs">
      <el-tab-pane v-for="t in tabs" :key="t.code" :name="t.code" :label="tr(t, 'title')" />
    </el-tabs>
    <div v-if="sections.length" class="secbar">
      <el-radio-group v-model="section" class="secs">
        <el-radio-button v-for="s in sections" :key="s.code" :value="s.code">{{ tr(s, 'title') }}</el-radio-button>
      </el-radio-group>
    </div>
    <div class="boardbar">
      <div class="row" style="gap:6px; align-items:center">
        <span class="small muted">{{ $t('wv.compare') }}:</span>
        <el-select v-model="cmpA" clearable size="small" style="width:92px" :placeholder="$t('common.year')">
          <el-option v-for="y in yearList" :key="y" :label="y" :value="y" />
        </el-select>
        <span class="small muted">{{ $t('wv.and') }}</span>
        <el-select v-model="cmpB" clearable size="small" style="width:92px" :placeholder="$t('common.year')">
          <el-option v-for="y in yearList" :key="y" :label="y" :value="y" />
        </el-select>
        <el-tag v-if="highlight != null" size="small" closable type="warning" @close="highlight = null">{{ $t('wv.highlighted') }}: {{ highlight }}</el-tag>
      </div>
      <el-button size="small" :loading="reporting" @click="report"><el-icon><Document /></el-icon>&nbsp;{{ $t('wv.report') }}</el-button>
    </div>
    <div class="grid12">
      <Widget v-for="w in visible" :key="w.id + JSON.stringify(w.source) + JSON.stringify(w.options)" :widget="w" :filters="wfilters" :species="species">
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
import { computed, provide, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { downloadPost } from '../api'
import { tr } from '../i18n'
import Widget from './Widget.vue'
const p = defineProps({ board: Object, filters: Object, species: Object, editing: Boolean, modelValue: String, wbName: String })
const emit = defineEmits(['edit-widget', 'move', 'remove', 'update:modelValue'])
const { t } = useI18n()
const tabs = computed(() => (p.board?.tabs?.length ? p.board.tabs : [{ code: 'main', title_ru: 'Главная' }]))
const tab = ref(p.modelValue || tabs.value[0]?.code)
watch(tab, (v) => emit('update:modelValue', v))
watch(tabs, (tt) => { if (!tt.find((x) => x.code === tab.value)) tab.value = tt[0]?.code })
const curTab = computed(() => tabs.value.find((x) => x.code === tab.value) || tabs.value[0])
const sections = computed(() => curTab.value?.sections || [])
const section = ref(null)
watch(sections, (s) => { if (s.length && !s.find((x) => x.code === section.value)) section.value = s[0].code }, { immediate: true })
const visible = computed(() => (p.board?.widgets || []).filter((w) => (w.tab || tabs.value[0].code) === tab.value &&
  (!sections.value.length || (w.section || sections.value[0].code) === section.value)))

// ---- связь виджетов: подсветка года, сравнение двух лет, отчёт раздела
const highlight = ref(null)
const years = ref(new Set())
const yearList = computed(() => [...years.value].sort((a, b) => b - a))
const cmpA = ref(null)
const cmpB = ref(null)
const compare = computed(() => (cmpA.value && cmpB.value && cmpA.value !== cmpB.value
  ? [Math.min(cmpA.value, cmpB.value), Math.max(cmpA.value, cmpB.value)] : null))
const wfilters = computed(() => ({ ...p.filters, ...(compare.value ? { compare: compare.value } : {}) }))
watch(() => p.filters?.water_body, () => { years.value = new Set(); highlight.value = null; cmpA.value = null; cmpB.value = null })
const reg = new Map()
provide('board', {
  highlight,
  wbName: computed(() => p.wbName || ''),
  setHighlight: (y) => { highlight.value = y == null || highlight.value === y ? null : y },
  setSection: (s) => { const tb = tabs.value.find((x) => (x.sections || []).some((q) => q.code === s)); if (tb) { tab.value = tb.code; section.value = s } },
  addYears: (ys) => { const n = new Set(years.value); for (const y of ys || []) if (Number.isInteger(+y) && +y > 1900) n.add(+y); if (n.size !== years.value.size) years.value = n },
  register: (id, fn, ready) => { reg.set(id, { fn, ready }); return () => reg.delete(id) },
})
const reporting = ref(false)
async function report() {
  reporting.value = true
  try {
    const ids = visible.value.map((w) => w.id).filter((id) => reg.has(id) && reg.get(id).ready())
    const widgets = await Promise.all(ids.map((id) => reg.get(id).fn()))
    const sec = sections.value.find((s) => s.code === section.value)
    const title = [tr(curTab.value, 'title'), sec ? tr(sec, 'title') : null].filter(Boolean).join(' — ')
    const ctx = [p.wbName, p.filters?.species ? p.species?.[p.filters.species] : null,
      compare.value ? `${t('wv.compare')}: ${compare.value[0]} ${t('wv.and')} ${compare.value[1]}` : null].filter(Boolean).join(' · ')
    await downloadPost('dashboards', '/reports/section.pdf', { title, context: ctx, widgets },
      `${(p.wbName || 'FishStock').replace(/[^\p{L}\p{N}]+/gu, '_')}_${(sec?.code || tab.value)}.pdf`)
  } catch (e) { ElMessage.error(e.message || String(e)) } finally { reporting.value = false }
}
</script>
<style scoped>
.dtabs { margin-bottom: 6px; }
.secbar { margin: 0 0 10px; overflow-x: auto; }
.secs { flex-wrap: nowrap; }
.boardbar { display: flex; justify-content: space-between; align-items: center; gap: 10px; margin-bottom: 10px; flex-wrap: wrap; }
</style>
