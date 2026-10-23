// Кабинет «Мониторинг»: карта, мониторинг водоёма, дашборды.
import { boot, helpRoutes, view } from '../boot'

boot('monitoring', [
  { path: '/monitoring/', component: view('MapHome') },
  // вид/раздел/слайд в адресе — без перезагрузки страницы
  { path: '/monitoring/waterbody/:wb?', component: view('Monitoring'), meta: { queryState: true } },
  { path: '/monitoring/dashboards', component: view('Dashboards') },
  { path: '/monitoring/dashboards/:id', component: view('DashboardView') },
  ...helpRoutes('/monitoring/'),
])
