// Кабинет «Администрирование»: пользователи и журнал действий (каталог алгоритмов — в «Расчётах запасов рыб», № 66).
import { boot, helpRoutes, view } from '../boot'

boot('admin', [
  { path: '/admin/', redirect: '/admin/users' },
  { path: '/admin/users', component: view('Users'), meta: { perm: 'users.manage' } },
  { path: '/admin/audit', component: view('Audit'), meta: { perm: 'audit.view' } },
  ...helpRoutes('/admin/'),
])
