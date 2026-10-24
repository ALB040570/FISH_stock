// Кабинет «Расчёты запасов рыб» (решение № 66): расчёты (алгоритм + входы + период + параметры, один результат,
// основной / альтернативный), каталог алгоритмов a–k, параметры алгоритмов (наборы с версиями).
import { boot, helpRoutes, view } from '../boot'

boot('calc', [
  { path: '/calc/', redirect: (to) => ({ path: '/calc/calculations', query: to.query }) },
  { path: '/calc/calculations', component: view('Calcs') },
  { path: '/calc/calculations/:id', component: view('CalcView') },
  { path: '/calc/catalog', component: view('Catalog') },
  { path: '/calc/params', component: view('ParamSets'), meta: { perm: 'profile.view' } },
  { path: '/calc/params/:id', component: view('ParamSets'), meta: { perm: 'profile.view' } },
  ...helpRoutes('/calc/'),
])
