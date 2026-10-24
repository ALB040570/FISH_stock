<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1>{{ $t('users.title') }}</h1>
        <div class="muted small">{{ $t('users.sub') }}</div>
      </div>
      <div class="row">
        <el-input v-model="q" clearable :placeholder="$t('common.search')" style="width:200px"><template #prefix><el-icon><Search /></el-icon></template></el-input>
        <el-button type="primary" @click="openNew"><el-icon><Plus /></el-icon>&nbsp;{{ $t('users.new') }}</el-button>
      </div>
    </div>
    <StateBlock :loading="loading" :error="error">
      <div class="card">
        <el-table :data="shown" class="utable" :row-class-name="({ row }) => row.blocked ? 'is-blocked' : ''">
          <el-table-column :label="$t('users.user')" min-width="260">
            <template #default="{ row }">
              <div class="who">
                <UserAvatar :user="row" :size="34" />
                <div class="who-t">
                  <div class="nm">{{ row.name }}<el-tag v-if="row.id === auth.user?.id" size="small" effect="plain" class="me">{{ $t('users.you') }}</el-tag></div>
                  <div class="muted small">{{ row.login }}<template v-if="row.email"> · {{ row.email }}</template></div>
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column :label="$t('users.position') + ' / ' + $t('users.organization')" min-width="200">
            <template #default="{ row }">
              <div>{{ row.position || '—' }}</div>
              <div v-if="row.organization" class="muted small">{{ orgName(orgs, row.organization) }}</div>
            </template>
          </el-table-column>
          <el-table-column :label="$t('users.role')" min-width="170"><template #default="{ row }">{{ $t('roles.' + row.role) }}</template></el-table-column>
          <el-table-column :label="$t('common.status')" width="130">
            <template #default="{ row }"><el-tag :type="row.blocked ? 'danger' : 'success'" size="small">{{ row.blocked ? $t('users.blocked') : $t('users.active') }}</el-tag></template>
          </el-table-column>
          <el-table-column :label="$t('users.last_login')" width="150">
            <template #default="{ row }"><span class="small">{{ row.last_login_at ? new Date(row.last_login_at).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' }) : '—' }}</span></template>
          </el-table-column>
          <el-table-column :width="narrow ? 112 : 170" align="right" fixed="right" :label="$t('users.actions')">
            <template #default="{ row }">
              <div class="acts">
                <el-button size="small" :aria-label="$t('common.edit')" :title="$t('common.edit')" @click="openEdit(row)"><el-icon><Edit /></el-icon><span v-if="!narrow">&nbsp;{{ $t('common.edit') }}</span></el-button>
                <el-dropdown trigger="click" @command="(c) => cmd(row, c)">
                  <el-button size="small" :aria-label="$t('users.more')"><el-icon><MoreFilled /></el-icon></el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item v-if="!row.blocked" command="block" :disabled="row.id === auth.user?.id"><el-icon><Lock /></el-icon>{{ $t('users.block') }}</el-dropdown-item>
                      <el-dropdown-item v-else command="unblock"><el-icon><Unlock /></el-icon>{{ $t('users.unblock') }}</el-dropdown-item>
                      <el-dropdown-item command="reset"><el-icon><Key /></el-icon>{{ $t('users.reset') }}</el-dropdown-item>
                      <el-dropdown-item v-if="row.avatar_ver" command="photo"><el-icon><Picture /></el-icon>{{ $t('users.photo_remove') }}</el-dropdown-item>
                      <el-dropdown-item command="delete" divided :disabled="row.id === auth.user?.id" class="danger-item"><el-icon><Delete /></el-icon>{{ $t('common.delete') }}</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <div class="muted small foot-note">
        {{ $t('users.block_vs_delete') }}
        <template v-if="canGo(ORG_DICT_PATH, auth.role)"> <a :href="ORG_DICT_PATH" @click.prevent="hardGo(ORG_DICT_PATH)">{{ $t('users.org_dict') }}</a></template>
      </div>
    </StateBlock>

    <el-dialog v-model="dlg" :title="edit ? $t('users.edit') : $t('users.new')" width="560px" class="user-dlg">
      <el-form label-position="top" @submit.prevent="save">
        <div class="row2">
          <el-form-item :label="$t('users.login')" :required="!edit">
            <el-input v-model="f.login" :disabled="!!edit" maxlength="64" />
            <div v-if="edit" class="muted small">{{ $t('users.login_fixed') }}</div>
          </el-form-item>
          <el-form-item :label="$t('users.role')" required>
            <el-select v-model="f.role" style="width:100%"><el-option v-for="r in roles" :key="r" :label="$t('roles.' + r)" :value="r" /></el-select>
          </el-form-item>
        </div>
        <el-form-item :label="$t('users.name')" required :error="errs.name"><el-input v-model="f.name" maxlength="200" /></el-form-item>
        <div class="row2">
          <el-form-item :label="$t('users.position')"><el-input v-model="f.position" maxlength="200" :placeholder="$t('users.position_ph')" /></el-form-item>
          <el-form-item :label="$t('users.email')" :error="errs.email"><el-input v-model="f.email" maxlength="200" /></el-form-item>
        </div>
        <el-form-item :label="$t('users.organization')">
          <el-select v-model="f.organization" filterable clearable :placeholder="$t('users.org_ph')" style="width:100%">
            <el-option v-for="o in orgs" :key="o.code" :label="o.name" :value="o.code" />
            <el-option v-if="f.organization && !orgs.some((o) => o.code === f.organization)" :label="f.organization" :value="f.organization" />
          </el-select>
          <div v-if="!orgs.length" class="muted small">{{ $t('users.org_empty_admin') }}</div>
        </el-form-item>
        <el-form-item v-if="!edit" :label="$t('login.password')" required>
          <el-input v-model="f.password" type="password" show-password />
          <div class="muted small">{{ $t('users.password') }}. {{ $t('users.password_first') }}</div>
        </el-form-item>
        <el-alert v-if="edit && f.role !== edit.role" type="info" :closable="false" :title="$t('users.role_relogin')" style="margin-bottom:8px" />
      </el-form>
      <StateBlock :error="err" />
      <template #footer>
        <el-button @click="dlg = false">{{ $t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="busy" @click="save">{{ edit ? $t('common.save') : $t('common.create') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>
<script setup>
// Администрирование пользователей: создание, правка (кроме логина), блокировка, сброс пароля, удаление (решение № 58).
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../api'
import { useAuth } from '../store/auth'
import { canGo, hardGo } from '../cabinets'
import { ORG_DICT_PATH, loadOrgs, orgName } from '../orgs'
import { checkProfile } from '../profile'
import { loadPeople } from '../avatar'
import StateBlock from '../components/StateBlock.vue'
import UserAvatar from '../components/UserAvatar.vue'
const { t, locale } = useI18n()
const auth = useAuth()
const roles = ['admin', 'ichthyologist', 'mathematician', 'operator', 'viewer', 'presenter']
const items = ref([])
const orgs = ref([])
const loading = ref(true)
const error = ref(null)
const q = ref('')
const narrow = window.innerWidth < 700  // телефон: в колонке действий только значки
const dlg = ref(false)
const edit = ref(null)
const err = ref(null)
const busy = ref(false)
const empty = () => ({ login: '', name: '', email: '', position: '', organization: '', role: 'ichthyologist', password: '' })
const f = reactive(empty())
const errs = reactive({ name: '', email: '' })

const shown = computed(() => {
  const s = q.value.trim().toLowerCase()
  const list = [...items.value].sort((a, b) => (a.name || a.login).localeCompare(b.name || b.login, 'ru'))
  if (!s) return list
  return list.filter((u) => [u.login, u.name, u.email, u.position, orgName(orgs.value, u.organization), t('roles.' + u.role)]
    .some((x) => String(x || '').toLowerCase().includes(s)))
})

async function load() {
  try { items.value = await api.get('users', '/users') } catch (e) { error.value = e } finally { loading.value = false }
}
function afterChange(u) { if (u && u.id === auth.user?.id) auth.setUser(u); loadPeople(true) }
function openNew() { Object.assign(f, empty()); edit.value = null; err.value = null; Object.assign(errs, { name: '', email: '' }); dlg.value = true }
function openEdit(row) {
  Object.assign(f, { ...empty(), login: row.login, name: row.name || '', email: row.email || '', position: row.position || '',
    organization: row.organization || '', role: row.role })
  edit.value = row; err.value = null; Object.assign(errs, { name: '', email: '' }); dlg.value = true
}
async function save() {
  Object.assign(errs, checkProfile(f, t)); err.value = null
  if (errs.name || errs.email) return
  busy.value = true
  try {
    const body = { name: f.name, email: f.email, position: f.position, organization: f.organization || '', role: f.role }
    let u
    if (edit.value) u = await api.patch('users', `/users/${edit.value.id}`, body)
    else u = await api.post('users', '/users', { ...body, login: f.login, password: f.password })
    dlg.value = false
    ElMessage.success(t(edit.value ? 'users.saved' : 'users.created'))
    afterChange(u); await load()
  } catch (e) { err.value = e } finally { busy.value = false }
}
async function cmd(row, c) {
  try {
    if (c === 'block' || c === 'unblock') { await api.post('users', `/users/${row.id}/${c}`) }
    if (c === 'reset') {
      const { value } = await ElMessageBox.prompt(t('users.reset_prompt'), `${row.name} (${row.login})`,
        { inputType: 'password', inputPattern: /^.{8,}$/, inputErrorMessage: t('users.password') })
      await api.post('users', `/users/${row.id}/reset-password`, { password: value })
      ElMessage.success(t('users.reset_done'))
    }
    if (c === 'photo') {
      await ElMessageBox.confirm(t('users.photo_remove_q', { name: row.name }), '', { type: 'warning' })
      afterChange(await api.del('users', `/users/${row.id}/avatar`))
    }
    if (c === 'delete') {
      await ElMessageBox.confirm(t('users.delete_text'), t('users.delete_q', { name: row.name, login: row.login }),
        { type: 'warning', confirmButtonText: t('common.delete'), confirmButtonClass: 'el-button--danger', distinguishCancelAndClose: true })
      await api.del('users', `/users/${row.id}`)
      ElMessage.success(t('users.deleted', { login: row.login }))
      loadPeople(true)
    }
    await load()
  } catch (e) {
    if (e === 'cancel' || e === 'close') return
    ElMessage.error(e.message || String(e))
  }
}
onMounted(async () => { await load(); orgs.value = await loadOrgs(locale.value) })
</script>
<style scoped>
.row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.who { display: flex; gap: 10px; align-items: center; min-width: 0; }
.who-t { min-width: 0; }
.nm { font-weight: 600; display: flex; align-items: center; gap: 6px; }
.me { font-weight: 400; }
.acts { display: inline-flex; gap: 6px; }
.acts :deep(.el-button + .el-button), .acts :deep(.el-dropdown) { margin-left: 0; }
.small { font-size: 12px; line-height: 1.4; }
.el-form-item .small { margin-top: 4px; }
.foot-note { margin-top: 10px; line-height: 1.5; }
.row2 { display: grid; grid-template-columns: 1fr 1fr; gap: 0 14px; }
.utable :deep(.is-blocked .nm) { color: var(--fs-muted); }
:global(.danger-item:not(.is-disabled)) { color: var(--fs-danger) !important; }
:global(.user-dlg) { max-width: calc(100vw - 32px); }
@media (max-width: 600px) { .row2 { grid-template-columns: 1fr; } }
</style>
