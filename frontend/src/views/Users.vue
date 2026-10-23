<template>
  <div class="page">
    <div class="page-head">
      <div><h1>{{ $t('users.title') }}</h1></div>
      <el-button type="primary" @click="openNew"><el-icon><Plus /></el-icon>&nbsp;{{ $t('users.new') }}</el-button>
    </div>
    <StateBlock :loading="loading" :error="error">
      <div class="card">
        <el-table :data="items">
          <el-table-column prop="login" :label="$t('users.login')" width="150" />
          <el-table-column prop="name" :label="$t('users.name')" min-width="200" />
          <el-table-column prop="email" :label="$t('users.email')" min-width="160" />
          <el-table-column :label="$t('users.role')" width="210">
            <template #default="{ row }">
              <el-select :model-value="row.role" size="small" @change="(v) => setRole(row, v)"><el-option v-for="r in roles" :key="r" :label="$t('roles.' + r)" :value="r" /></el-select>
            </template>
          </el-table-column>
          <el-table-column :label="$t('common.status')" width="140"><template #default="{ row }"><el-tag :type="row.blocked ? 'danger' : 'success'" size="small">{{ row.blocked ? $t('users.blocked') : 'активен' }}</el-tag></template></el-table-column>
          <el-table-column :label="$t('users.last_login')" width="170"><template #default="{ row }">{{ row.last_login_at ? new Date(row.last_login_at).toLocaleString('ru-RU') : '—' }}</template></el-table-column>
          <el-table-column width="330" align="right">
            <template #default="{ row }">
              <el-button v-if="!row.blocked" size="small" @click="act(row, 'block')">{{ $t('users.block') }}</el-button>
              <el-button v-else size="small" type="success" plain @click="act(row, 'unblock')">{{ $t('users.unblock') }}</el-button>
              <el-button size="small" @click="reset(row)">{{ $t('users.reset') }}</el-button>
              <el-button size="small" text type="danger" @click="del(row)"><el-icon><Delete /></el-icon></el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </StateBlock>
    <el-dialog v-model="dlg" :title="$t('users.new')" width="520px">
      <el-form label-width="140px">
        <el-form-item :label="$t('users.login')"><el-input v-model="f.login" /></el-form-item>
        <el-form-item :label="$t('users.name')"><el-input v-model="f.name" /></el-form-item>
        <el-form-item :label="$t('users.email')"><el-input v-model="f.email" /></el-form-item>
        <el-form-item :label="$t('users.role')"><el-select v-model="f.role"><el-option v-for="r in roles" :key="r" :label="$t('roles.' + r)" :value="r" /></el-select></el-form-item>
        <el-form-item :label="$t('login.password')"><el-input v-model="f.password" type="password" show-password /><div class="muted small">{{ $t('users.password') }}. Пользователь сменит его при первом входе.</div></el-form-item>
      </el-form>
      <StateBlock :error="err" />
      <template #footer><el-button @click="dlg = false">{{ $t('common.cancel') }}</el-button><el-button type="primary" @click="create">{{ $t('common.create') }}</el-button></template>
    </el-dialog>
  </div>
</template>
<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../api'
import StateBlock from '../components/StateBlock.vue'
const roles = ['admin', 'ichthyologist', 'mathematician', 'operator', 'viewer']
const items = ref([])
const loading = ref(true)
const error = ref(null)
const dlg = ref(false)
const err = ref(null)
const f = reactive({ login: '', name: '', email: '', role: 'ichthyologist', password: '' })
async function load() { try { items.value = await api.get('users', '/users') } catch (e) { error.value = e } finally { loading.value = false } }
function openNew() { Object.assign(f, { login: '', name: '', email: '', role: 'ichthyologist', password: '' }); err.value = null; dlg.value = true }
async function create() { err.value = null; try { await api.post('users', '/users', f); dlg.value = false; await load() } catch (e) { err.value = e } }
async function act(row, a) { try { await api.post('users', `/users/${row.id}/${a}`); await load() } catch (e) { ElMessage.error(e.message) } }
async function setRole(row, role) { try { await api.patch('users', `/users/${row.id}`, { role }); await load() } catch (e) { ElMessage.error(e.message); await load() } }
async function reset(row) {
  const { value } = await ElMessageBox.prompt('Новый временный пароль (не короче 8 символов)', row.login, { inputType: 'password' })
  try { await api.post('users', `/users/${row.id}/reset-password`, { password: value }); ElMessage.success('Пароль сброшен') } catch (e) { ElMessage.error(e.message) }
}
async function del(row) { await ElMessageBox.confirm(`Удалить пользователя ${row.login}?`, '', { type: 'warning' }); try { await api.del('users', `/users/${row.id}`); await load() } catch (e) { ElMessage.error(e.message) } }
onMounted(load)
</script>
