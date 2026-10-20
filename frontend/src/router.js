import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from './store/auth'

const L = (n) => () => import(`./views/${n}.vue`)

const routes = [
  { path: '/login', component: L('Login'), meta: { public: true } },
  { path: '/', component: L('MapHome') },
  { path: '/monitoring/:wb?', component: L('Monitoring') },
  { path: '/data', component: L('Datasets') },
  { path: '/data/:id', component: L('DatasetView') },
  { path: '/dictionaries', component: L('Dictionaries') },
  { path: '/dictionaries/entities/:code', component: L('EntityView') },
  { path: '/dictionaries/types/:code', component: L('DatasetTypeView') },
  { path: '/algorithms', component: L('Algorithms'), meta: { perm: 'algo.develop' } },
  { path: '/algorithms/drafts/:id', component: L('DraftEditor'), meta: { perm: 'algo.develop' } },
  { path: '/catalog', component: L('Catalog') },
  { path: '/profiles', component: L('Profiles') },
  { path: '/calculations', component: L('Calculations') },
  { path: '/calculations/:id', component: L('CalculationView') },
  // режим конструктора: тот же экран, редактирование порядка расчёта / дашборда
  { path: '/design/calculations', component: L('Calculations'), meta: { design: true, perm: 'run.execute' } },
  { path: '/design/calculations/:id', component: L('CalculationView'), meta: { design: true, perm: 'run.execute' } },
  { path: '/runs', component: L('Runs') },
  { path: '/runs/:id', component: L('RunView') },
  { path: '/dashboards', component: L('Dashboards') },
  { path: '/dashboards/:id', component: L('DashboardView') },
  { path: '/design/dashboards', component: L('Dashboards'), meta: { design: true, perm: 'dashboard.edit' } },
  { path: '/design/dashboards/:id', component: L('DashboardView'), meta: { design: true, perm: 'dashboard.edit' } },
  { path: '/users', component: L('Users'), meta: { perm: 'users.manage' } },
  { path: '/audit', component: L('Audit'), meta: { perm: 'audit.view' } },
  { path: '/help/:id?', component: L('Help') },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to) => {
  const auth = useAuth()
  if (!to.meta.public && !auth.loggedIn) return { path: '/login', query: { next: to.fullPath } }
  if (to.meta.perm && !auth.can(to.meta.perm)) return '/'
})

export default router
