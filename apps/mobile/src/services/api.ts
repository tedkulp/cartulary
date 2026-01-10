import axios, {
  AxiosInstance,
  AxiosError,
  InternalAxiosRequestConfig,
  AxiosResponse,
} from 'axios';
import { API_CONFIG, AUTH_CONFIG } from '@config/constants';
import { secureStorage, storage } from '@utils/storage';
import type { ApiError } from '../types/api';

class ApiClient {
  private client: AxiosInstance;
  private refreshTokenPromise: Promise<string> | null = null;

  constructor() {
    this.client = axios.create({
      timeout: API_CONFIG.TIMEOUT,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.setupInterceptors();
  }

  private setupInterceptors() {
    // Request interceptor to add auth token and dynamic base URL
    this.client.interceptors.request.use(
      async (config: InternalAxiosRequestConfig) => {
        // Get dynamic API URL
        const apiUrl = await storage.getItem(AUTH_CONFIG.API_URL_STORAGE_KEY);
        config.baseURL = apiUrl || API_CONFIG.DEFAULT_URL;

        // Add auth token if available
        const token = await secureStorage.getItem(AUTH_CONFIG.TOKEN_STORAGE_KEY);
        if (token && config.headers) {
          config.headers.Authorization = `Bearer ${token}`;
        }

        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor for error handling and token refresh
    this.client.interceptors.response.use(
      (response: AxiosResponse) => response,
      async (error: AxiosError<ApiError>) => {
        const originalRequest = error.config as InternalAxiosRequestConfig & {
          _retry?: boolean;
        };

        // Handle 401 Unauthorized - try to refresh token
        if (error.response?.status === 401 && !originalRequest._retry) {
          originalRequest._retry = true;

          try {
            const newToken = await this.refreshAccessToken();
            if (newToken && originalRequest.headers) {
              originalRequest.headers.Authorization = `Bearer ${newToken}`;
              return this.client(originalRequest);
            }
          } catch (refreshError) {
            // Refresh failed, user needs to log in again
            // This will be handled by the auth store
            return Promise.reject(refreshError);
          }
        }

        // Handle other errors
        return Promise.reject(this.normalizeError(error));
      }
    );
  }

  private async refreshAccessToken(): Promise<string | null> {
    // Prevent multiple simultaneous refresh requests
    if (this.refreshTokenPromise) {
      return this.refreshTokenPromise;
    }

    this.refreshTokenPromise = (async () => {
      try {
        const refreshToken = await secureStorage.getItem(
          AUTH_CONFIG.REFRESH_TOKEN_STORAGE_KEY
        );

        if (!refreshToken) {
          throw new Error('No refresh token available');
        }

        const apiUrl = await storage.getItem(AUTH_CONFIG.API_URL_STORAGE_KEY);
        const baseURL = apiUrl || API_CONFIG.DEFAULT_URL;

        const response = await axios.post(
          `${baseURL}/api/v1/auth/refresh`,
          { refresh_token: refreshToken },
          {
            headers: { 'Content-Type': 'application/json' },
          }
        );

        const { access_token, refresh_token } = response.data;

        // Store new tokens
        await secureStorage.setItem(AUTH_CONFIG.TOKEN_STORAGE_KEY, access_token);
        if (refresh_token) {
          await secureStorage.setItem(
            AUTH_CONFIG.REFRESH_TOKEN_STORAGE_KEY,
            refresh_token
          );
        }

        return access_token;
      } catch (error) {
        // Clear stored tokens on refresh failure
        await secureStorage.removeItem(AUTH_CONFIG.TOKEN_STORAGE_KEY);
        await secureStorage.removeItem(AUTH_CONFIG.REFRESH_TOKEN_STORAGE_KEY);
        throw error;
      } finally {
        this.refreshTokenPromise = null;
      }
    })();

    return this.refreshTokenPromise;
  }

  private normalizeError(error: AxiosError<ApiError>): ApiError {
    if (error.response) {
      return {
        detail: error.response.data?.detail || 'An error occurred',
        status: error.response.status,
      };
    } else if (error.request) {
      return {
        detail: 'Network error - please check your connection',
        status: 0,
      };
    } else {
      return {
        detail: error.message || 'An unexpected error occurred',
        status: -1,
      };
    }
  }

  // Public method to get the axios instance
  getInstance(): AxiosInstance {
    return this.client;
  }

  // Helper methods for common operations
  async get<T>(url: string, config?: any): Promise<T> {
    const response = await this.client.get<T>(url, config);
    return response.data;
  }

  async post<T>(url: string, data?: any, config?: any): Promise<T> {
    const response = await this.client.post<T>(url, data, config);
    return response.data;
  }

  async put<T>(url: string, data?: any, config?: any): Promise<T> {
    const response = await this.client.put<T>(url, data, config);
    return response.data;
  }

  async patch<T>(url: string, data?: any, config?: any): Promise<T> {
    const response = await this.client.patch<T>(url, data, config);
    return response.data;
  }

  async delete<T>(url: string, config?: any): Promise<T> {
    const response = await this.client.delete<T>(url, config);
    return response.data;
  }
}

// Export singleton instance
export const api = new ApiClient();
export default api;
