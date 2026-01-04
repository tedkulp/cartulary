import { create } from 'zustand';
import { authService } from '@services/auth.service';
import type {
  User,
  LoginRequest,
  RegisterRequest,
  OIDCConfig,
} from '../types/api';

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  oidcConfig: OIDCConfig | null;

  // Actions
  login: (credentials: LoginRequest) => Promise<void>;
  register: (data: RegisterRequest) => Promise<void>;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
  getOIDCConfig: () => Promise<void>;
  loginWithOIDC: () => Promise<void>;
  completeOIDC: (code: string, state: string) => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  isAuthenticated: false,
  isLoading: false,
  error: null,
  oidcConfig: null,

  login: async (credentials: LoginRequest) => {
    try {
      set({ isLoading: true, error: null });

      const { user } = await authService.login(credentials);

      set({
        user,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });
    } catch (error: any) {
      set({
        isLoading: false,
        error: error.detail || 'Login failed',
      });
      throw error;
    }
  },

  register: async (data: RegisterRequest) => {
    try {
      set({ isLoading: true, error: null });

      const { user } = await authService.register(data);

      set({
        user,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });
    } catch (error: any) {
      set({
        isLoading: false,
        error: error.detail || 'Registration failed',
      });
      throw error;
    }
  },

  logout: async () => {
    try {
      set({ isLoading: true });

      await authService.logout();

      set({
        user: null,
        isAuthenticated: false,
        isLoading: false,
        error: null,
        oidcConfig: null,
      });
    } catch (error: any) {
      set({
        isLoading: false,
        error: error.detail || 'Logout failed',
      });
    }
  },

  checkAuth: async () => {
    try {
      set({ isLoading: true });

      const isAuth = await authService.isAuthenticated();

      if (isAuth) {
        // Try to get stored user first
        let user = await authService.getStoredUser();

        // If no stored user, fetch from API
        if (!user) {
          user = await authService.getCurrentUser();
        }

        set({
          user,
          isAuthenticated: true,
          isLoading: false,
        });
      } else {
        set({
          user: null,
          isAuthenticated: false,
          isLoading: false,
        });
      }
    } catch (error: any) {
      // If check fails, assume not authenticated
      set({
        user: null,
        isAuthenticated: false,
        isLoading: false,
      });
    }
  },

  getOIDCConfig: async () => {
    try {
      const config = await authService.getOIDCConfig();
      set({ oidcConfig: config });
    } catch (error: any) {
      // Silently fail - server may not be configured yet
      // Only log if it's not a network error
      if (error.status !== 0) {
        console.error('Failed to get OIDC config:', error);
      }
      set({ oidcConfig: { enabled: false } });
    }
  },

  loginWithOIDC: async () => {
    try {
      set({ isLoading: true, error: null });

      const result = await authService.initiateOIDC();

      console.log('OIDC result:', result);

      if (result.type === 'success') {
        console.log('OIDC success, callback URL:', result.url);

        // Parse the callback URL to get code and state
        const url = new URL(result.url);
        const code = url.searchParams.get('code');
        const state = url.searchParams.get('state');
        const error = url.searchParams.get('error');

        console.log('Parsed from URL - code:', code, 'state:', state, 'error:', error);

        if (error) {
          throw new Error(error);
        }

        if (code && state) {
          await get().completeOIDC(code, state);
        } else {
          throw new Error('Missing code or state in OIDC callback');
        }
      } else {
        console.log('OIDC result type:', result.type);
        set({ isLoading: false });
      }
    } catch (error: any) {
      console.error('OIDC login error:', error);
      set({
        isLoading: false,
        error: error.message || 'OIDC login failed',
      });
      throw error;
    }
  },

  completeOIDC: async (code: string, state: string) => {
    try {
      set({ isLoading: true, error: null });

      console.log('Completing OIDC with code:', code, 'state:', state);

      const { user } = await authService.completeOIDC(code, state);

      console.log('OIDC complete, user:', user);

      set({
        user,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });
    } catch (error: any) {
      console.error('OIDC complete error:', error);
      set({
        isLoading: false,
        error: error.message || 'OIDC authentication failed',
      });
      throw error;
    }
  },

  clearError: () => set({ error: null }),
}));
