import Constants from 'expo-constants';
import { Platform } from 'react-native';

// Default API URL based on platform
const getDefaultApiUrl = (): string => {
  if (__DEV__) {
    // Development mode defaults - connect to frontend which proxies to backend
    if (Platform.OS === 'ios') {
      return 'http://localhost:8080';
    } else if (Platform.OS === 'android') {
      return 'http://10.0.2.2:8080';
    }
  }
  // Production - should be configured by user
  return 'https://api.cartulary.example.com';
};

export const API_CONFIG = {
  DEFAULT_URL: getDefaultApiUrl(),
  TIMEOUT: 30000,
  MAX_RETRIES: 3,
} as const;

export const AUTH_CONFIG = {
  TOKEN_STORAGE_KEY: 'auth_token',
  REFRESH_TOKEN_STORAGE_KEY: 'refresh_token',
  USER_STORAGE_KEY: 'user_data',
  API_URL_STORAGE_KEY: 'api_url',
  OIDC_STATE_KEY: 'oidc_state',
  OIDC_VERIFIER_KEY: 'oidc_code_verifier',
} as const;

export const DOCUMENT_CONFIG = {
  PAGE_SIZE: 20,
  MAX_FILE_SIZE: 50 * 1024 * 1024, // 50MB
  SUPPORTED_MIME_TYPES: [
    'application/pdf',
    'image/jpeg',
    'image/jpg',
    'image/png',
    'image/tiff',
    'image/webp',
  ],
  SUPPORTED_EXTENSIONS: ['.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.tif', '.webp'],
} as const;

export const CAMERA_CONFIG = {
  IMAGE_QUALITY: 0.9,
  COMPRESSION_QUALITY: 0.8,
  MAX_IMAGE_DIMENSION: 3000,
} as const;

export const APP_INFO = {
  NAME: 'Cartulary',
  VERSION: Constants.expoConfig?.version || '1.0.0',
  BUNDLE_ID: Platform.select({
    ios: 'com.cartulary.app',
    android: 'com.cartulary.app',
  }),
} as const;

export const COLORS = {
  primary: '#2196F3',
  primaryDark: '#1976D2',
  primaryLight: '#BBDEFB',
  accent: '#FF5722',
  background: '#FFFFFF',
  surface: '#F5F5F5',
  error: '#F44336',
  text: '#212121',
  textSecondary: '#757575',
  border: '#E0E0E0',
  success: '#4CAF50',
  warning: '#FF9800',
} as const;
