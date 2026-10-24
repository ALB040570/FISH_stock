<template>
  <el-container class="layout" :data-cabinet="cab.key">
    <el-aside :width="collapsed ? '64px' : '260px'" class="aside">
      <div class="brand" @click="$router.push(cab.base)">
        <svg viewBox="0 0 64 64" width="30" height="30"><path class="logo-body" d="M6 32c10-14 30-16 42-6l10-8v28l-10-8c-12 10-32 8-42-6z"/><circle class="logo-eye" cx="20" cy="29" r="3"/></svg>
        <div v-if="!collapsed"><div class="b1">FishStock</div><div class="b2">{{ $t('app.subtitle') }}</div></div>
      </div>
      <div class="cab-title" :title="$t('cab.' + cab.key)">
        <el-icon :size="18"><component :is="cab.icon" /></el-icon><span v-if="!collapsed">{{ $t('cab.' + cab.key) }}</span>
      </div>
      <el-menu :default-active="active" router :collapse="collapsed" popper-class="fs-nav-popup">
        <el-menu-item v-for="it in items" :key="it.index" :index="it.index" :class="{ 'nav-dash': it.dash, 'nav-more': it.more }">
          <el-icon><component :is="it.icon" /></el-icon>
          <template #title>
            <span class="nav-label">{{ it.label }}</span>
            <el-icon v-if="it.personal" class="nav-personal" :title="$t('nav.personal')"><Lock /></el-icon>
          </template>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header" height="52px">
        <el-button text @click="collapsed = !collapsed"><el-icon :size="18"><Fold v-if="!collapsed" /><Expand v-else /></el-icon></el-button>
        <el-dropdown v-if="cabs.length > 1" trigger="click" class="cab-switch" @command="hardGo">
          <el-button text :title="$t('cab.switch')"><el-icon><Grid /></el-icon><span class="hide-sm">&nbsp;{{ $t('cab.switch') }}</span><el-icon class="el-icon--right"><ArrowDown /></el-icon></el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item v-for="c in cabs" :key="c.key" :command="c.base" :disabled="c.key === cab.key">
                <el-icon><component :is="c.icon" /></el-icon>{{ $t('cab.' + c.key) }}
              </el-dropdown-item>
              <el-dropdown-item v-if="hasFlow(auth.role)" command="/" divided><el-icon><Share /></el-icon>{{ $t('flow.title') }}</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <div class="grow" />
        <el-button text class="help-link" :title="$t('nav.help')" @click="$router.push(helpPath())"><el-icon><Reading /></el-icon><span class="hide-sm">&nbsp;{{ $t('nav.help') }}</span></el-button>
        <el-tooltip :content="$t('help.context')" placement="bottom">
          <span class="hide-sm ctx-help">
          <el-button circle size="small" @click="openContext"><el-icon><QuestionFilled /></el-icon></el-button></span>
        </el-tooltip>
        <ThemeToggle />
        <el-radio-group v-model="lang" size="small" @change="setLang">
          <el-radio-button value="ru">РУС</el-radio-button>
          <el-radio-button value="kk">ҚАЗ</el-radio-button>
        </el-radio-group>
        <el-dropdown trigger="click" @command="onCmd">
          <span class="user">
            <UserAvatar :user="auth.user" :size="28" />
            <span class="uname hide-sm">{{ auth.user?.name }}<br><span class="urole">{{ $t('roles.' + auth.role) }}</span></span>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="profile"><el-icon><User /></el-icon>{{ $t('profile.title') }}</el-dropdown-item>
              <el-dropdown-item command="password"><el-icon><Lock /></el-icon>{{ $t('nav.password') }}</el-dropdown-item>
              <el-dropdown-item command="logout" divided>{{ $t('nav.logout') }}</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>
      <el-main class="main"><slot /></el-main>
    </el-container>
    <PasswordDialog v-model="pwd" :forced="forced" />
    <ProfileDialog v-model="prof" @password="prof = false; pwd = true" />
    <el-drawer v-model="ctxOpen" :title="ctxArt?.title || $t('nav.help')" size="560px">
      <div v-if="ctxArt">
        <HelpMarkdown :source="ctxArt.markdown" strip-title @navigate="ctxOpen = false" />
        <el-button style="margin-top:14px" type="primary" plain @click="ctxOpen = false; router.push(helpPath(ctxArt.id))">{{ $t('help.open_in_help') }}</el-button>
      </div>
    </el-drawer>
  </el-container>
