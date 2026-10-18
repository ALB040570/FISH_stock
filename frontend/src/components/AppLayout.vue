<template>
  <el-container class="layout">
    <el-aside :width="collapsed ? '64px' : '248px'" class="aside">
      <div class="brand" @click="$router.push('/')">
        <svg viewBox="0 0 64 64" width="30" height="30"><path d="M6 32c10-14 30-16 42-6l10-8v28l-10-8c-12 10-32 8-42-6z" fill="#7fc4d8"/><circle cx="20" cy="29" r="3" fill="#12324a"/></svg>
        <div v-if="!collapsed"><div class="b1">FishStocke</div><div class="b2">{{ $t('app.subtitle') }}</div></div>
      </div>
      <el-menu :default-active="active" router :collapse="collapsed" background-color="#12324a" text-color="#c9d7e3" active-text-color="#ffffff">
        <el-menu-item-group :title="collapsed ? '' : $t('nav.section_work')">
          <el-menu-item index="/"><el-icon><MapLocation /></el-icon><span>{{ $t('nav.map') }}</span></el-menu-item>
          <el-menu-item index="/monitoring"><el-icon><DataLine /></el-icon><span>{{ $t('nav.monitoring') }}</span></el-menu-item>
          <el-menu-item index="/data"><el-icon><Files /></el-icon><span>{{ $t('nav.data') }}</span></el-menu-item>
          <el-menu-item index="/calculations"><el-icon><Operation /></el-icon><span>{{ $t('nav.calculations') }}</span></el-menu-item>
          <el-menu-item index="/runs"><el-icon><Timer /></el-icon><span>{{ $t('nav.runs') }}</span></el-menu-item>
          <el-menu-item index="/dashboards"><el-icon><Histogram /></el-icon><span>{{ $t('nav.dashboards') }}</span></el-menu-item>
        </el-menu-item-group>
        <el-menu-item-group :title="collapsed ? '' : $t('nav.section_model')">
          <el-menu-item index="/dictionaries"><el-icon><Collection /></el-icon><span>{{ $t('nav.dictionaries') }}</span></el-menu-item>
          <el-menu-item v-if="auth.can('algo.develop')" index="/algorithms"><el-icon><Cpu /></el-icon><span>{{ $t('nav.algorithms') }}</span></el-menu-item>
          <el-menu-item index="/catalog"><el-icon><Box /></el-icon><span>{{ $t('nav.catalog') }}</span></el-menu-item>
          <el-menu-item index="/profiles"><el-icon><SetUp /></el-icon><span>{{ $t('nav.profiles') }}</span></el-menu-item>
        </el-menu-item-group>
        <el-menu-item-group v-if="auth.can('users.manage')" :title="collapsed ? '' : $t('nav.section_admin')">
          <el-menu-item index="/users"><el-icon><User /></el-icon><span>{{ $t('nav.users') }}</span></el-menu-item>
          <el-menu-item index="/audit"><el-icon><Document /></el-icon><span>{{ $t('nav.audit') }}</span></el-menu-item>
        </el-menu-item-group>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header" height="52px">
        <el-button text @click="collapsed = !collapsed"><el-icon :size="18"><Fold v-if="!collapsed" /><Expand v-else /></el-icon></el-button>
        <div class="grow" />
        <el-radio-group v-model="lang" size="small" @change="setLang">
          <el-radio-button value="ru">РУС</el-radio-button>
          <el-radio-button value="kk">ҚАЗ</el-radio-button>
        </el-radio-group>
        <el-dropdown trigger="click" @command="onCmd">
          <span class="user">
            <el-avatar :size="28" style="background:#2b7a9e">{{ initials }}</el-avatar>
            <span class="uname">{{ auth.user?.name }}<br><span class="urole">{{ $t('roles.' + auth.role) }}</span></span>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="password">{{ $t('nav.password') }}</el-dropdown-item>
              <el-dropdown-item command="logout" divided>{{ $t('nav.logout') }}</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>
      <el-main class="main"><slot /></el-main>
    </el-container>
    <PasswordDialog v-model="pwd" :forced="forced" />
  </el-container>
</template>
<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuth } from '../store/auth'
import { setLang } from '../i18n'
import PasswordDialog from './PasswordDialog.vue'

const auth = useAuth()
const route = useRoute()
const router = useRouter()
const { locale } = useI18n()
const lang = ref(locale.value)
const collapsed = ref(window.innerWidth < 900)
const pwd = ref(!!auth.user?.must_change_password)
const forced = computed(() => !!auth.user?.must_change_password)
const active = computed(() => '/' + (route.path.split('/')[1] || ''))
const initials = computed(() => (auth.user?.name || '?').split(/\s+/).map((s) => s[0]).slice(0, 2).join('').toUpperCase())
watch(() => auth.loggedIn, (v) => { if (!v) router.push({ path: '/login', query: { next: route.fullPath } }) })
function onCmd(c) {
  if (c === 'logout') { auth.logout(); router.push('/login') }
  if (c === 'password') pwd.value = true
}
</script>
<style scoped>
.layout { height: 100vh; }
.aside { background: #12324a; transition: width .2s; overflow-x: hidden; overflow-y: auto; }
.brand { display: flex; gap: 10px; align-items: center; padding: 14px 16px 10px; cursor: pointer; color: #fff; }
.b1 { font-weight: 700; font-size: 16px; letter-spacing: .02em; }
.b2 { font-size: 10.5px; color: #9fb8cc; line-height: 1.25; margin-top: 2px; }
.aside :deep(.el-menu) { border-right: none; }
.aside :deep(.el-menu-item-group__title) { color: #7f9bb2; font-size: 11px; text-transform: uppercase; letter-spacing: .06em; padding-top: 14px; }
.aside :deep(.el-menu-item.is-active) { background: #1d5c7a !important; }
.header { display: flex; align-items: center; gap: 14px; background: #fff; border-bottom: 1px solid var(--fs-line); }
.user { display: flex; align-items: center; gap: 8px; cursor: pointer; }
.uname { font-size: 13px; line-height: 1.15; }
.urole { color: var(--fs-muted); font-size: 11px; }
.main { padding: 0; overflow: auto; }
</style>
