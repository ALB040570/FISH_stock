<template>
  <div class="flow-page">
    <section class="hero">
    <div class="waves" aria-hidden="true" />
    <header class="top">
      <div class="brand">
        <svg viewBox="0 0 64 64" width="30" height="30"><path class="logo-body" d="M6 32c10-14 30-16 42-6l10-8v28l-10-8c-12 10-32 8-42-6z"/><circle class="logo-eye" cx="20" cy="29" r="3"/></svg>
        <div><div class="b1">FishStock</div><div class="b2">{{ $t('app.subtitle') }}</div></div>
      </div>
      <div class="grow" />
      <a class="top-link" :href="helpPath()"><el-icon><Reading /></el-icon>&nbsp;{{ $t('nav.help') }}</a>
      <ThemeToggle />
      <el-radio-group v-model="lang" size="small" @change="setLang">
        <el-radio-button value="ru">РУС</el-radio-button><el-radio-button value="kk">ҚАЗ</el-radio-button>
      </el-radio-group>
      <el-dropdown trigger="click" @command="onCmd">
        <span class="user"><UserAvatar :user="auth.user" :size="28" />
          <span class="uname">{{ auth.user?.name }}<br><span class="urole">{{ $t('roles.' + auth.role) }}</span></span></span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="profile"><el-icon><User /></el-icon>{{ $t('profile.title') }}</el-dropdown-item>
              <el-dropdown-item command="password"><el-icon><Lock /></el-icon>{{ $t('nav.password') }}</el-dropdown-item>
            <el-dropdown-item command="logout" divided>{{ $t('nav.logout') }}</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </header>

      <div class="hello">
        <div class="hello-text">
          <h1>{{ greeting }}{{ firstName ? ', ' + firstName : '' }}</h1>
          <div class="muted">
            {{ $t('roles.' + auth.role) }}
            <template v-if="flow"> · {{ $t('flow.with_data', { n: flow.withData }) }}</template>
            <span v-if="updatedAt" class="faint"> · {{ $t('flow.updated', { t: updatedAt }) }}</span>
          </div>
          <div v-if="flow?.waiting" class="attn"><span class="dot" :style="{ background: MAP_STATE.stale }" />{{ $t('flow.waiting', { n: flow.waiting }) }}</div>
        </div>
        <a v-if="last && last.cab" class="continue" :href="last.path" data-test="continue">
          <el-icon><Clock /></el-icon><span><span class="faint">{{ $t('flow.continue') }}:</span> {{ lastLabel }}</span><el-icon><Right /></el-icon>
        </a>
      </div>

      <div class="section-label on-hero"><b>{{ $t('flow.path') }}:</b> {{ $t('flow.path_hint') }}</div>
    </section>

    <main class="body">
      <div class="flow" :class="{ loading }">
        <!-- Ввод данных -->
        <div class="tile" role="link" tabindex="0" data-cabinet="input" @click="go('input')" @keydown.enter="go('input')">
          <div class="tname"><el-icon><component :is="cab('input').icon" /></el-icon><a :href="cab('input').base" @click.stop>{{ $t('cab.input') }}</a><kbd>{{ keyOf('input') }}</kbd></div>
          <div class="tdesc">{{ $t('flow.p_input') }}</div>
          <div v-if="flow" class="metrics">
            <div><b>{{ flow.datasets }}</b><span>{{ $t('flow.datasets') }}</span></div>
            <div v-if="flow.lastUpload"><b>{{ shortDate(flow.lastUpload.at) }}</b><span>{{ $t('flow.last_upload') }} · {{ short(flow.lastUpload.name) }}</span></div>
          </div>
          <div v-if="flow?.total" class="note">{{ $t('flow.no_data', { a: flow.withData, b: flow.total }) }}</div>
          <span class="act">{{ $t(auth.can('data.edit') ? 'flow.act_input' : 'flow.act_input_view') }} →</span>
        </div>

        <!-- труба: ждут расчёта -->
        <div class="pipe" data-pipe="wait_calc">
          <div class="pbody">
          <div class="plabel">{{ $t('flow.pipe_calc') }}</div>
          <div class="pchips">
            <template v-if="flow?.byStage.wait_calc.length">
              <a v-for="w in shown('wait_calc')" :key="w.code" class="chip" :href="href(w)" :title="w.name + ' — ' + $t(w.failed ? 'flow.hint_failed' : 'flow.hint_calc')">
                <span class="dot" :style="{ background: w.failed ? RUN_STEP.failed : MAP_STATE.stale }" /><span class="cn">{{ short(w.name) }}</span>
                <el-icon v-if="w.failed" class="ci"><WarningFilled /></el-icon>
              </a>
              <button v-if="rest('wait_calc')" class="chip more" @click="toggle('wait_calc')">{{ open.wait_calc ? $t('flow.less') : $t('flow.more', { n: rest('wait_calc') }) }}</button>
            </template>
            <span v-else-if="flow" class="free">{{ $t('flow.free') }}</span>
          </div>
          </div>
          <div class="pline" aria-hidden="true"><el-icon><ArrowRight /></el-icon></div>
        </div>

        <!-- Расчёты -->
        <div class="tile" role="link" tabindex="0" data-cabinet="calc" @click="go('calc')" @keydown.enter="go('calc')">
          <div class="tname"><el-icon><component :is="cab('calc').icon" /></el-icon><a :href="cab('calc').base" @click.stop>{{ $t('cab.calc') }}</a><kbd>{{ keyOf('calc') }}</kbd></div>
          <div class="tdesc">{{ $t('flow.p_calc') }}</div>
          <div v-if="flow" class="metrics">
            <div><b>{{ flow.running }}</b><span>{{ $t('flow.running') }}</span></div>
            <div><b>{{ flow.queued }}</b><span>{{ $t('flow.queued') }}</span></div>
          </div>
          <div v-if="flow?.byStage.running.length" class="inner">
            <a v-for="w in shown('running')" :key="w.code" class="chip" :href="href(w)" :title="w.name + ' — ' + $t('flow.hint_running')" @click.stop>
              <span class="dot pulse" :style="{ background: RUN_STEP.running }" /><span class="cn">{{ short(w.name) }}</span> ·
              {{ w.queued ? $t('flow.queued') : $t('flow.step', runProgress(w.run)) }}
            </a>
            <button v-if="rest('running')" class="chip more" @click.stop="toggle('running')">{{ open.running ? $t('flow.less') : $t('flow.more', { n: rest('running') }) }}</button>
          </div>
          <span class="act">{{ $t('flow.act_calc') }} →</span>
        </div>

        <!-- труба: ждут отметки основного -->
        <div class="pipe" data-pipe="wait_main">
          <div class="pbody">
          <div class="plabel">{{ $t('flow.pipe_main') }}</div>
          <div class="pchips">
            <template v-if="flow?.byStage.wait_main.length">
              <a v-for="w in shown('wait_main')" :key="w.code" class="chip" :href="href(w)" :title="w.name + ' — ' + $t('flow.hint_main')">
                <span class="dot" :style="{ background: MAP_STATE.has_data }" /><span class="cn">{{ short(w.name) }}</span>
              </a>
              <button v-if="rest('wait_main')" class="chip more" @click="toggle('wait_main')">{{ open.wait_main ? $t('flow.less') : $t('flow.more', { n: rest('wait_main') }) }}</button>
            </template>
            <span v-else-if="flow" class="free">{{ $t('flow.free') }}</span>
          </div>
          </div>
          <div class="pline" aria-hidden="true"><el-icon><ArrowRight /></el-icon></div>
        </div>

        <!-- Мониторинг -->
        <div class="tile" role="link" tabindex="0" data-cabinet="monitoring" @click="go('monitoring')" @keydown.enter="go('monitoring')">
          <div class="tname"><el-icon><component :is="cab('monitoring').icon" /></el-icon><a :href="cab('monitoring').base" @click.stop>{{ $t('cab.monitoring') }}</a><kbd>{{ keyOf('monitoring') }}</kbd></div>
          <div class="tdesc">{{ $t('flow.p_monitoring') }}</div>
          <div v-if="flow" class="metrics">
            <div><b>{{ $t('flow.of', { a: flow.byStage.ready.length, b: flow.withData }) }}</b><span>{{ $t('flow.ready') }}</span></div>
          </div>
          <div v-if="flow?.byStage.ready.length" class="inner">
            <a v-for="w in shown('ready')" :key="w.code" class="chip" :href="href(w)" :title="w.name + ' — ' + $t('flow.hint_ready')" @click.stop>
              <span class="dot" :style="{ background: MAP_STATE.has_run }" /><span class="cn">{{ short(w.name) }}</span>
            </a>
            <button v-if="rest('ready')" class="chip more" @click.stop="toggle('ready')">{{ open.ready ? $t('flow.less') : $t('flow.more', { n: rest('ready') }) }}</button>
          </div>
          <span class="act">{{ $t('flow.act_monitoring') }} →</span>
        </div>
      </div>

      <div class="legend">
        <span><i class="dot" :style="{ background: MAP_STATE.stale }" />{{ $t('flow.legend_wait') }}</span>
        <span><i class="dot" :style="{ background: RUN_STEP.running }" />{{ $t('flow.legend_run') }}</span>
        <span><i class="dot" :style="{ background: MAP_STATE.has_data }" />{{ $t('flow.legend_main') }}</span>
        <span><i class="dot" :style="{ background: MAP_STATE.has_run }" />{{ $t('flow.legend_ready') }}</span>
      </div>

      <!-- итог для первого взгляда: ПДУ по основным расчётам (золото — только ПДУ, тема «Степь и небо») -->
      <template v-if="flow">
        <div class="section-label">{{ $t('flow.res_title') }}</div>
        <div v-if="flow.results.length" class="results">
          <a v-for="r in flow.results" :key="r.code" class="res" :href="resultLink(r, auth.can('results.view'))" :data-result="r.code">
            <div class="rname">{{ r.name }}</div>
            <template v-if="r.rows.length">
              <div class="runit">{{ $t('flow.res_unit', { y: r.year }) }}</div>
              <div v-for="x in r.rows.slice(0, 3)" :key="x.species" class="rrow"><span>{{ x.species }}</span><b>{{ fmtT(x.pdu_t) }}</b></div>
              <div v-if="r.rows.length > 3" class="rmore">{{ $t('flow.res_more', { n: r.rows.length - 3 }) }}</div>
            </template>
            <div v-else class="runit">{{ $t('flow.res_npc') }}</div>
            <span class="act">{{ $t('flow.res_open') }} →</span>
          </a>
        </div>
        <div v-else class="note">{{ $t('flow.res_empty') }}</div>
      </template>

      <template v-if="baseCabs.length">
        <div class="section-label">{{ $t('flow.base') }}</div>
        <div class="base">
          <a v-for="c in baseCabs" :key="c.key" class="tile row" :href="c.base" :data-cabinet="c.key">
            <el-icon :size="22" class="bicon"><component :is="c.icon" /></el-icon>
            <div class="grow">
              <div class="tname">{{ $t('cab.' + c.key) }}<kbd>{{ keyOf(c.key) }}</kbd></div>
              <div class="tdesc">{{ baseLine(c.key) || $t('cab.' + c.key + '_d') }}</div>
            </div>
          </a>
        </div>
      </template>
      <el-alert v-if="error" type="warning" :closable="false" :title="error" style="margin-top:14px" />
    </main>
    <PasswordDialog v-model="pwd" :forced="forced" />
    <ProfileDialog v-model="prof" @password="prof = false; pwd = true" />
  </div>
