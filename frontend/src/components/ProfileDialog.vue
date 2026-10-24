<template>
  <el-dialog :model-value="modelValue" :title="$t('profile.title')" width="560px" class="profile-dlg"
             @update:model-value="$emit('update:modelValue', $event)" @open="open">
    <div class="top">
      <UserAvatar :user="preview" :size="88" />
      <div class="photo-actions">
        <div class="who">{{ auth.user?.login }} · {{ $t('roles.' + auth.role) }}</div>
        <div class="muted small">{{ $t('profile.fixed') }}</div>
        <div class="btns">
          <el-button size="small" :loading="photoBusy" @click="pick">
            <el-icon><Camera /></el-icon>&nbsp;{{ auth.user?.avatar_ver ? $t('profile.photo_change') : $t('profile.photo_add') }}
          </el-button>
          <el-button v-if="auth.user?.avatar_ver" size="small" text type="danger" :disabled="photoBusy" @click="removePhoto">
            {{ $t('profile.photo_remove') }}
          </el-button>
        </div>
        <div class="muted small">{{ $t('profile.photo_hint') }}</div>
        <input ref="file" type="file" accept="image/jpeg,image/png,image/webp" hidden @change="onFile">
      </div>
    </div>
    <el-form label-position="top" class="form" @submit.prevent="save">
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
        <div class="muted small">{{ orgs.length ? $t('users.org_missing') : $t('users.org_empty') }}</div>
      </el-form-item>
      <el-alert v-if="err" type="error" :closable="false" :title="err" />
    </el-form>
    <template #footer>
      <div class="foot">
        <el-button text @click="$emit('password')"><el-icon><Lock /></el-icon>&nbsp;{{ $t('nav.password') }}</el-button>
        <span>
          <el-button @click="$emit('update:modelValue', false)">{{ $t('common.cancel') }}</el-button>
          <el-button type="primary" :loading="busy" @click="save">{{ $t('common.save') }}</el-button>
        </span>
      </div>
    </template>
  </el-dialog>
</template>
<script setup>
// «Мой профиль»: пользователь сам меняет имя, почту, должность, организацию, фото (решение № 58).
// Логин и роль только показываются — их меняет администратор.
import { computed, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { api } from '../api'
import { useAuth } from '../store/auth'
import { prepareAvatar } from '../avatar'
import { loadOrgs } from '../orgs'
import { checkProfile } from '../profile'
import UserAvatar from './UserAvatar.vue'
defineProps({ modelValue: Boolean })
const emit = defineEmits(['update:modelValue', 'password'])
const { t, locale } = useI18n()
const auth = useAuth()
const f = reactive({ name: '', email: '', position: '', organization: '' })
const errs = reactive({ name: '', email: '' })
const err = ref('')
const busy = ref(false)
const photoBusy = ref(false)
const orgs = ref([])
const file = ref(null)
const preview = computed(() => ({ ...auth.user, name: f.name || auth.user?.name }))

async function open() {
  const u = auth.user || {}
  Object.assign(f, { name: u.name || '', email: u.email || '', position: u.position || '', organization: u.organization || '' })
  Object.assign(errs, { name: '', email: '' }); err.value = ''
  orgs.value = await loadOrgs(locale.value)
}
async function save() {
  Object.assign(errs, checkProfile(f, t)); err.value = ''
  if (errs.name || errs.email) return
  busy.value = true
  try {
    auth.setSession(await api.patch('users', '/auth/me', { name: f.name, email: f.email, position: f.position, organization: f.organization || '' }))
    ElMessage.success(t('profile.saved'))
    emit('update:modelValue', false)
  } catch (e) { err.value = e.message } finally { busy.value = false }
}
function pick() { file.value.value = ''; file.value.click() }
async function onFile(ev) {
  const fl = ev.target.files?.[0]
  if (!fl) return
  photoBusy.value = true
  try {
    const data = await prepareAvatar(fl)
    auth.setUser(await api.put('users', '/auth/me/avatar', { data }))
    ElMessage.success(t('profile.photo_saved'))
  } catch (e) { ElMessage.error(e.message) } finally { photoBusy.value = false }
}
async function removePhoto() {
  photoBusy.value = true
  try { auth.setUser(await api.del('users', '/auth/me/avatar')) } catch (e) { ElMessage.error(e.message) } finally { photoBusy.value = false }
}
</script>
<style scoped>
.top { display: flex; gap: 18px; align-items: center; margin-bottom: 14px; }
.photo-actions { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.who { font-weight: 600; }
.btns { display: flex; gap: 6px; flex-wrap: wrap; margin: 4px 0 2px; }
.row2 { display: grid; grid-template-columns: 1fr 1fr; gap: 0 14px; }
.foot { display: flex; justify-content: space-between; align-items: center; gap: 8px; flex-wrap: wrap; }
.small { font-size: 12px; line-height: 1.35; }
@media (max-width: 600px) { .row2 { grid-template-columns: 1fr; } .top { align-items: flex-start; } }
:global(.profile-dlg) { max-width: calc(100vw - 32px); }
</style>
