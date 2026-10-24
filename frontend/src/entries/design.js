// Кабинет «Конструктор»: структура данных, алгоритмы, порядок расчёта, дашборды, правила замечаний.
import { boot, helpRoutes, view } from '../boot'

boot('design', [
  { path: '/design/', redirect: '/design/dictionaries' },
  { path: '/design/dictionaries', component: view('Dictionaries') },
  { path: '/design/dictionaries/entities/:code', component: view('EntityView') },
  { path: '/design/dictionaries/types/:code', component: view('DatasetTypeView') },
  { path: '/design/algorithms', component: view('Algorithms'), meta: { perm: 'algo.develop' } },
  { path: '/design/algorithms/drafts/:id', component: view('DraftEditor'), meta: { perm: 'algo.develop' } },
  // режим конструктора: тот же экран, редактирование порядка расчёта / дашборда
  { path: '/design/calculations', component: view('Calculations'), meta: { design: true, perm: 'run.execute' } },
  { path: '/design/calculations/:id', component: view('CalculationView'), meta: { design: true, perm: 'run.execute' } },
  { path: '/design/dashboards', component: view('Dashboards'), meta: { design: true, perm: 'dashboard.edit' } },
  { path: '/design/dashboards/:id', component: view('DashboardView'), meta: { design: true, perm: 'dashboard.edit' } },
  { path: '/design/signal-rules', component: view('SignalRules'), meta: { perm: 'dashboard.edit' } },
  // каталог для тех, кто не входит в «Администрирование» (ихтиолог, «Презентация»): только просмотр
  { path: '/design/catalog', component: view('Catalog') },
  ...helpRoutes('/design/'),
])
