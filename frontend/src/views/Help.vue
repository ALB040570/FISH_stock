<template>
  <div class="page help-page">
    <div class="page-head">
      <div><h1>{{ $t('help.title') }}</h1><div class="sub">{{ $t('help.subtitle') }}</div></div>
      <div class="row">
        <el-dropdown trigger="click" @command="exportAll">
          <el-button><el-icon><Download /></el-icon>&nbsp;{{ $t('help.download_guide') }}</el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="docx">{{ $t('help.word') }}</el-dropdown-item>
              <el-dropdown-item command="pdf">{{ $t('help.pdf') }}</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>
    <div class="help-body">
      <aside class="card toc">
        <el-input v-model="q" :placeholder="$t('help.search')" clearable @input="onSearch">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <div v-if="q && q.length >= 2" class="results">
          <div v-if="!results.length" class="muted small" style="padding:8px 4px">{{ $t('help.nothing') }}</div>
          <div v-for="r in results" :key="r.id" class="res" @click="open(r.id)">
            <div class="rt">{{ r.title }}</div><div class="small muted">{{ r.section }}</div>
            <div class="small snip">{{ r.snippet }}</div>
          </div>
        </div>
        <template v-else>
          <div v-for="s in toc" :key="s.code" class="sec">
            <div class="sec-t" @click="toggle(s.code)">
              <el-icon :size="12"><ArrowRight v-if="!opened.has(s.code)" /><ArrowDown v-else /></el-icon>{{ s.title }}
            </div>
            <div v-if="opened.has(s.code)">
              <div v-for="a in s.articles" :key="a.id" class="art" :class="{ active: a.id === id }" @click="open(a.id)">
                {{ a.title }}<el-tag v-if="a.bundle_update && auth.can('help.edit')" size="small" type="warning" style="margin-left:4px">↻</el-tag>
              </div>
            </div>
          </div>
        </template>
      </aside>
      <section class="card content">
        <StateBlock :loading="loading" :error="error">
          <template v-if="art">
            <div class="row art-head">
              <span class="small muted">{{ art.section_title }}</span>
              <div class="grow" />
              <el-dropdown trigger="click" @command="exportOne">
                <el-button size="small">{{ $t('help.download_article') }}</el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="article:docx">{{ $t('help.article') }} — Word</el-dropdown-item>
                    <el-dropdown-item command="article:pdf">{{ $t('help.article') }} — PDF</el-dropdown-item>
                    <el-dropdown-item command="section:docx" divided>{{ $t('help.section') }} — Word</el-dropdown-item>
                    <el-dropdown-item command="section:pdf">{{ $t('help.section') }} — PDF</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
              <el-button v-if="art.can_edit && !editing" size="small" @click="startEdit"><el-icon><Edit /></el-icon>&nbsp;{{ $t('common.edit') }}</el-button>
              <el-button size="small" @click="showVersions"><el-icon><Clock /></el-icon>&nbsp;{{ $t('common.versions') }}</el-button>
            </div>
            <el-alert v-if="art.fallback" type="info" :closable="false" :title="$t('help.fallback')" style="margin-bottom:10px" />
            <el-alert v-if="art.bundle_update && art.can_edit" type="warning" :closable="false" style="margin-bottom:10px"
                      :title="$t('help.bundle_update')">
              <el-button size="small" @click="takeBundled">{{ $t('help.take_bundled') }}</el-button>
            </el-alert>
            <el-alert v-if="viewVersion" type="warning" :closable="false" style="margin-bottom:10px"
                      :title="$t('help.old_version', { n: viewVersion })">
              <el-button size="small" @click="viewVersion = null; load()">{{ $t('help.to_current') }}</el-button>
              <el-button v-if="art.can_edit" size="small" type="warning" @click="restore(viewVersion)">{{ $t('common.restore') }}</el-button>
            </el-alert>

            <div v-if="art.has_example && !editing" class="row example-bar">
              <span class="small">{{ $t('help.example_for') }}</span>
              <WaterBodySelect v-model="ex.wb" @update:model-value="loadExampleOptions" />
              <el-select v-model="ex.species" style="width:160px" :placeholder="$t('common.species')" @change="load">
                <el-option v-for="s in exOpts.species_list || []" :key="s" :label="s" :value="s" />
              </el-select>
              <el-select v-model="ex.year" style="width:110px" :placeholder="$t('common.year')" @change="load">
                <el-option v-for="y in exOpts.years || []" :key="y" :label="y" :value="y" />
              </el-select>
            </div>

            <template v-if="!editing">
              <HelpMarkdown :source="art.markdown" />
              <div class="small muted foot">v{{ art.version }} · {{ new Date(art.updated_at).toLocaleString('ru-RU') }}</div>
            </template>

            <div v-else class="editor">
              <div class="row" style="margin-bottom:8px">
                <el-radio-group v-model="editLang" size="small" @change="switchEditLang">
                  <el-radio-button value="ru">РУС</el-radio-button>
                  <el-radio-button value="kk">ҚАЗ</el-radio-button>
                </el-radio-group>
                <el-upload :show-file-list="false" accept="image/png,image/jpeg,image/gif,image/webp" :http-request="uploadImage">
                  <el-button size="small"><el-icon><Picture /></el-icon>&nbsp;{{ $t('help.insert_image') }}</el-button>
                </el-upload>
                <span class="small muted">{{ $t('help.md_hint') }}</span>
              </div>
              <div class="split">
                <el-input ref="ta" v-model="draft" type="textarea" :autosize="{ minRows: 24, maxRows: 60 }" class="mono-ta" />
                <div class="preview"><HelpMarkdown :source="draft" /></div>
              </div>
              <div class="row" style="margin-top:10px">
                <el-input v-model="comment" :placeholder="$t('common.comment')" style="width:380px" />
                <el-button type="primary" :loading="busy" @click="save">{{ $t('common.save') }}</el-button>
                <el-button @click="cancelEdit">{{ $t('common.cancel') }}</el-button>
              </div>
              <StateBlock :error="saveErr" />
            </div>
          </template>
        </StateBlock>
      </section>
    </div>

    <el-drawer v-model="versionsOpen" :title="$t('common.versions')" size="440px">
      <el-table :data="versions" size="small">
        <el-table-column prop="n" label="v" width="50" />
        <el-table-column :label="$t('common.date')" width="150"><template #default="{ row }">{{ new Date(row.created_at).toLocaleString('ru-RU') }}</template></el-table-column>
        <el-table-column prop="comment" :label="$t('common.comment')" />
        <el-table-column width="70"><template #default="{ row }"><el-button size="small" link @click="openVersion(row.n)">{{ $t('common.open') }}</el-button></template></el-table-column>
      </el-table>
    </el-drawer>
  </div>