</template>
<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuth } from '../store/auth'
import { setLang, tr } from '../i18n'
import { api } from '../api'
import { MAP_STATE, RUN_STEP } from '../theme'
import { FLOW_BASE, FLOW_PATH, cabinet, cabinetsFor, canEnter, hardGo, hasFlow, helpPath, mainPage } from '../cabinets'
import { buildFlow, resultLink, runProgress, stageLink } from '../flow'
import { loadLast } from '../lastPlace'
import ThemeToggle from '../components/ThemeToggle.vue'
import PasswordDialog from '../components/PasswordDialog.vue'
import ProfileDialog from '../components/ProfileDialog.vue'
import UserAvatar from '../components/UserAvatar.vue'

// Стартовая страница «Поток» (docs/decisions.md, № 53): путь данных Ввод → Расчёты → Мониторинг, между кабинетами —
// «трубы» с водоёмами, ждущими следующего этапа. Состояния — только факты из сервисов (src/flow.js).
const auth = useAuth()
const i18n = useI18n()
const lang = ref(i18n.locale.value)
const cab = cabinet
const mine = computed(() => cabinetsFor(auth.role).map((c) => c.key))
const order = computed(() => [...FLOW_PATH, ...FLOW_BASE].filter((k) => mine.value.includes(k)))
const keyOf = (k) => order.value.indexOf(k) + 1
const baseCabs = computed(() => FLOW_BASE.filter((k) => mine.value.includes(k)).map(cabinet))
const pwd = ref(!!auth.user?.must_change_password)
const prof = ref(false)
const forced = computed(() => !!auth.user?.must_change_password)
const firstName = computed(() => {
  // «Фамилия Имя Отчество» или «Имя Фамилия»: обращаемся по имени — второму слову из трёх, иначе первому
  const p = (auth.user?.name || '').trim().split(/\s+/).filter(Boolean)
  return p.length >= 3 ? p[1] : p[0] || ''
})
const greeting = computed(() => {
  const h = new Date().getHours()
  return i18n.t(h < 5 ? 'flow.greet_night' : h < 12 ? 'flow.greet_morning' : h < 17 ? 'flow.greet_day' : h < 23 ? 'flow.greet_evening' : 'flow.greet_night')
})
const last = ref(loadLast(auth.user?.id))
const wbNames = ref({})
const lastLabel = computed(() => {
  const l = last.value
  if (!l) return ''
  return [l.cab ? i18n.t('cab.' + l.cab) : '', l.item, l.wb ? wbNames.value[l.wb] || l.wb : ''].filter(Boolean).join(' · ')
})
const fmtT = (v) => (v >= 100 ? Math.round(v) : Math.round(v * 10) / 10).toLocaleString('ru-RU')
const shortDate = (s) => (s ? new Date(s).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' }) : '')

const loading = ref(true)
const error = ref('')
const flow = ref(null)
const extra = reactive({})
const updatedAt = ref('')
const open = reactive({})
const LIMIT = 3
const shown = (s) => (open[s] ? flow.value.byStage[s] : flow.value.byStage[s].slice(0, LIMIT))
const rest = (s) => Math.max(0, (flow.value?.byStage[s].length || 0) - LIMIT)
const toggle = (s) => { open[s] = !open[s] }
const go = (k) => hardGo(cabinet(k).base)
// короткое название водоёма для трубы: без уточнения в скобках, «водохранилище» → «вдхр.»
const short = (n) => String(n || '').replace(/\s*\([^)]*\)/g, '').replace(/\s*водохранилище/i, ' вдхр.').replace(/\s*су қоймасы/i, ' с.қ.').trim()
const href = (w) => { const l = stageLink(w); return l.path + (l.query ? '?' + new URLSearchParams(l.query) : '') }

