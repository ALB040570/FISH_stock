<template>
  <div class="login-wrap">
    <div class="side">
      <svg viewBox="0 0 64 64" width="54" height="54"><path d="M6 32c10-14 30-16 42-6l10-8v28l-10-8c-12 10-32 8-42-6z" fill="#7fc4d8"/><circle cx="20" cy="29" r="3" fill="#12324a"/></svg>
      <h1>FishStocke</h1>
      <p>{{ $t('app.subtitle') }}</p>
      <div class="waves" />
    </div>
    <div class="form">
      <div class="lang">
        <el-radio-group v-model="lang" size="small" @change="setLang">
          <el-radio-button value="ru">РУС</el-radio-button><el-radio-button value="kk">ҚАЗ</el-radio-button>
        </el-radio-group>
      </div>
      <h2>{{ $t('login.title') }}</h2>
      <el-alert v-if="auth.expired" type="info" :closable="false" :title="$t('login.expired')" style="margin-bottom:12px" />
      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item :label="$t('login.login')"><el-input v-model="login" autocomplete="username" size="large" autofocus /></el-form-item>
        <el-form-item :label="$t('login.password')"><el-input v-model="password" type="password" show-password autocomplete="current-password" size="large" /></el-form-item>
        <el-alert v-if="err" type="error" :closable="false" :title="err" style="margin-bottom:12px" />
        <el-button type="primary" size="large" native-type="submit" :loading="busy" style="width:100%">{{ $t('login.submit') }}</el-button>
      </el-form>
      <p class="muted small" style="margin-top:14px">{{ $t('login.hint') }}</p>
    </div>
  </div>
</template>
<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { api } from '../api'
import { useAuth } from '../store/auth'
import { setLang } from '../i18n'
const auth = useAuth()
const router = useRouter()
const route = useRoute()
const { locale } = useI18n()
const lang = ref(locale.value)
const login = ref('')
const password = ref('')
const err = ref('')
const busy = ref(false)
async function submit() {
  err.value = ''; busy.value = true
  try {
    const j = await api.post('users', '/auth/login', { login: login.value, password: password.value })
    auth.setSession(j)
    router.push(route.query.next || '/')
  } catch (e) { err.value = e.message } finally { busy.value = false }
}
</script>
<style scoped>
.login-wrap { display: grid; grid-template-columns: 1.1fr 1fr; min-height: 100vh; }
.side { background: linear-gradient(160deg, #12324a 0%, #1d5c7a 70%, #2a9d8f 100%); color: #fff; padding: 12vh 8vw; position: relative; overflow: hidden; }
.side h1 { font-size: 34px; margin: 14px 0 6px; }
.side p { color: #cfe3ee; font-size: 16px; max-width: 420px; line-height: 1.45; }
.waves { position: absolute; left: -10%; right: -10%; bottom: -40px; height: 180px; border-radius: 50%; background: rgba(255,255,255,.06); box-shadow: 0 -40px 0 rgba(255,255,255,.04); }
.form { padding: 12vh 8vw; background: #fff; position: relative; }
.form h2 { font-size: 22px; margin-bottom: 18px; }
.lang { position: absolute; top: 20px; right: 24px; }
@media (max-width: 800px) { .login-wrap { grid-template-columns: 1fr; } .side { padding: 40px 24px; } .form { padding: 30px 24px; } }
</style>
