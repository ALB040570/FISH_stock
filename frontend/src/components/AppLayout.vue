<template>
  <el-container class="layout">
    <el-aside :width="collapsed ? '64px' : '260px'" class="aside">
      <div class="brand" @click="$router.push('/')">
        <svg viewBox="0 0 64 64" width="30" height="30"><path class="logo-body" d="M6 32c10-14 30-16 42-6l10-8v28l-10-8c-12 10-32 8-42-6z"/><circle class="logo-eye" cx="20" cy="29" r="3"/></svg>
        <div v-if="!collapsed"><div class="b1">FishStock</div><div class="b2">{{ $t('app.subtitle') }}</div></div>
      </div>
      <el-menu ref="menuRef" :default-active="active" :default-openeds="openeds" router :collapse="collapsed" popper-class="fs-nav-popup">
        <template v-for="(sec, si) in sections" :key="sec.key">
          <li v-if="si === 2" class="nav-sep" />
          <el-sub-menu :index="sec.key">
            <template #title><el-icon><component :is="sec.icon" /></el-icon><span>{{ $t('nav.' + sec.key) }}</span></template>
            <el-menu-item v-for="it in sec.items" :key="it.index" :index="it.index" :class="{ 'nav-dash': it.dash, 'nav-more': it.more }">
              <span class="nav-label">{{ it.label }}</span>
              <el-icon v-if="it.personal" class="nav-personal" :title="$t('nav.personal')"><Lock /></el-icon>
            </el-menu-item>
          </el-sub-menu>
        </template>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header" height="52px">
        <el-button text @click="collapsed = !collapsed"><el-icon :size="18"><Fold v-if="!collapsed" /><Expand v-else /></el-icon></el-button>
        <div class="grow" />
        <el-button text class="help-link" @click="$router.push('/help')"><el-icon><Reading /></el-icon>&nbsp;{{ $t('nav.help') }}</el-button>
        <el-tooltip :content="$t('help.context')" placement="bottom">
          <el-button circle size="small" @click="openContext"><el-icon><QuestionFilled /></el-icon></el-button>
        </el-tooltip>
        <ThemeToggle />
        <el-radio-group v-model="lang" size="small" @change="setLang">
          <el-radio-button value="ru">РУС</el-radio-button>
          <el-radio-button value="kk">ҚАЗ</el-radio-button>
        </el-radio-group>
        <el-dropdown trigger="click" @command="onCmd">
          <span class="user">
            <el-avatar :size="28" class="avatar">{{ initials }}</el-avatar>
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
    <el-drawer v-model="ctxOpen" :title="ctxArt?.title || $t('nav.help')" size="560px">
      <div v-if="ctxArt">
        <HelpMarkdown :source="ctxArt.markdown" strip-title @navigate="ctxOpen = false" />
        <el-button style="margin-top:14px" type="primary" plain @click="ctxOpen = false; router.push(`/help/${ctxArt.id}`)">{{ $t('help.open_in_help') }}</el-button>
      </div>
    </el-drawer>
  </el-container>
</template>
<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuth } from '../store/auth'
import { setLang, tr } from '../i18n'
import ThemeToggle from './ThemeToggle.vue'
import PasswordDialog from './PasswordDialog.vue'
import HelpMarkdown from './HelpMarkdown.vue'
import { api } from '../api'

