import * as AuthSession from 'expo-auth-session';
import * as WebBrowser from 'expo-web-browser';
import * as Crypto from 'expo-crypto';
import { api } from './api';
import { secureStorage, storage } from '@utils/storage';
import { AUTH_CONFIG } from '@config/constants';
import type {
  User,
  LoginRequest,
  RegisterRequest,
  TokenResponse,
  OIDCConfig,
} from '../types/api';

// Required for OIDC redirect handling
WebBrowser.maybeCompleteAuthSession();

class AuthService {
  /**
   * Login with email and password
   */
  async login(credentials: LoginRequest): Promise<{
    user: User;
    tokens: TokenResponse;
  }> {
    const formData = new FormData();
    formData.append('username', credentials.email);
    formData.append('password', credentials.password);

    const tokens = await api.post<TokenResponse>('/api/v1/auth/login', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });

    // Store tokens securely
    await secureStorage.setItem(AUTH_CONFIG.TOKEN_STORAGE_KEY, tokens.access_token);
    await secureStorage.setItem(
      AUTH_CONFIG.REFRESH_TOKEN_STORAGE_KEY,
      tokens.refresh_token
    );

    // Fetch user profile
    const user = await this.getCurrentUser();

    return { user, tokens };
  }

  /**
   * Register new user
   */
  async register(data: RegisterRequest): Promise<{
    user: User;
    tokens: TokenResponse;
  }> {
    const tokens = await api.post<TokenResponse>('/api/v1/auth/register', data);

    // Store tokens securely
    await secureStorage.setItem(AUTH_CONFIG.TOKEN_STORAGE_KEY, tokens.access_token);
    await secureStorage.setItem(
      AUTH_CONFIG.REFRESH_TOKEN_STORAGE_KEY,
      tokens.refresh_token
    );

    // Fetch user profile
    const user = await this.getCurrentUser();

    return { user, tokens };
  }

  /**
   * Get current user profile
   */
  async getCurrentUser(): Promise<User> {
    const user = await api.get<User>('/api/v1/auth/me');
    // Store user data in regular storage
    await storage.setObject(AUTH_CONFIG.USER_STORAGE_KEY, user);
    return user;
  }

  /**
   * Logout user
   */
  async logout(): Promise<void> {
    // Clear all auth-related storage
    await secureStorage.removeItem(AUTH_CONFIG.TOKEN_STORAGE_KEY);
    await secureStorage.removeItem(AUTH_CONFIG.REFRESH_TOKEN_STORAGE_KEY);
    await storage.removeItem(AUTH_CONFIG.USER_STORAGE_KEY);
    await secureStorage.removeItem(AUTH_CONFIG.OIDC_STATE_KEY);
    await secureStorage.removeItem(AUTH_CONFIG.OIDC_VERIFIER_KEY);
  }

  /**
   * Get OIDC configuration from server
   */
  async getOIDCConfig(): Promise<OIDCConfig> {
    return api.get<OIDCConfig>('/api/v1/auth/oidc/config');
  }

  /**
   * Generate PKCE challenge for OIDC
   */
  private async generatePKCE(): Promise<{
    codeVerifier: string;
    codeChallenge: string;
  }> {
    // Generate a random code verifier (43-128 characters)
    const randomBytes = await Crypto.getRandomBytesAsync(32);
    const codeVerifier = Array.from(randomBytes)
      .map(b => b.toString(16).padStart(2, '0'))
      .join('');

    // Generate code challenge from verifier using base64url encoding
    // Per RFC 7636: code_challenge = BASE64URL(SHA256(ASCII(code_verifier)))
    const codeChallengeDigest = await Crypto.digestStringAsync(
      Crypto.CryptoDigestAlgorithm.SHA256,
      codeVerifier,
      { encoding: Crypto.CryptoEncoding.BASE64 }
    );

    // Convert base64 to base64url (replace +/= with -_)
    const codeChallenge = codeChallengeDigest
      .replace(/\+/g, '-')
      .replace(/\//g, '_')
      .replace(/=+$/, '');

    return { codeVerifier, codeChallenge };
  }

  /**
   * Fetch OIDC discovery document and extract authorization endpoint
   */
  private async getAuthorizationEndpoint(discoveryUrl: string): Promise<string> {
    try {
      const response = await fetch(discoveryUrl);
      const discoveryDoc = await response.json();

      if (!discoveryDoc.authorization_endpoint) {
        throw new Error('Discovery document missing authorization_endpoint');
      }

      return discoveryDoc.authorization_endpoint;
    } catch (error) {
      console.error('Failed to fetch OIDC discovery document:', error);
      throw new Error('Failed to fetch OIDC configuration from provider');
    }
  }

  /**
   * Initiate OIDC authentication flow
   */
  async initiateOIDC(): Promise<WebBrowser.WebBrowserAuthSessionResult> {
    const oidcConfig = await this.getOIDCConfig();

    if (!oidcConfig.enabled || !oidcConfig.authorization_url) {
      throw new Error('OIDC is not enabled or not configured');
    }

    const { codeVerifier, codeChallenge } = await this.generatePKCE();
    const state = Crypto.randomUUID();

    // Store PKCE verifier and state for later use
    await secureStorage.setItem(AUTH_CONFIG.OIDC_VERIFIER_KEY, codeVerifier);
    await secureStorage.setItem(AUTH_CONFIG.OIDC_STATE_KEY, state);

    const redirectUri = oidcConfig.redirect_uri || 'cartulary://auth/callback';

    // If authorization_url looks like a discovery document, fetch it
    let authorizationEndpoint = oidcConfig.authorization_url;
    if (authorizationEndpoint.includes('.well-known/openid-configuration')) {
      authorizationEndpoint = await this.getAuthorizationEndpoint(authorizationEndpoint);
    }

    // Build authorization URL
    const authUrl = new URL(authorizationEndpoint);
    authUrl.searchParams.append('client_id', oidcConfig.client_id || '');
    authUrl.searchParams.append('response_type', 'code');
    authUrl.searchParams.append('redirect_uri', redirectUri);
    authUrl.searchParams.append('scope', oidcConfig.scopes?.join(' ') || 'openid profile email');
    authUrl.searchParams.append('state', state);
    authUrl.searchParams.append('code_challenge', codeChallenge);
    authUrl.searchParams.append('code_challenge_method', 'S256');

    // Open authentication session
    const result = await WebBrowser.openAuthSessionAsync(
      authUrl.toString(),
      redirectUri
    );

    return result;
  }

  /**
   * Exchange authorization code with OIDC provider for tokens
   */
  private async exchangeCodeWithProvider(
    code: string,
    codeVerifier: string,
    discoveryUrl: string,
    clientId: string,
    redirectUri: string
  ): Promise<{ id_token: string; access_token: string }> {
    // Fetch discovery document to get token endpoint
    const discoveryResponse = await fetch(discoveryUrl);
    const discoveryDoc = await discoveryResponse.json();

    if (!discoveryDoc.token_endpoint) {
      throw new Error('Discovery document missing token_endpoint');
    }

    // Exchange code for tokens with OIDC provider
    const tokenResponse = await fetch(discoveryDoc.token_endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: new URLSearchParams({
        grant_type: 'authorization_code',
        code,
        redirect_uri: redirectUri,
        client_id: clientId,
        code_verifier: codeVerifier,
      }).toString(),
    });

    if (!tokenResponse.ok) {
      const error = await tokenResponse.text();
      throw new Error(`Token exchange failed: ${error}`);
    }

    const tokenData = await tokenResponse.json();

    if (!tokenData.id_token || !tokenData.access_token) {
      throw new Error('Token response missing id_token or access_token');
    }

    return {
      id_token: tokenData.id_token,
      access_token: tokenData.access_token,
    };
  }

  /**
   * Complete OIDC authentication by exchanging code for tokens
   */
  async completeOIDC(code: string, state: string): Promise<{
    user: User;
    tokens: TokenResponse;
  }> {
    // Verify state to prevent CSRF
    const storedState = await secureStorage.getItem(AUTH_CONFIG.OIDC_STATE_KEY);
    if (storedState !== state) {
      throw new Error('Invalid state parameter - possible CSRF attack');
    }

    const codeVerifier = await secureStorage.getItem(AUTH_CONFIG.OIDC_VERIFIER_KEY);
    if (!codeVerifier) {
      throw new Error('PKCE code verifier not found');
    }

    // Get OIDC config to get discovery URL and client ID
    const oidcConfig = await this.getOIDCConfig();
    if (!oidcConfig.authorization_url || !oidcConfig.client_id) {
      throw new Error('OIDC configuration incomplete');
    }

    const redirectUri = oidcConfig.redirect_uri || 'cartulary://auth/callback';

    // Exchange code with OIDC provider for id_token and access_token
    const oidcTokens = await this.exchangeCodeWithProvider(
      code,
      codeVerifier,
      oidcConfig.authorization_url,
      oidcConfig.client_id,
      redirectUri
    );

    // Exchange OIDC tokens for application tokens with our backend
    const tokens = await api.post<TokenResponse>('/api/v1/auth/oidc/token', {
      id_token: oidcTokens.id_token,
      access_token: oidcTokens.access_token,
    });

    // Store tokens securely
    await secureStorage.setItem(AUTH_CONFIG.TOKEN_STORAGE_KEY, tokens.access_token);
    await secureStorage.setItem(
      AUTH_CONFIG.REFRESH_TOKEN_STORAGE_KEY,
      tokens.refresh_token
    );

    // Clean up OIDC temporary storage
    await secureStorage.removeItem(AUTH_CONFIG.OIDC_STATE_KEY);
    await secureStorage.removeItem(AUTH_CONFIG.OIDC_VERIFIER_KEY);

    // Fetch user profile
    const user = await this.getCurrentUser();

    return { user, tokens };
  }

  /**
   * Check if user has valid authentication
   */
  async isAuthenticated(): Promise<boolean> {
    const token = await secureStorage.getItem(AUTH_CONFIG.TOKEN_STORAGE_KEY);
    return !!token;
  }

  /**
   * Get stored user data (without API call)
   */
  async getStoredUser(): Promise<User | null> {
    return storage.getObject<User>(AUTH_CONFIG.USER_STORAGE_KEY);
  }
}

export const authService = new AuthService();
export default authService;
