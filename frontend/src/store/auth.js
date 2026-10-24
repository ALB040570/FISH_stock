import { defineStore } from 'pinia'

const KEY = 'fishstock.session'
function load() { try { return JSON.parse(localStorage.getItem(KEY)) || {} } catch (e) { return {} } }

const PERMS = {
  'users.manage': ['admin'], 'audit.view': ['admin'],
  'dict.edit': ['admin', 'ichthyologist', 'mathematician'], 'data.edit': ['admin', 'ichthyologist', 'mathematician', 'operator'],
  'profile.edit': ['admin', 'ichthyologist', 'mathematician'], 'algo.develop': ['admin', 'mathematician'],
  'catalog.manage': ['admin', 'mathematician'], 'run.execute': ['admin', 'ichthyologist', 'mathematician'],
  'dashboard.edit': ['admin', 'ichthyologist', 'mathematician'], 'dashboard.template': ['admin', 'mathematician'],
  // результаты модели и закрытое от «Презентации» (fishcommon/auth.py, № 62)
  'results.view': ['admin', 'ichthyologist', 'mathematician'],
  'results.summary': ['admin', 'ichthyologist', 'mathematician', 'presenter'],
  'profile.view': ['admin', 'ichthyologist', 'mathematician', 'operator', 'viewer'],
  'catalog.files': ['admin', 'ichthyologist', 'mathematician', 'operator', 'viewer'],
  'help.full': ['admin', 'ichthyologist', 'mathematician', 'operator', 'viewer'],
}

export const useAuth = defineStore('auth', {
  state: () => ({ ...{ accessToken: null, refreshToken: null, user: null }, ...load(), expired: false }),
  getters: {
    loggedIn: (s) => !!s.accessToken && !!s.user,
    role: (s) => s.user?.role,
  },
  actions: {
    setSession(j) {
      this.accessToken = j.access_token; this.refreshToken = j.refresh_token; this.user = j.user; this.expired = false
      this.persist()
    },
    persist() {
      try { localStorage.setItem(KEY, JSON.stringify({ accessToken: this.accessToken, refreshToken: this.refreshToken, user: this.user })) } catch (e) { /* приватный режим */ }
    },
    /** Профиль с сервера (имя, фото…) без смены токенов — например, после правки администратором. */
    setUser(u) {
      if (!u || !this.user || u.id !== this.user.id) return
      this.user = { ...this.user, ...u }
      this.persist()
    },
    logout(expired = false) {
      this.accessToken = null; this.refreshToken = null; this.user = null; this.expired = expired
      try { localStorage.removeItem(KEY) } catch (e) { /* */ }
    },
    can(perm) { return !!this.user && (PERMS[perm] ? PERMS[perm].includes(this.user.role) : true) },
  },
})