function baseLine(key) {
  const t = (k, n) => (n === undefined || n === null ? null : i18n.t(k, { n }))
  if (key === 'design') return [t('flow.dicts', extra.dicts), t('flow.types', extra.types), t('flow.algos', extra.algos)].filter(Boolean).join(' · ')
  if (key === 'admin') {
    return [t('flow.users', extra.users), extra.blocked ? t('flow.blocked', extra.blocked) : null, t('flow.catalog', extra.catalog),
      auth.can('audit.view') ? i18n.t('flow.journal') : null].filter(Boolean).join(' · ')
  }
  return ''
}

const safe = (p) => p.catch(() => null)
async function load() {
  try {
    const [fc, ds, rs, q] = await Promise.all([
      api.get('data-model', '/water-bodies.geojson'), api.get('data-admin', '/water-bodies/status'),
      api.get('algo-admin', '/water-bodies/status'), safe(api.get('algo-admin', '/queue')),
    ])
    const names = Object.fromEntries((fc.features || []).map((f) => [f.properties.code, tr(f.properties, 'name')]))
    wbNames.value = names
    flow.value = buildFlow({ names, data: ds || {}, runs: rs || {}, queue: q })
    error.value = ''
    updatedAt.value = new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
  } catch (e) { error.value = e.message } finally { loading.value = false }
}
async function loadExtra() {
  const len = (x) => (Array.isArray(x) ? x.length : null)
  const [ents, types, algos, users, cat] = await Promise.all([
    safe(api.get('data-model', '/entities')), safe(api.get('data-model', '/dataset-types')),
    auth.can('algo.develop') ? safe(api.get('algo-model', '/algorithms')) : null,
    auth.can('users.manage') ? safe(api.get('users', '/users')) : null,
    canEnter(cabinet('admin'), auth.role) ? safe(api.get('algo-admin', '/catalog')) : null,
  ])
  Object.assign(extra, { dicts: len(ents), types: len(types), algos: len(algos), users: len(users),
    blocked: Array.isArray(users) ? users.filter((u) => u.blocked).length : null, catalog: len(cat) })
}

