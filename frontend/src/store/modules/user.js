import { defineStore } from 'pinia'
import { authApi } from '@/api/auth'
import { clearToken, getRefresh, persistAuth } from '@/utils/auth'

export const useUserStore = defineStore('user', {
  state: () => ({
    user: null,
    codes: [],
    roles: [],
    is_superuser: false,
    menus: [],
    loaded: false,
  }),
  getters: {
    name: (s) => s.user?.display_name || s.user?.username || '匿名',
    avatarText: (s) => (s.user?.display_name || s.user?.username || '?').slice(0, 1),
    hasPerm: (s) => (code) => {
      if (!code) return true
      if (s.codes.includes('*') || s.is_superuser) return true
      if (s.codes.includes(code)) return true
      const module = code.split(':')[0]
      return s.codes.includes(`${module}:*`)
    },
  },
  actions: {
    async login(payload) {
      const res = await authApi.login(payload)
      persistAuth(res)
      this.user = res.user
      await this.loadAccess()
      return res
    },
    async loadAccess() {
      const [menus, perms] = await Promise.all([authApi.menus(), authApi.myPermissions()])
      this.menus = menus || []
      this.codes = perms?.codes || []
      this.roles = perms?.roles || []
      this.is_superuser = !!perms?.is_superuser
      this.loaded = true
    },
    async fetchProfile() {
      this.user = await authApi.profile()
      return this.user
    },
    async logout() {
      try {
        await authApi.logout(getRefresh())
      } catch (e) {
        /* 忽略 */
      }
      this.reset()
    },
    reset() {
      clearToken()
      this.user = null
      this.codes = []
      this.roles = []
      this.is_superuser = false
      this.menus = []
      this.loaded = false
    },
  },
})