</template>
<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { api, download } from '../api'
import { useAuth } from '../store/auth'
import HelpMarkdown from '../components/HelpMarkdown.vue'
import StateBlock from '../components/StateBlock.vue'
import WaterBodySelect from '../components/WaterBodySelect.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuth()
const { locale, t } = useI18n()
const toc = ref([])
const opened = reactive(new Set(['general']))
const id = computed(() => route.params.id || 'intro')
const art = ref(null)
const loading = ref(false)
const error = ref(null)
const q = ref('')
const results = ref([])
const editing = ref(false)
const editLang = ref('ru')
const draft = ref('')
const comment = ref('')
const busy = ref(false)
const saveErr = ref(null)
const versionsOpen = ref(false)
const versions = ref([])
const viewVersion = ref(null)
const ex = reactive({ wb: 'zhaysan', species: null, year: null })
const exOpts = ref({})
const ta = ref(null)

async function loadToc() {
  toc.value = await api.get('help', '/sections', { lang: locale.value })
  const sec = toc.value.find((s) => s.articles.some((a) => a.id === id.value))
  if (sec) opened.add(sec.code)
}
function toggle(code) { opened.has(code) ? opened.delete(code) : opened.add(code) }
function open(aid) { q.value = ''; router.push(`/help/${aid}`) }

async function load() {
  loading.value = !art.value || art.value.id !== id.value
  error.value = null
  try {
    art.value = await api.get('help', `/articles/${id.value}`, {
      lang: locale.value, expand: 1, version: viewVersion.value || undefined,
      wb: ex.wb, species: ex.species || undefined, year: ex.year || undefined,
    })
    if (art.value.has_example && !exOpts.value.years) loadExampleOptions(false)
  } catch (e) { error.value = e } finally { loading.value = false }
}
async function loadExampleOptions(reload = true) {
  try {
    exOpts.value = await api.get('help', '/example', { wb: ex.wb })
    ex.species = exOpts.value.species || null
    ex.year = exOpts.value.year || null
  } catch (e) { exOpts.value = {} }
  if (reload) load()
}