// обратная связь: очередь и состояния обновляются сами
let timer = null
function onKey(e) {
  if (e.ctrlKey || e.metaKey || e.altKey || /input|textarea|select/i.test(e.target?.tagName || '')) return
  const k = order.value[Number(e.key) - 1]
  if (k) hardGo(cabinet(k).base)
}
onMounted(() => {
  if (!hasFlow(auth.role)) { hardGo(mainPage(auth.role)); return }
  document.title = 'FishStock — ' + i18n.t('flow.title')
  load(); loadExtra()
  timer = setInterval(load, 30000)
  window.addEventListener('keydown', onKey)
})
onBeforeUnmount(() => { clearInterval(timer); window.removeEventListener('keydown', onKey) })
function onCmd(c) {
  if (c === 'logout') { auth.logout(); hardGo('/login') }
  if (c === 'password') pwd.value = true
  if (c === 'profile') prof.value = true
}
</script>
<style scoped>
.flow-page { min-height: 100vh; background: var(--fs-bg); color: var(--fs-text); }
/* полоса «Степь и небо»: тёмно-синий фон меню, светлый текст, волны как на экране входа */
.hero { position: relative; overflow: hidden; color: var(--fs-nav-text); padding-bottom: 92px;
  background: linear-gradient(160deg, var(--fs-nav-active) 0%, var(--fs-nav) 60%, var(--fs-nav) 100%); }
