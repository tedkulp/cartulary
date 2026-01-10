import { create } from 'zustand'
import type { AuthService } from '../services/auth.service'
import type { LoginCredentials, RegisterData, User } from '../types/auth'

interface AuthState {
  // State
  user: User | null
  accessToken: string | null
  refreshTokenValue: string | null
  loading: boolean
  error: string | null
  initializing: boolean

  // Getters (computed properties)
  isAuthenticated: () => boolean
  isSuperuser: () => boolean

  // Internal helper
  _authService: AuthService | null
  _storage: Storage | null

  // Actions
  setAuthService: (service: AuthService, storage?: Storage) => void
  register: (data: RegisterData) => Promise<boolean>
  login: (credentials: LoginCredentials) => Promise<boolean>
  logout: () => void
  refreshToken: () => Promise<boolean>
  fetchCurrentUser: () => Promise<void>
  initialize: () => Promise<void>
  clearError: () => void
}

/**
 * Auth store using Zustand
 * Platform-agnostic: works with both web (localStorage) and mobile (AsyncStorage)
 *
 * Usage:
 * - Web: useAuthStore.getState().setAuthService(authService, localStorage)
 * - Mobile: useAuthStore.getState().setAuthService(authService, AsyncStorage)
 */
export const useAuthStore = create<AuthState>((set, get) => ({
  // Initial state
  user: null,
  accessToken: null,
  refreshTokenValue: null,
  loading: false,
  error: null,
  initializing: true,
  _authService: null,
  _storage: null,

  // Getters
  isAuthenticated: () => {
    const state = get()
    return !!state.accessToken && !!state.user
  },

  isSuperuser: () => {
    const state = get()
    return state.user?.is_superuser || false
  },

  // Initialize with auth service and storage
  setAuthService: (service: AuthService, storage?: Storage) => {
    set({ _authService: service, _storage: storage || null })

    // Load tokens from storage if available
    if (storage) {
      const accessToken = storage.getItem?.('access_token') || null
      const refreshTokenValue = storage.getItem?.('refresh_token') || null
      set({ accessToken, refreshTokenValue })
    }
  },

  // Actions
  register: async (data: RegisterData): Promise<boolean> => {
    const { _authService, login } = get()
    if (!_authService) {
      console.error('AuthService not initialized')
      return false
    }

    set({ loading: true, error: null })

    try {
      await _authService.register(data)

      // Auto-login after registration
      await login({ email: data.email, password: data.password })

      return true
    } catch (err: any) {
      set({ error: err.response?.data?.detail || 'Registration failed', loading: false })
      return false
    } finally {
      set({ loading: false })
    }
  },

  login: async (credentials: LoginCredentials): Promise<boolean> => {
    const { _authService, _storage, fetchCurrentUser } = get()
    if (!_authService) {
      console.error('AuthService not initialized')
      return false
    }

    set({ loading: true, error: null })

    try {
      const tokens = await _authService.login(credentials)

      // Store tokens
      set({
        accessToken: tokens.access_token,
        refreshTokenValue: tokens.refresh_token,
      })

      if (_storage) {
        _storage.setItem?.('access_token', tokens.access_token)
        _storage.setItem?.('refresh_token', tokens.refresh_token)
      }

      // Fetch user data
      await fetchCurrentUser()

      return true
    } catch (err: any) {
      set({ error: err.response?.data?.detail || 'Login failed', loading: false })
      return false
    } finally {
      set({ loading: false })
    }
  },

  refreshToken: async (): Promise<boolean> => {
    const { _authService, _storage, refreshTokenValue, logout } = get()
    if (!_authService || !refreshTokenValue) {
      return false
    }

    try {
      const tokens = await _authService.refreshToken(refreshTokenValue)

      // Update tokens
      set({
        accessToken: tokens.access_token,
        refreshTokenValue: tokens.refresh_token,
      })

      if (_storage) {
        _storage.setItem?.('access_token', tokens.access_token)
        _storage.setItem?.('refresh_token', tokens.refresh_token)
      }

      return true
    } catch (err) {
      // Refresh failed, clear everything
      logout()
      return false
    }
  },

  fetchCurrentUser: async (): Promise<void> => {
    const { _authService, accessToken, logout } = get()
    if (!_authService || !accessToken) {
      return
    }

    try {
      const user = await _authService.getCurrentUser()
      set({ user })
    } catch (err: any) {
      // Only logout on authentication errors (401, 403)
      // Don't logout on network errors or other temporary issues
      const status = err?.response?.status
      if (status === 401 || status === 403) {
        console.log('Authentication failed, logging out')
        logout()
      } else {
        console.error('Failed to fetch current user, but keeping session:', err)
      }
    }
  },

  logout: () => {
    const { _storage } = get()

    set({
      user: null,
      accessToken: null,
      refreshTokenValue: null,
      error: null,
    })

    if (_storage) {
      _storage.removeItem?.('access_token')
      _storage.removeItem?.('refresh_token')
    }
  },

  initialize: async (): Promise<void> => {
    set({ initializing: true })
    const { accessToken, fetchCurrentUser } = get()
    if (accessToken) {
      await fetchCurrentUser()
    }
    set({ initializing: false })
  },

  clearError: () => {
    set({ error: null })
  },
}))
