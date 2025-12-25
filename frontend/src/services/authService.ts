import api from './api'
import type { LoginCredentials, RegisterData, TokenResponse, User } from '@/types/auth'

export interface OIDCConfig {
  enabled: boolean
  authorization_url?: string
  client_id?: string
}

export const authService = {
  async register(data: RegisterData): Promise<User> {
    const response = await api.post<User>('/api/v1/auth/register', data)
    return response.data
  },

  async login(credentials: LoginCredentials): Promise<TokenResponse> {
    const response = await api.post<TokenResponse>('/api/v1/auth/login', credentials)
    return response.data
  },

  async refreshToken(refreshToken: string): Promise<TokenResponse> {
    const response = await api.post<TokenResponse>('/api/v1/auth/refresh', {
      refresh_token: refreshToken,
    })
    return response.data
  },

  async getCurrentUser(): Promise<User> {
    const response = await api.get<User>('/api/v1/auth/me')
    return response.data
  },

  // OIDC Methods
  async getOIDCConfig(): Promise<OIDCConfig> {
    const response = await api.get<OIDCConfig>('/api/v1/auth/oidc/config')
    return response.data
  },

  async initiateOIDCLogin(): Promise<void> {
    // Redirect to backend OIDC login endpoint
    window.location.href = `${api.defaults.baseURL}/api/v1/auth/oidc/login`
  },

  async handleOIDCCallback(code: string, state: string): Promise<TokenResponse> {
    const response = await api.get<TokenResponse>('/api/v1/auth/oidc/callback', {
      params: { code, state }
    })
    return response.data
  },
}
