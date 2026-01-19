import type { AxiosInstance } from 'axios'
import type { LoginCredentials, RegisterData, TokenResponse, User } from '../types/auth'

export interface OIDCConfig {
  enabled: boolean
  authorization_url?: string
  client_id?: string
}

/**
 * Authentication service with dependency injection
 */
export class AuthService {
  constructor(private api: AxiosInstance) { }

  async register(data: RegisterData): Promise<User> {
    const response = await this.api.post<User>('/api/v1/auth/register', data)
    return response.data
  }

  async login(credentials: LoginCredentials): Promise<TokenResponse> {
    const response = await this.api.post<TokenResponse>('/api/v1/auth/login', credentials)
    return response.data
  }

  async refreshToken(refreshToken: string): Promise<TokenResponse> {
    const response = await this.api.post<TokenResponse>('/api/v1/auth/refresh', {
      refresh_token: refreshToken,
    })
    return response.data
  }

  async getCurrentUser(): Promise<User> {
    const response = await this.api.get<User>('/api/v1/auth/me')
    return response.data
  }

  // OIDC Methods
  async getOIDCConfig(): Promise<OIDCConfig> {
    const response = await this.api.get<OIDCConfig>('/api/v1/auth/oidc/config')
    return response.data
  }

  /**
   * Initiates OIDC login by redirecting to backend
   * Platform-specific: uses window.location for web
   */
  async initiateOIDCLogin(): Promise<void> {
    if (typeof window !== 'undefined') {
      // Web platform - use relative URL to leverage proxy
      window.location.href = '/api/v1/auth/oidc/login'
    } else {
      // Mobile platform - should be handled differently
      throw new Error('initiateOIDCLogin not implemented for this platform. Use platform-specific implementation.')
    }
  }

  async handleOIDCCallback(code: string, state: string): Promise<TokenResponse> {
    console.log('handleOIDCCallback')

    const response = await this.api.get<TokenResponse>('/api/v1/auth/oidc/callback', {
      params: { code, state }
    })
    return response.data
  }
}
