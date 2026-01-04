import { create } from 'zustand';
import { storage } from '@utils/storage';
import { API_CONFIG, AUTH_CONFIG } from '@config/constants';

interface SettingsState {
  apiUrl: string;
  theme: 'light' | 'dark' | 'auto';
  isLoading: boolean;

  // Actions
  setApiUrl: (url: string) => Promise<void>;
  loadSettings: () => Promise<void>;
  setTheme: (theme: 'light' | 'dark' | 'auto') => Promise<void>;
  resetToDefaults: () => Promise<void>;
}

export const useSettingsStore = create<SettingsState>((set) => ({
  apiUrl: API_CONFIG.DEFAULT_URL,
  theme: 'auto',
  isLoading: false,

  setApiUrl: async (url: string) => {
    try {
      // Remove trailing slash if present
      const cleanUrl = url.replace(/\/$/, '');

      await storage.setItem(AUTH_CONFIG.API_URL_STORAGE_KEY, cleanUrl);
      set({ apiUrl: cleanUrl });
    } catch (error) {
      console.error('Failed to set API URL:', error);
      throw error;
    }
  },

  loadSettings: async () => {
    try {
      set({ isLoading: true });

      // Load API URL
      const apiUrl = await storage.getItem(AUTH_CONFIG.API_URL_STORAGE_KEY);

      // Load theme
      const theme = await storage.getItem('app_theme');

      set({
        apiUrl: apiUrl || API_CONFIG.DEFAULT_URL,
        theme: (theme as 'light' | 'dark' | 'auto') || 'auto',
        isLoading: false,
      });
    } catch (error) {
      console.error('Failed to load settings:', error);
      set({ isLoading: false });
    }
  },

  setTheme: async (theme: 'light' | 'dark' | 'auto') => {
    try {
      await storage.setItem('app_theme', theme);
      set({ theme });
    } catch (error) {
      console.error('Failed to set theme:', error);
      throw error;
    }
  },

  resetToDefaults: async () => {
    try {
      await storage.setItem(AUTH_CONFIG.API_URL_STORAGE_KEY, API_CONFIG.DEFAULT_URL);
      await storage.setItem('app_theme', 'auto');

      set({
        apiUrl: API_CONFIG.DEFAULT_URL,
        theme: 'auto',
      });
    } catch (error) {
      console.error('Failed to reset settings:', error);
      throw error;
    }
  },
}));