let timer = null
function onSearch() {
  clearTimeout(timer)
  timer = setTimeout(async () => {
    if (!q.value || q.value.length < 2) { results.value = []; return }
    results.value = await api.get('help', '/search', { q: q.value, lang: locale.value })
  }, 250)
}

function startEdit() {
  editLang.value = locale.value
  draft.value = art.value.texts?.[editLang.value] || ''
  comment.value = ''
  saveErr.value = null
  editing.value = true
}
function switchEditLang() { draft.value = art.value.texts?.[editLang.value] || '' }
function cancelEdit() { editing.value = false }
async function save() {
  busy.value = true; saveErr.value = null
  try {
    const r = await api.put('help', `/articles/${id.value}`, { lang: editLang.value, markdown: draft.value,
      comment: comment.value, base_version: art.value.current_version })
    ElMessage.success(r.changed ? `${t('common.saved')}: v${r.version}` : t('common.saved'))
    editing.value = false
    await load(); await loadToc()
  } catch (e) { saveErr.value = e } finally { busy.value = false }
}
async function uploadImage({ file }) {
  try {
    const r = await api.upload('help', '/images', { file })
    const el = ta.value?.textarea
    const pos = el ? el.selectionStart : draft.value.length
    draft.value = draft.value.slice(0, pos) + `\n${r.markdown}\n` + draft.value.slice(pos)
    await nextTick()
  } catch (e) { ElMessage.error(e.message) }
}
async function takeBundled() {
  await api.post('help', `/articles/${id.value}/take-bundled`)
  await load(); await loadToc()
}
async function showVersions() {
  versions.value = await api.get('help', `/articles/${id.value}/versions`)
  versionsOpen.value = true
}
function openVersion(n) { viewVersion.value = n === art.value.current_version ? null : n; versionsOpen.value = false; load() }
async function restore(n) {
  await api.post('help', `/articles/${id.value}/restore/${n}`)
  viewVersion.value = null
  ElMessage.success(t('common.saved'))
  await load()
}
function exportAll(fmt) { download('help', `/export.${fmt}`, { lang: locale.value, wb: ex.wb }) }
function exportOne(cmd) {
  const [what, fmt] = cmd.split(':')
  const query = { lang: locale.value, wb: ex.wb, species: ex.species || undefined, year: ex.year || undefined }
  if (what === 'article') query.article = id.value
  else query.section = art.value.section
  download('help', `/export.${fmt}`, query)
}

watch(id, () => { editing.value = false; viewVersion.value = null; load() })
watch(locale, () => { loadToc(); load() })
onMounted(async () => { await Promise.all([loadToc(), load()]) })
</script>
<style scoped>
.help-body { display: grid; grid-template-columns: 300px 1fr; gap: 16px; align-items: start; }
.toc { position: sticky; top: 8px; max-height: calc(100vh - 140px); overflow-y: auto; padding: 12px; }
.sec { margin-top: 10px; }
.sec-t { font-weight: 600; font-size: 13.5px; cursor: pointer; display: flex; gap: 6px; align-items: center; color: #12324a; padding: 3px 0; }
.art { font-size: 13.5px; padding: 4px 8px 4px 20px; cursor: pointer; border-radius: 4px; color: #33495c; }
.art:hover { background: #f0f5f9; }
.art.active { background: #e2eef6; color: #0f3c5a; font-weight: 500; }
.results { margin-top: 8px; }
.res { padding: 8px 6px; border-bottom: 1px solid #edf1f5; cursor: pointer; }
.res:hover { background: #f5f8fb; }
.rt { font-weight: 500; font-size: 14px; }
.snip { color: #55687a; margin-top: 2px; }
.content { padding: 18px 26px; min-height: 60vh; }
.art-head { margin-bottom: 8px; }
.foot { margin-top: 22px; border-top: 1px solid #edf1f5; padding-top: 6px; }
.example-bar { background: #f5f8fb; border-radius: 6px; padding: 8px 10px; margin-bottom: 12px; flex-wrap: wrap; }
.split { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.preview { border: 1px solid #e3e9ef; border-radius: 4px; padding: 10px 14px; max-height: 80vh; overflow-y: auto; }
.mono-ta :deep(textarea) { font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 13px; }
@media (max-width: 1000px) { .help-body { grid-template-columns: 1fr; } .toc { position: static; max-height: none; } .split { grid-template-columns: 1fr; } }
</style>
