// Кабинет «Администрирование»: пользователи, журнал действий, каталог алгоритмов.
import { boot, helpRoutes, view } from '../boot'
import { useAuth } from '../store/auth'

boot('admin', [
  { path: '/admin/', redirect: () => (useAuth().can('users.manage') ? '/admin/users' : '/admin/catalog') },
  { path: '/admin/users', component: view('Users'), meta: { perm: 'users.manage' } },
  { path: '/admin/audit', component: view('Audit'), meta: { perm: 'audit.view' } },
  { path: '/admin/catalog', component: view('Catalog') },
  ...helpRoutes('/admin/'),
])
