// Кабинет «Мониторинг»: карта, мониторинг водоёма, дашборды.
import { boot, helpRoutes, view } from '../boot'

boot('monitoring', [
  { path: '/monitoring/', component: view('MapHome') },
  // вид/раздел/слайд в адресе — без перезагрузки страницы
  { path: '/monitoring/waterbody/:wb?', component: view('Monitoring'), meta: { queryState: true } },
  // сравнение расчётов (№ 77): ряды из результатов модели — только с правом на результаты
  { path: '/monitoring/compare', component: view('CompareCalcs'), meta: { perm: 'results.view', queryState: true } },
  { path: '/monitoring/dashboards', component: view('Dashboards') },
  { path: '/monitoring/dashboards/:id', component: view('DashboardView') },
  ...helpRoutes('/monitoring/'),
])
