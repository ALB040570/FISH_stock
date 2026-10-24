// Кабинет «Конструктор»: структура данных, алгоритмы (разработка), дашборды, правила замечаний. Порядок расчёта
// (цепочки шагов) и каталог для просмотра убраны — расчёты и каталог в «Расчётах запасов рыб» (решение № 70).
import { boot, helpRoutes, view } from '../boot'

boot('design', [
  { path: '/design/', redirect: '/design/dictionaries' },
  { path: '/design/dictionaries', component: view('Dictionaries') },
  { path: '/design/dictionaries/entities/:code', component: view('EntityView') },
  { path: '/design/dictionaries/types/:code', component: view('DatasetTypeView') },
  { path: '/design/algorithms', component: view('Algorithms'), meta: { perm: 'algo.develop' } },
  { path: '/design/algorithms/drafts/:id', component: view('DraftEditor'), meta: { perm: 'algo.develop' } },
  // режим конструктора дашборда
  { path: '/design/dashboards', component: view('Dashboards'), meta: { design: true, perm: 'dashboard.edit' } },
  { path: '/design/dashboards/:id', component: view('DashboardView'), meta: { design: true, perm: 'dashboard.edit' } },
  { path: '/design/signal-rules', component: view('SignalRules'), meta: { perm: 'dashboard.edit' } },
  ...helpRoutes('/design/'),
])
