// Кабинет «Расчёты»: расчёты, запуски, основной запуск, параметры водоёмов.
import { boot, helpRoutes, view } from '../boot'

boot('calc', [
  { path: '/calc/', redirect: (to) => ({ path: '/calc/calculations', query: to.query }) },
  { path: '/calc/calculations', component: view('Calculations') },
  { path: '/calc/calculations/:id', component: view('CalculationView') },
  { path: '/calc/runs', component: view('Runs') },
  { path: '/calc/runs/:id', component: view('RunView') },
  { path: '/calc/profiles', component: view('Profiles') },
  ...helpRoutes('/calc/'),
])
