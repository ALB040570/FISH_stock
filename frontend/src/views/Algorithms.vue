<template>
  <div class="page">
    <div class="page-head">
      <div><h1>{{ $t('algo.title') }}</h1><div class="sub">Рабочее место математика: код и параметры алгоритмов, проверка, тестовый прогон, публикация проверенных версий в каталог.</div></div>
      <el-button type="primary" @click="dlg = true"><el-icon><Plus /></el-icon>&nbsp;{{ $t('algo.new') }}</el-button>
    </div>
    <StateBlock :loading="loading" :error="error">
      <div class="card">
        <el-table :data="items" row-key="code" @expand-change="expand">
          <el-table-column type="expand">
            <template #default="{ row }">
              <div style="padding:6px 20px">
                <div v-if="details[row.code]">
                  <div class="row">
                    <b>{{ $t('algo.drafts') }}</b>
                    <el-select v-model="fromV[row.code]" size="small" :placeholder="$t('algo.new_draft')" style="width:220px">
                      <el-option v-for="v in details[row.code].published" :key="v.version" :label="v.version" :value="v.version" />
                    </el-select>
                    <el-button size="small" :disabled="!details[row.code].published.length" @click="newDraft(row.code)">{{ $t('algo.new_draft') }}</el-button>
                  </div>
                  <el-table :data="details[row.code].drafts" size="small" style="margin-top:6px" @row-click="(d) => $router.push('/algorithms/drafts/' + d.id)">
                    <el-table-column :label="$t('common.date')" width="170"><template #default="{ row: d }">{{ new Date(d.created_at).toLocaleString() }}</template></el-table-column>
                    <el-table-column :label="$t('common.status')" width="130"><template #default="{ row: d }"><el-tag size="small" :type="d.status === 'published' ? 'success' : 'info'">{{ d.status === 'published' ? 'опубликован ' + d.published_version : 'черновик' }}</el-tag></template></el-table-column>
                    <el-table-column label="От версии" width="100" prop="base_version" />
                    <el-table-column label="Тест" width="140"><template #default="{ row: d }"><span v-if="d.last_test">{{ $t('algo.' + d.last_test.status) }}</span></template></el-table-column>
                    <el-table-column prop="author_name" :label="$t('common.author')" />
                  </el-table>
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column :label="$t('common.name')" min-width="260"><template #default="{ row }"><b>{{ tr(row, 'title') }}</b> <el-tag v-if="row.builtin" size="small" type="info">{{ $t('algo.builtin') }}</el-tag><div class="muted small">{{ row.description }}</div></template></el-table-column>
          <el-table-column prop="code" :label="$t('common.code')" width="180"><template #default="{ row }"><span class="mono">{{ row.code }}</span></template></el-table-column>
          <el-table-column prop="drafts" :label="$t('algo.drafts')" width="100" align="right" />
        </el-table>
      </div>
    </StateBlock>
    <el-dialog v-model="dlg" :title="$t('algo.new')" width="560px">
      <el-form label-width="140px">
        <el-form-item :label="$t('common.code')"><el-input v-model="f.code" placeholder="my_method" /></el-form-item>
        <el-form-item :label="$t('dict.title_ru')"><el-input v-model="f.title_ru" /></el-form-item>
        <el-form-item :label="$t('dict.title_kk')"><el-input v-model="f.title_kk" /></el-form-item>
        <el-form-item :label="$t('common.description')"><el-input v-model="f.description" type="textarea" /></el-form-item>
      </el-form>
      <div class="muted small">{{ $t('algo.contract') }}</div>
      <StateBlock :error="err" />
      <template #footer><el-button @click="dlg = false">{{ $t('common.cancel') }}</el-button><el-button type="primary" @click="create">{{ $t('common.create') }}</el-button></template>
    </el-dialog>
  </div>
</template>
<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { tr } from '../i18n'
import StateBlock from '../components/StateBlock.vue'
const router = useRouter()
const items = ref([])
const details = reactive({})
const fromV = reactive({})
const loading = ref(true)
const error = ref(null)
const dlg = ref(false)
const err = ref(null)
const f = reactive({ code: '', title_ru: '', title_kk: '', description: '' })
async function load() { try { items.value = await api.get('algo-model', '/algorithms') } catch (e) { error.value = e } finally { loading.value = false } }
async function expand(row) { details[row.code] = await api.get('algo-model', `/algorithms/${row.code}`) }
async function newDraft(code) {
  const d = await api.post('algo-model', `/algorithms/${code}/drafts`, { from_version: fromV[code] || null })
  router.push('/algorithms/drafts/' + d.id)
}
async function create() {
  err.value = null
  try { const r = await api.post('algo-model', '/algorithms', f); router.push('/algorithms/drafts/' + r.draft_id) } catch (e) { err.value = e }
}
onMounted(load)
</script>
