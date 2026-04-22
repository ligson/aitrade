import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { fetchCurrentUser, login as loginApi, logout as logoutApi } from '@/api/auth'
import type { CurrentUser } from '@/types/auth'
import { clearToken, getToken, setToken } from '@/utils/token'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(getToken())
  const currentUser = ref<CurrentUser | null>(null)
  const isLoggedIn = computed(() => Boolean(token.value))
  const isAdmin = computed(() => Boolean(currentUser.value?.isAdmin))

  async function login(payload: { username: string; password: string; captchaKey: string; captchaCode: string }) {
    const result = await loginApi(payload)
    token.value = result.token
    currentUser.value = result.user
    setToken(result.token)
  }

  async function restore() {
    if (!token.value) {
      return
    }
    try {
      currentUser.value = await fetchCurrentUser()
    } catch {
      logout(true)
    }
  }

  async function logout(silent = false) {
    if (!silent && token.value) {
      try {
        await logoutApi()
      } catch {
        // ignore
      }
    }
    token.value = ''
    currentUser.value = null
    clearToken()
  }

  return {
    token,
    currentUser,
    isLoggedIn,
    isAdmin,
    login,
    restore,
    logout,
  }
})
