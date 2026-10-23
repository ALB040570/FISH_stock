<template>
  <div class="cab-page">
    <header class="top">
      <div class="brand">
        <svg viewBox="0 0 64 64" width="30" height="30"><path class="logo-body" d="M6 32c10-14 30-16 42-6l10-8v28l-10-8c-12 10-32 8-42-6z"/><circle class="logo-eye" cx="20" cy="29" r="3"/></svg>
        <div><div class="b1">FishStock</div><div class="b2">{{ $t('app.subtitle') }}</div></div>
      </div>
      <div class="grow" />
      <ThemeToggle />
      <el-radio-group v-model="lang" size="small" @change="setLang">
        <el-radio-button value="ru">РУС</el-radio-button><el-radio-button value="kk">ҚАЗ</el-radio-button>
      </el-radio-group>
      <span class="user">{{ auth.user?.name }} · {{ $t('roles.' + auth.role) }}</span>
      <el-button text @click="logout">{{ $t('nav.logout') }}</el-button>
    </header>
    <main class="body">
      <h2>{{ $t('cab.choose') }}</h2>
      <div class="tiles">
        <a v-for="c in cabs" :key="c.key" :href="c.base" class="tile" :data-cabinet="c.key">
          <el-icon :size="28" class="ticon"><component :is="c.icon" /></el-icon>
          <div class="tname">{{ $t('cab.' + c.key) }}</div>
          <div class="tdesc">{{ $t('cab.' + c.key + '_d') }}</div>
        </a>
      </div>
    </main>
  </div>
</template>
<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuth } from '../store/auth'
import { setLang } from '../i18n'
import { cabinetsFor, hardGo } from '../cabinets'
import ThemeToggle from '../components/ThemeToggle.vue'

const auth = useAuth()
const { locale } = useI18n()
const lang = ref(locale.value)
const cabs = computed(() => cabinetsFor(auth.role))
document.title = 'FishStock'
// с единственным кабинетом выбирать нечего
onMounted(() => { if (cabs.value.length === 1) hardGo(cabs.value[0].base) })
function logout() { auth.logout(); hardGo('/login') }
</script>
<style scoped>
.cab-page { min-height: 100vh; background: var(--fs-bg); }
.top { display: flex; align-items: center; gap: 12px; padding: 10px 24px; background: var(--fs-nav); color: var(--fs-nav-text); }
.top :deep(.el-button.is-text) { color: var(--fs-nav-text); }
.brand { display: flex; gap: 10px; align-items: center; }
.b1 { font-weight: 600; font-size: 16px; }
.b2 { font-size: 11px; color: var(--fs-nav-muted); }
.logo-body { fill: var(--fs-accent); }
.logo-eye { fill: var(--fs-nav); }
.grow { flex: 1; }
.user { font-size: 13px; color: var(--fs-nav-muted); }
.body { max-width: 1100px; margin: 0 auto; padding: 40px 24px; }
.body h2 { font-size: 22px; margin-bottom: 20px; }
.tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; }
.tile { display: block; padding: 22px 20px; border-radius: var(--fs-radius); background: var(--fs-card); border: 1px solid var(--fs-line);
  color: var(--fs-text); text-decoration: none; transition: box-shadow .15s, border-color .15s; }
.tile:hover, .tile:focus-visible { border-color: var(--fs-primary); box-shadow: var(--fs-shadow-pop); outline: none; }
.ticon { color: var(--fs-primary); }
.tname { font-size: 17px; font-weight: 600; margin: 10px 0 6px; }
.tdesc { font-size: 13px; color: var(--fs-muted); line-height: 1.45; }
@media (max-width: 700px) { .top { flex-wrap: wrap; padding: 10px 16px; } .body { padding: 24px 16px; } }
</style>