.waves { position: absolute; left: -10%; right: -10%; bottom: -70px; height: 190px; border-radius: 50%; pointer-events: none;
  background: rgba(255, 255, 255, .05); box-shadow: 0 -36px 0 rgba(255, 255, 255, .035); }
.top { position: relative; display: flex; align-items: center; gap: 14px; padding: 10px 24px; border-bottom: 1px solid rgba(255, 255, 255, .1); }
.brand { display: flex; gap: 10px; align-items: center; }
.b1 { font-weight: 600; font-size: 16px; }
.b2 { font-size: 11px; color: var(--fs-nav-muted); }
.logo-body { fill: var(--fs-accent); }
.logo-eye { fill: var(--fs-nav); }
.grow { flex: 1; min-width: 0; }
.top-link { color: var(--fs-nav-muted); text-decoration: none; display: inline-flex; align-items: center; font-size: 14px; }
.top-link:hover { color: var(--fs-nav-text); }
.top :deep(.el-button) { background: transparent; border-color: rgba(255, 255, 255, .25); color: var(--fs-nav-text); }
.top :deep(.el-radio-button__inner) { background: transparent; border-color: rgba(255, 255, 255, .25); color: var(--fs-nav-muted); box-shadow: none; }
.top :deep(.el-radio-button.is-active .el-radio-button__inner) { background: var(--fs-primary-2); border-color: var(--fs-primary-2); color: var(--fs-nav-active); }
.user { display: flex; align-items: center; gap: 8px; cursor: pointer; color: var(--fs-nav-text); }
.uname { font-size: 13px; line-height: 1.15; }
.urole { color: var(--fs-nav-muted); font-size: 11px; }
.hello { position: relative; max-width: 1180px; margin: 0 auto; padding: 30px 24px 0; display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }
.hello-text { flex: 1; min-width: 240px; }
.hello h1 { font-size: 28px; font-weight: 600; margin: 0 0 6px; letter-spacing: -0.015em; color: var(--fs-nav-text); }
.hero .muted { color: var(--fs-nav-muted); font-size: 14px; }
.hero .faint { color: var(--fs-nav-muted); opacity: .8; }
.attn { display: inline-flex; align-items: center; gap: 8px; margin-top: 10px; padding: 4px 12px; border-radius: 999px; font-size: 13px;
  font-weight: 500; background: rgba(255, 255, 255, .1); color: var(--fs-nav-text); }
