// Проверка полей профиля в браузере — те же правила, что на сервере (services/users, ProfileFields).
export const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/

/** { name, email } — тексты ошибок ('' — без ошибки). t — функция перевода. */
export function checkProfile(f, t = (k) => k) {
  const name = String(f.name || '').trim()
  const email = String(f.email || '').trim()
  return {
    name: name ? '' : t('profile.err_name'),
    email: !email || EMAIL_RE.test(email) ? '' : t('profile.err_email'),
  }
}
