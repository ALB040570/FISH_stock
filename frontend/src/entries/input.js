// Кабинет «Ввод данных»: наборы данных — загрузка Excel, правка, версии, сравнение.
import { boot, helpRoutes, view } from '../boot'

boot('input', [
  { path: '/input/', redirect: (to) => ({ path: '/input/datasets', query: to.query }) },
  { path: '/input/datasets', component: view('Datasets') },
  { path: '/input/datasets/:id', component: view('DatasetView') },
  ...helpRoutes('/input/'),
])
