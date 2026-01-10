import { useAuthStore } from '../stores/authStore'

/**
 * React hook for authentication
 * Wrapper around the Zustand auth store for convenient access
 */
export function useAuth() {
  const {
    user,
    accessToken,
    loading,
    error,
    isAuthenticated,
    isSuperuser,
    register,
    login,
    logout,
    refreshToken,
    fetchCurrentUser,
    initialize,
    clearError
  } = useAuthStore()

  return {
    // State
    user,
    accessToken,
    loading,
    error,

    // Getters (computed)
    isAuthenticated: isAuthenticated(),
    isSuperuser: isSuperuser(),

    // Actions
    register,
    login,
    logout,
    refreshToken,
    fetchCurrentUser,
    initialize,
    clearError
  }
}
