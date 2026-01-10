// Re-export shared types for convenience
export type {
  User,
  LoginCredentials,
  RegisterData,
  TokenResponse,
  Document,
  Tag,
} from '@cartulary/shared';

// Mobile-specific types that aren't in shared

export interface OIDCConfig {
  enabled: boolean;
  authorization_url?: string;
  token_url?: string;
  client_id?: string;
  scopes?: string[];
  redirect_uri?: string;
}

export interface DocumentListResponse {
  documents: Document[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface DocumentUploadRequest {
  file: File | Blob;
  title?: string;
  tags?: string[];
  metadata?: Record<string, any>;
}

export interface SearchRequest {
  query: string;
  page?: number;
  page_size?: number;
  filters?: {
    tags?: string[];
    date_from?: string;
    date_to?: string;
  };
}

export interface SearchResult {
  document: import('@cartulary/shared').Document;
  score: number;
  highlights?: string[];
}

export interface SearchResponse {
  results: SearchResult[];
  total: number;
  page: number;
  page_size: number;
  query: string;
}

export interface ApiError {
  detail: string | { error: string; message?: string };
  status: number;
}