.continue { display: inline-flex; align-items: center; gap: 8px; padding: 10px 16px; border-radius: var(--fs-radius); max-width: 100%;
  background: rgba(255, 255, 255, .08); border: 1px solid rgba(255, 255, 255, .18); color: var(--fs-nav-text); text-decoration: none; font-size: 14px; }
.continue:hover { background: rgba(255, 255, 255, .14); border-color: var(--fs-primary-2); }
.continue .faint { color: var(--fs-nav-muted); }
.section-label { font-size: 13px; color: var(--fs-muted); margin: 6px 0 10px; font-weight: 500; }
.section-label.on-hero { position: relative; max-width: 1180px; margin: 22px auto 0; padding: 0 24px; color: var(--fs-nav-muted); }
.body { position: relative; max-width: 1180px; margin: -80px auto 0; padding: 0 24px 40px; }
.muted { color: var(--fs-muted); font-size: 14px; }
.faint { color: var(--fs-faint); }
.small { font-size: 12px; }
.flow { display: grid; grid-template-columns: minmax(0, 1fr) minmax(190px, .95fr) minmax(0, 1fr) minmax(190px, .95fr) minmax(0, 1fr); align-items: stretch; }
.flow.loading { opacity: .6; }
.tile { position: relative; z-index: 1; display: flex; flex-direction: column; gap: 8px; padding: 18px 18px 16px; border-radius: var(--fs-radius);
  background: var(--fs-card); border: 1px solid var(--fs-line); color: var(--fs-text); text-decoration: none; min-width: 0;
  transition: border-color .15s, box-shadow .15s; }
.tile:hover, .tile:focus-visible { border-color: var(--fs-primary-2); box-shadow: var(--fs-shadow-pop); outline: none; }
.flow .tile { border-top: 3px solid var(--fs-primary-2); box-shadow: var(--fs-shadow-pop); }
.tname > .el-icon { width: 32px; height: 32px; border-radius: 50%; flex: none;
  background: color-mix(in srgb, var(--fs-primary-2) 16%, var(--fs-card)); }
.tname { display: flex; align-items: center; gap: 8px; font-size: 17px; font-weight: 600; }
.tname .el-icon { color: var(--fs-primary-2); }
.tname a { color: inherit; text-decoration: none; }
.tile[role=link] { cursor: pointer; }
kbd { margin-left: auto; font: 500 11px/1 inherit; color: var(--fs-faint); border: 1px solid var(--fs-line); border-radius: 4px; padding: 3px 6px; }
.tdesc { font-size: 13px; color: var(--fs-muted); line-height: 1.4; }
.metrics { display: flex; gap: 18px; flex-wrap: wrap; margin-top: 2px; }
.metrics b { display: block; font-size: 22px; font-weight: 600; line-height: 1.2; }
.metrics span { font-size: 12px; color: var(--fs-muted); }
.note { font-size: 12px; color: var(--fs-muted); }
.act { margin-top: auto; padding-top: 6px; font-size: 13px; color: var(--fs-primary); font-weight: 500; }
.inner { display: flex; flex-direction: column; gap: 6px; align-items: flex-start; }

