// «Продолжить» на стартовой странице: последний открытый экран пользователя (только в этом браузере).
const key = (uid) => `fishstock.last.${uid || 'anon'}`

export function saveLast(uid, place) {
  try { localStorage.setItem(key(uid), JSON.stringify({ ...place, at: new Date().toISOString() })) } catch (e) { /* приватный режим */ }
}

export function loadLast(uid) {
  try {
    const v = JSON.parse(localStorage.getItem(key(uid)))
    return v && typeof v.path === 'string' && v.path.startsWith('/') && !v.path.startsWith('//') ? v : null
  } catch (e) { return null }
}
