// Страница входа и выбора кабинета (/, /login); старые адреса единого интерфейса перенаправляются в кабинеты.
import { boot, view } from '../boot'

boot(null, [
  { path: '/login', component: view('Login'), meta: { public: true } },
  { path: '/', component: view('Cabinets'), meta: { bare: true } },
])