.pipe { position: relative; display: flex; align-items: center; justify-content: center; padding: 0 10px; min-width: 0; }
.pipe::before { content: ''; position: absolute; left: 0; right: 0; top: 50%; border-top: 2px dashed var(--fs-primary-2); opacity: .6; z-index: 0; }
.pbody { position: relative; z-index: 1; display: flex; flex-direction: column; align-items: center; gap: 8px; max-width: 100%;
  padding: 10px 12px; border-radius: 16px; background: color-mix(in srgb, var(--fs-primary-2) 9%, var(--fs-bg));
  border: 1px solid color-mix(in srgb, var(--fs-primary-2) 45%, var(--fs-line)); }
.plabel { font-size: 12px; color: var(--fs-primary); font-weight: 500; text-align: center; line-height: 1.3; }
.pchips { display: flex; flex-direction: column; align-items: stretch; gap: 6px; max-width: 100%; min-width: 0; }
.pline { position: absolute; right: -4px; top: 50%; transform: translateY(-50%); color: var(--fs-primary-2); z-index: 2; display: flex; }
.chip { display: inline-flex; align-items: center; gap: 6px; max-width: 100%; padding: 4px 10px; font-size: 13px; line-height: 1.3;
  background: var(--fs-card); border: 1px solid var(--fs-line); color: var(--fs-text); text-decoration: none; cursor: pointer; font-family: inherit;
  border-radius: 12px; overflow-wrap: anywhere; }
.chip:hover { border-color: var(--fs-primary); color: var(--fs-primary); }
.chip.more { color: var(--fs-muted); background: transparent; justify-content: center; }

.ci { font-size: 14px; color: var(--fs-muted); }
.dot { width: 9px; height: 9px; border-radius: 50%; flex: none; display: inline-block; }
.pulse { animation: pulse 1.6s ease-in-out infinite; }
@keyframes pulse { 50% { opacity: .35; } }
@media (prefers-reduced-motion: reduce) { .pulse { animation: none; } }
.free { font-size: 12px; color: var(--fs-faint); background: var(--fs-card-soft); padding: 2px 8px; border-radius: 999px; }
.legend { display: flex; gap: 18px; flex-wrap: wrap; margin: 12px 0 22px; font-size: 12px; color: var(--fs-muted); }
.legend span { display: inline-flex; align-items: center; gap: 6px; }
.legend { margin-top: 14px; }
.results { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 14px; margin-bottom: 22px; }
.res { display: flex; flex-direction: column; gap: 6px; padding: 16px 18px; border-radius: var(--fs-radius); background: var(--fs-card);
  border: 1px solid var(--fs-line); border-left: 4px solid var(--fs-accent); color: var(--fs-text); text-decoration: none; }
.res:hover { box-shadow: var(--fs-shadow-pop); border-color: var(--fs-accent); }
.rname { font-size: 16px; font-weight: 600; }
.runit { font-size: 12px; color: var(--fs-muted); }
.rrow { display: flex; justify-content: space-between; gap: 10px; font-size: 14px; }
.rrow b { color: var(--fs-accent-text); font-variant-numeric: tabular-nums; }
.rmore { font-size: 12px; color: var(--fs-faint); }
.section-label.on-hero b { color: var(--fs-nav-text); font-weight: 600; }
.base { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px; }
.tile.row { flex-direction: row; align-items: center; gap: 14px; background: var(--fs-card); }
.bicon { color: var(--fs-nav-text); background: var(--fs-nav); width: 42px; height: 42px; border-radius: 50%; flex: none; }
.keys { margin-top: 18px; }
@media (max-width: 900px) {
  .flow { grid-template-columns: minmax(0, 1fr); }
  .pipe { padding: 12px 0 18px; }
  .pipe::before { left: 50%; right: auto; top: 0; bottom: 0; border-top: none; border-left: 2px dashed var(--fs-line); }
  .pchips { flex-direction: row; flex-wrap: wrap; justify-content: center; }
  .pline { right: auto; left: 50%; top: auto; bottom: -2px; transform: translateX(-50%) rotate(90deg); }
  .top { flex-wrap: wrap; padding: 10px 16px; }
  .hello { padding: 20px 16px 0; }
  .section-label.on-hero { padding: 0 16px; }
  .body { padding: 0 16px 32px; }
  .uname { display: none; }
  .keys { display: none; }
}
</style>