</template>
<script setup>
import { computed, onMounted, ref, watch, watchEffect } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuth } from '../store/auth'
import { setLang, tr } from '../i18n'
import { cabinet, cabinetsFor, canEnter, currentCabinet, hardGo, hasFlow, helpPath, helpRoute } from '../cabinets'
import { saveLast } from '../lastPlace'
import ThemeToggle from './ThemeToggle.vue'
import PasswordDialog from './PasswordDialog.vue'
import ProfileDialog from './ProfileDialog.vue'
import UserAvatar from './UserAvatar.vue'
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
const prof = ref(false)
const forced = computed(() => !!auth.user?.must_change_password)
// Кабинет — отдельный интерфейс со своим меню (docs/decisions.md, № 52). Права на экраны не меняются — пункт скрыт,
// если у роли нет к нему доступа.
const cab = currentCabinet()
const cabs = computed(() => cabinetsFor(auth.role))
watchEffect(() => { document.title = `FishStock — ${i18n.t('cab.' + cab.key)}` })
const dashboards = ref([])
const MAX_DASH = 8
async function loadDashboards() {
  if (cab.key !== 'monitoring') return
  try {
    const all = await api.get('dashboards', '/dashboards')
    dashboards.value = all.filter((d) => d.id !== 'monitoring' && (d.system || d.visibility === 'shared' || d.owner === auth.user?.id))
      .sort((x, y) => tr(x, 'title').localeCompare(tr(y, 'title'), 'ru'))
  } catch (e) { dashboards.value = [] }
}
const items = computed(() => {
  const t = (k) => i18n.t(k)
  const it = (index, key, icon, perm) => (!perm || auth.can(perm) ? [{ index, label: t(key), icon }] : [])
  switch (cab.key) {
    case 'monitoring': return [
      ...it('/monitoring/', 'nav.map', 'MapLocation'), ...it('/monitoring/waterbody', 'cab.waterbody', 'DataLine'),
      ...dashboards.value.slice(0, MAX_DASH).map((d) => ({ index: '/monitoring/dashboards/' + d.id, label: tr(d, 'title'), icon: 'Histogram',
        dash: true, personal: !d.system && d.visibility !== 'shared' })),
      { index: '/monitoring/dashboards', label: t('nav.all_dashboards'), icon: 'Grid', more: true }]
    case 'input': return it('/input/datasets', 'nav.data', 'Files')
    case 'calc': return [...it('/calc/calculations', 'nav.calculations', 'Odometer'), ...it('/calc/runs', 'nav.runs', 'List'),
      ...it('/calc/profiles', 'nav.profiles', 'Operation', 'profile.view')]
    case 'design': return [...it('/design/dictionaries', 'nav.dictionaries', 'Collection'),
      ...it('/design/algorithms', 'nav.algorithms', 'Cpu', 'algo.develop'), ...it('/design/calculations', 'nav.calc_order', 'Share', 'run.execute'),
      ...it('/design/dashboards', 'nav.dash_design', 'Histogram', 'dashboard.edit'),
      ...it('/design/signal-rules', 'cab.signal_rules', 'Bell', 'dashboard.edit'),
      // кто не входит в «Администрирование» — каталог алгоритмов для просмотра; без права правки — список дашбордов (№ 62)
      ...(canEnter(cabinet('admin'), auth.role) ? [] : it('/design/catalog', 'nav.catalog', 'Box', 'catalog.view')),
      ...(auth.can('dashboard.edit') ? [] : it('/monitoring/dashboards', 'nav.dashboards', 'Histogram'))]
    case 'admin': return [...it('/admin/users', 'nav.users', 'User', 'users.manage'), ...it('/admin/audit', 'nav.audit', 'Tickets', 'audit.view'),
      ...it('/admin/catalog', 'nav.catalog', 'Box')]
  }
  return []
})
// пункт меню для текущего адреса: вложенные страницы подсвечивают свой пункт (самый длинный подходящий)
const active = computed(() => {
  const p = route.path.replace(/\/+$/, '') || '/'
  if (cab.key === 'monitoring' && p === '/monitoring') return '/monitoring/'
  const m = p.match(/^\/monitoring\/dashboards\/([^/]+)/)
  if (m) return items.value.some((i) => i.index === p) ? p : '/monitoring/dashboards'
  const cand = items.value.filter((i) => i.index !== cab.base && (p === i.index || p.startsWith(i.index + '/')))
  return cand.sort((a, b) => b.index.length - a.index.length)[0]?.index || ''
})
watch(() => route.path, (p, old) => { if (/dashboards/.test(p) || /dashboards/.test(old || '')) loadDashboards() })
// «Продолжить» на стартовой странице: последний экран (кабинет · пункт меню · водоём)
watch([() => route.fullPath, active, items], () => {
  const item = items.value.find((i) => i.index === active.value)
  saveLast(auth.user?.id, { path: route.fullPath, cab: cab.key, item: item?.label || '', wb: route.params.wb || route.query.wb || '' })
}, { immediate: true })
onMounted(loadDashboards)
watch(() => auth.loggedIn, (v) => { if (!v) hardGo('/login?next=' + encodeURIComponent(route.fullPath)) })
const ctxOpen = ref(false)
const ctxArt = ref(null)
async function openContext() {
  try {
    // справка привязывает статьи к экранам по прежним адресам — переводим адрес кабинета обратно
    const c = await api.get('help', '/context', { route: helpRoute(route.path), lang: locale.value })
    ctxArt.value = await api.get('help', `/articles/${c.id}`, { lang: locale.value, expand: 1 })
    ctxOpen.value = true
  } catch (e) { router.push(helpPath()) }
}
function onCmd(c) {
  if (c === 'logout') { auth.logout(); hardGo('/login') }
  if (c === 'password') pwd.value = true
  if (c === 'profile') prof.value = true
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
.nav-label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
.nav-personal { font-size: 12px; margin: 0 0 0 6px !important; color: var(--fs-nav-muted); }
.cab-title { display: flex; align-items: center; gap: 8px; margin: 4px 12px 8px; padding: 8px 10px; border-radius: 6px;
  background: rgba(255, 255, 255, .08); color: var(--fs-nav-text); font-weight: 600; font-size: 14px; white-space: nowrap; overflow: hidden; }
.aside :deep(.el-menu > .el-menu-item) { border-radius: 6px; margin: 1px 6px; height: 40px; line-height: 40px; color: var(--fs-nav-text); }
.aside :deep(.el-menu > .el-menu-item.nav-dash) { color: var(--fs-nav-muted); height: 34px; line-height: 34px; }
.aside :deep(.el-menu > .el-menu-item.nav-more) { color: var(--fs-nav-muted); font-size: 13px; }
.aside :deep(.el-menu--collapse > .el-menu-item) { margin: 1px 8px; padding: 0 !important; justify-content: center; }
.help-link { color: var(--fs-muted); }
.aside :deep(.el-menu--collapse) { width: 64px; }
.aside :deep(.el-menu-item.is-active) { color: var(--fs-nav-text); background: var(--fs-nav-active) !important; box-shadow: inset 3px 0 0 var(--fs-accent); font-weight: 500; }
.header { display: flex; align-items: center; gap: 14px; background: var(--fs-card); border-bottom: 2px solid var(--fs-primary-2); } /* «небо» — линия под шапкой */
.user { display: flex; align-items: center; gap: 8px; cursor: pointer; }
.uname { font-size: 13px; line-height: 1.15; }
.urole { color: var(--fs-muted); font-size: 11px; }
.main { padding: 0; overflow: auto; }
.header > * { flex-shrink: 0; }
.header > .grow { flex: 1 1 0; min-width: 0; }
/* телефон: значки без подписей, без имени пользователя; справка по экрану — из «Справки» */
@media (max-width: 640px) {
  .header { gap: 6px; padding: 0 8px; }
  .header :deep(.el-button + .el-button) { margin-left: 0; }
  .header :deep(.el-button.is-text) { padding: 6px; }
  .header :deep(.cab-switch .el-icon--right) { margin-left: 2px; }
  .hide-sm { display: none !important; }
}
</style>
