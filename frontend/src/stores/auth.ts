import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authService } from '@/services/authService'
import type { LoginCredentials, RegisterData, User } from '@/types/auth'

export const useAuthStore = defineStore('auth', () => {
  // State
  const user = ref<User | null>(null)
  const accessToken = ref<string | null>(localStorage.getItem('access_token'))
  const refreshTokenValue = ref<string | null>(localStorage.getItem('refresh_token'))
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Getters
  const isAuthenticated = computed(() => !!accessToken.value && !!user.value)
  const isSuperuser = computed(() => user.value?.is_superuser || false)

  // Actions
  async function register(data: RegisterData): Promise<boolean> {
    loading.value = true
    error.value = null

    try {
      const newUser = await authService.register(data)

      // Auto-login after registration
      await login({ email: data.email, password: data.password })

      return true
    } catch (err: any) {
      error.value = err.response?.data?.detail || 'Registration failed'
      return false
    } finally {
      loading.value = false
    }
  }

  async function login(credentials: LoginCredentials): Promise<boolean> {
    loading.value = true
    error.value = null

    try {
      const tokens = await authService.login(credentials)

      // Store tokens
      accessToken.value = tokens.access_token
      refreshTokenValue.value = tokens.refresh_token
      localStorage.setItem('access_token', tokens.access_token)
      localStorage.setItem('refresh_token', tokens.refresh_token)

      // Fetch user data
      await fetchCurrentUser()

      return true
    } catch (err: any) {
      error.value = err.response?.data?.detail || 'Login failed'
      return false
    } finally {
      loading.value = false
    }
  }

  async function refreshToken(): Promise<boolean> {
    if (!refreshTokenValue.value) {
      return false
    }

    try {
      const tokens = await authService.refreshToken(refreshTokenValue.value)

      // Update tokens
      accessToken.value = tokens.access_token
      refreshTokenValue.value = tokens.refresh_token
      localStorage.setItem('access_token', tokens.access_token)
      localStorage.setItem('refresh_token', tokens.refresh_token)

      return true
    } catch (err) {
      // Refresh failed, clear everything
      logout()
      return false
    }
  }

  async function fetchCurrentUser(): Promise<void> {
    if (!accessToken.value) {
      return
    }

    try {
      user.value = await authService.getCurrentUser()
    } catch (err) {
      // If fetching user fails, logout
      logout()
    }
  }

  function logout(): void {
    user.value = null
    accessToken.value = null
    refreshTokenValue.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    error.value = null
  }

  async function initialize(): Promise<void> {
    if (accessToken.value) {
      await fetchCurrentUser()
    }
  }

  function clearError(): void {
    error.value = null
  }

  return {
    // State
    user,
    accessToken,
    loading,
    error,

    // Getters
    isAuthenticated,
    isSuperuser,

    // Actions
    register,
    login,
    logout,
    refreshToken,
    fetchCurrentUser,
    initialize,
    clearError,
  }
})
