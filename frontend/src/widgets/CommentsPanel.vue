<template>
  <div class="cm">
    <div class="cm-h"><el-tooltip :content="$t('mon.comments')" placement="left"><span class="cm-ic" :aria-label="$t('mon.comments')"><el-icon><ChatDotRound /></el-icon></span></el-tooltip><b>{{ items.length }}</b></div>
    <div v-if="auth.can('dashboard.edit')" class="cm-new">
      <el-input v-model="text" type="textarea" :autosize="{ minRows: 2, maxRows: 6 }" maxlength="2000" :placeholder="$t('mon.write')" />
      <div class="row" style="justify-content:space-between; margin-top:6px">
        <el-select v-model="year" clearable size="small" :placeholder="$t('mon.year_tag')" style="width:110px">
          <el-option v-for="y in years" :key="y" :label="y" :value="y" />
        </el-select>
        <el-button size="small" type="primary" :disabled="!text.trim()" :loading="busy" @click="send">{{ $t('mon.send') }}</el-button>
      </div>
    </div>
    <div v-if="!items.length && !loading" class="muted small" style="padding:8px 0">{{ $t(auth.can('dashboard.edit') ? 'mon.no_comments' : 'mon.no_comments_ro') }}</div>
    <div v-for="c in items" :key="c.id" class="cm-i">
      <UserAvatar :user="personOf(c.author_id, c.author_name)" :size="30" />
      <div class="cm-b">
        <div class="cm-m"><b :title="about(personOf(c.author_id, c.author_name))">{{ personOf(c.author_id, c.author_name).name }}</b><span class="muted">&nbsp;· {{ when(c.created_at) }}</span>
          <el-tag v-if="c.year" size="small" effect="plain" style="margin-left:6px">{{ c.year }}</el-tag>
          <el-button v-if="c.can_delete" size="small" text class="del" @click="del(c)"><el-icon><Delete /></el-icon></el-button>
        </div>
        <div class="cm-t">{{ c.text }}</div>
      </div>
    </div>
  </div>
</template>
<script setup>
import { ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../api'
import { useAuth } from '../store/auth'
import { loadPeople, personOf } from '../avatar'
import UserAvatar from '../components/UserAvatar.vue'
const p = defineProps({ boardId: String, widgetId: String, waterBody: String, species: String, years: { type: Array, default: () => [] } })
const emit = defineEmits(['changed'])
const auth = useAuth()
const items = ref([])
const loading = ref(false)
const text = ref('')
const year = ref(null)
const busy = ref(false)
const key = () => ({ board: p.boardId, widget: p.widgetId, water_body: p.waterBody, species: p.species || undefined })
async function load() {
  if (!p.boardId || !p.widgetId) return
  loading.value = true
  try { items.value = await api.get('dashboards', '/comments', key()) } catch (e) { items.value = [] } finally { loading.value = false }
}
watch(() => [p.boardId, p.widgetId, p.waterBody, p.species], load, { immediate: true })
loadPeople()  // актуальные имена и фото авторов (решение № 58)
const about = (u) => [u.position].filter(Boolean).join(', ')
async function send() {
  busy.value = true
  try {
    await api.post('dashboards', '/comments', { ...key(), species: p.species || null, year: year.value || null, text: text.value })
    text.value = ''; year.value = null
    await load(); emit('changed')
  } catch (e) { ElMessage.error(e.message || String(e)) } finally { busy.value = false }
}
async function del(c) {
  await ElMessageBox.confirm('Удалить комментарий?', '', { type: 'warning' })
  await api.del('dashboards', `/comments/${c.id}`)
  await load(); emit('changed')
}
function when(s) {
  if (!s) return ''
  const d = new Date(s)
  return d.toLocaleDateString('ru-RU') + ' ' + d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
}
</script>
<style scoped>
.cm-h { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; padding-top: 10px; border-top: 1px solid var(--fs-line-soft); }
.cm-ic { width: 26px; height: 26px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center;
  background: var(--fs-hover); color: var(--fs-primary-2); font-size: 15px; cursor: help; }
.cm-new { margin-bottom: 10px; }
.cm-i { display: flex; gap: 10px; padding: 8px 0; border-top: 1px solid var(--fs-line-soft); }
.cm-b { min-width: 0; flex: 1; }
.cm-m { font-size: 12.5px; display: flex; align-items: center; flex-wrap: wrap; }
.cm-t { white-space: pre-wrap; line-height: 1.45; margin-top: 2px; }
.del { margin-left: auto; }
</style>