const auth = useAuth()
const route = useRoute()
const router = useRouter()
const i18n = useI18n()
const { locale } = i18n
const lang = ref(locale.value)
const collapsed = ref(window.innerWidth < 900)
const pwd = ref(!!auth.user?.must_change_password)
const forced = computed(() => !!auth.user?.must_change_password)
// Меню: «создать → допустить → использовать» (docs/decisions.md, № 24). Права на экраны не меняются — пункт скрыт,
// если у роли нет к нему доступа.
const dashboards = ref([])
const MAX_DASH = 8
async function loadDashboards() {
  try {
    const all = await api.get('dashboards', '/dashboards')
    dashboards.value = all.filter((d) => d.id !== 'monitoring' && (d.system || d.visibility === 'shared' || d.owner === auth.user?.id))
      .sort((x, y) => tr(x, 'title').localeCompare(tr(y, 'title'), 'ru'))
  } catch (e) { dashboards.value = [] }
}
const sections = computed(() => {
  const t = (k) => i18n.t('nav.' + k)
  const it = (index, key, perm) => (!perm || auth.can(perm) ? [{ index, label: t(key) }] : [])
  const dash = dashboards.value.slice(0, MAX_DASH).map((d) => ({ index: '/dashboards/' + d.id, label: tr(d, 'title'), dash: true,
    personal: !d.system && d.visibility !== 'shared' }))
  return [
    { key: 'sec_analytics', icon: 'TrendCharts', items: [...it('/', 'map'), ...it('/monitoring', 'monitoring'), ...dash,
      { index: '/dashboards', label: t('all_dashboards'), more: true }] },
    { key: 'sec_calc', icon: 'Odometer', items: [...it('/data', 'data'), ...it('/calculations', 'calculations')] },
    { key: 'sec_design', icon: 'EditPen', items: [...it('/dictionaries', 'dictionaries'), ...it('/algorithms', 'algorithms', 'algo.develop'),
      ...it('/design/calculations', 'calc_order', 'run.execute'), ...it('/design/dashboards', 'dash_design', 'dashboard.edit')] },
    { key: 'sec_manage', icon: 'Setting', items: [...it('/catalog', 'catalog'), ...it('/profiles', 'profiles'),
      ...it('/users', 'users', 'users.manage'), ...it('/audit', 'audit', 'audit.view')] },
  ].filter((sec) => sec.items.length)
})
// пункт меню для текущего адреса: вложенные страницы подсвечивают свой пункт
const ACTIVE = [
  [/^\/monitoring/, '/monitoring'], [/^\/data/, '/data'], [/^\/(calculations|runs)/, '/calculations'],
  [/^\/design\/calculations/, '/design/calculations'], [/^\/design\/dashboards/, '/design/dashboards'],
  [/^\/dictionaries/, '/dictionaries'], [/^\/algorithms/, '/algorithms'], [/^\/catalog/, '/catalog'], [/^\/profiles/, '/profiles'],
  [/^\/users/, '/users'], [/^\/audit/, '/audit'],
]
const active = computed(() => {
  const p = route.path
  if (p === '/') return '/'
  const m = p.match(/^\/dashboards\/([^/]+)/)
  if (m) return dashboards.value.slice(0, MAX_DASH).some((d) => d.id === m[1]) ? p : '/dashboards'
  if (p === '/dashboards') return '/dashboards'
  return ACTIVE.find(([re]) => re.test(p))?.[1] || ''
})
const sectionOf = (index) => sections.value.find((sec) => sec.items.some((i) => i.index === index))?.key
const openeds = [sectionOf(active.value) || 'sec_analytics']
const menuRef = ref(null)
watch(active, (v) => { const k = sectionOf(v); if (k && menuRef.value) menuRef.value.open(k) })
watch(() => route.path, (p, old) => { if (/dashboards/.test(p) || /dashboards/.test(old || '')) loadDashboards() })
onMounted(loadDashboards)
const initials = computed(() => (auth.user?.name || '?').split(/\s+/).map((s) => s[0]).slice(0, 2).join('').toUpperCase())
watch(() => auth.loggedIn, (v) => { if (!v) router.push({ path: '/login', query: { next: route.fullPath } }) })
const ctxOpen = ref(false)
const ctxArt = ref(null)
async function openContext() {
  try {
    const c = await api.get('help', '/context', { route: route.path, lang: locale.value })
    ctxArt.value = await api.get('help', `/articles/${c.id}`, { lang: locale.value, expand: 1 })
    ctxOpen.value = true
  } catch (e) { router.push('/help') }
}
function onCmd(c) {
  if (c === 'logout') { auth.logout(); router.push('/login') }
  if (c === 'password') pwd.value = true
}
</script>
<style scoped>
.layout { height: 100vh; }
.aside { background: var(--fs-nav); transition: width .2s; overflow-x: hidden; overflow-y: auto; }
.brand { display: flex; gap: 10px; align-items: center; padding: 14px 16px 10px; cursor: pointer; color: var(--fs-nav-text); }
.logo-body { fill: var(--fs-accent); }
.logo-eye { fill: var(--fs-nav); }
.b1 { font-weight: 600; font-size: 16px; letter-spacing: .01em; }
.b2 { font-size: 11px; color: var(--fs-nav-muted); line-height: 1.25; margin-top: 2px; }
.aside :deep(.el-menu) { border-right: none; --el-menu-bg-color: var(--fs-nav); --el-menu-text-color: var(--fs-nav-text);
  --el-menu-active-color: var(--fs-nav-text); --el-menu-hover-bg-color: rgba(255, 255, 255, .08); --el-menu-item-height: 44px; }
.aside :deep(.el-sub-menu__title) { height: 42px; margin: 2px 6px; border-radius: 6px; padding-left: 10px !important; font-weight: 600; color: var(--fs-nav-text); }
.aside :deep(.el-sub-menu__title:hover) { background: rgba(255, 255, 255, .08); }
.aside :deep(.el-sub-menu.is-active > .el-sub-menu__title) { color: var(--fs-nav-text); }
.aside :deep(.el-sub-menu .el-menu-item) { border-radius: 6px; margin: 1px 6px 1px 6px; padding-left: 40px !important; padding-right: 8px;
  height: 34px; line-height: 34px; color: var(--fs-nav-text); }
.aside :deep(.el-sub-menu .el-menu-item.nav-dash) { color: var(--fs-nav-muted); }
.aside :deep(.el-sub-menu .el-menu-item.nav-more) { color: var(--fs-nav-muted); font-size: 13px; }
.nav-label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
.nav-personal { font-size: 12px; margin: 0 0 0 6px !important; color: var(--fs-nav-muted); }
.nav-sep { list-style: none; height: 1px; background: rgba(255, 255, 255, .14); margin: 10px 14px; }
.help-link { color: var(--fs-muted); }
.aside :deep(.el-menu--collapse) { width: 64px; }
.aside :deep(.el-menu--collapse .el-sub-menu__title) { margin: 2px 8px; padding: 0 !important; justify-content: center; }
.aside :deep(.el-menu--collapse .el-sub-menu__title .el-icon) { margin-right: 0; }
.aside :deep(.el-menu--collapse .el-sub-menu__icon-arrow) { display: none; }
.aside :deep(.el-menu-item.is-active) { color: var(--fs-nav-text); background: var(--fs-nav-active) !important; box-shadow: inset 3px 0 0 var(--fs-accent); font-weight: 500; }
.avatar { background: var(--fs-primary-2); font-weight: 600; }
.header { display: flex; align-items: center; gap: 14px; background: var(--fs-card); border-bottom: 1px solid var(--fs-line); }
.user { display: flex; align-items: center; gap: 8px; cursor: pointer; }
.uname { font-size: 13px; line-height: 1.15; }
.urole { color: var(--fs-muted); font-size: 11px; }
.main { padding: 0; overflow: auto; }
</style>
