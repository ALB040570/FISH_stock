<template>
  <el-dialog :model-value="modelValue" :title="$t('password.title')" width="420px" :close-on-click-modal="!forced"
             :show-close="!forced" @update:model-value="$emit('update:modelValue', $event)">
    <el-alert v-if="forced" type="warning" :closable="false" :title="$t('password.must')" style="margin-bottom:12px" />
    <el-form label-position="top" @submit.prevent="save">
      <el-form-item :label="$t('password.old')"><el-input v-model="f.old" type="password" show-password /></el-form-item>
      <el-form-item :label="$t('password.new')"><el-input v-model="f.n1" type="password" show-password /></el-form-item>
      <el-form-item :label="$t('password.repeat')"><el-input v-model="f.n2" type="password" show-password /></el-form-item>
      <el-alert v-if="err" type="error" :closable="false" :title="err" />
    </el-form>
    <template #footer>
      <el-button v-if="!forced" @click="$emit('update:modelValue', false)">{{ $t('common.cancel') }}</el-button>
      <el-button type="primary" :loading="busy" @click="save">{{ $t('common.save') }}</el-button>
    </template>
  </el-dialog>
</template>
<script setup>
import { reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { api } from '../api'
import { useAuth } from '../store/auth'
defineProps({ modelValue: Boolean, forced: Boolean })
const emit = defineEmits(['update:modelValue'])
const { t } = useI18n()
const f = reactive({ old: '', n1: '', n2: '' })
const err = ref('')
const busy = ref(false)
async function save() {
  err.value = ''
  if (f.n1 !== f.n2) { err.value = t('password.mismatch'); return }
  busy.value = true
  try {
    const j = await api.post('users', '/auth/password', { old_password: f.old, new_password: f.n1 })
    useAuth().setSession(j)
    ElMessage.success(t('password.changed'))
    emit('update:modelValue', false)
  } catch (e) { err.value = e.message } finally { busy.value = false }
}
</script>
