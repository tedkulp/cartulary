export interface User {
  id: string;
  email: string;
  full_name?: string;
  is_active: boolean;
  is_superuser: boolean;
  role?: string;
  created_at: string;
  updated_at: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  full_name?: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface OIDCConfig {
  enabled: boolean;
  authorization_url?: string;
  token_url?: string;
  client_id?: string;
  scopes?: string[];
  redirect_uri?: string;
}

export interface Tag {
  id: string;
  name: string;
  color?: string;
  description?: string;
  created_at: string;
}

export interface Document {
  id: string;
  title: string;
  original_filename: string;
  file_extension: string;
  mime_type: string;
  file_size: number;
  checksum: string;
  ocr_text?: string;
  processing_status: 'pending' | 'processing' | 'completed' | 'failed';
  tags: Tag[];
  description?: string;
  extracted_title?: string;
  extracted_correspondent?: string;
  extracted_document_type?: string;
  extracted_summary?: string;
  extracted_date?: string;
  uploaded_by: string;
  created_at: string;
  updated_at: string;
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
  document: Document;
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
