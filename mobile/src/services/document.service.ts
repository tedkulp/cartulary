import * as FileSystem from 'expo-file-system/legacy';
import { api } from './api';
import { DOCUMENT_CONFIG } from '@config/constants';
import type {
  Document,
  SearchRequest,
  SearchResponse,
} from '../types/api';

class DocumentService {
  /**
   * Get list of documents with pagination
   */
  async list(params?: {
    page?: number;
    page_size?: number;
    sort_by?: string;
    sort_order?: 'asc' | 'desc';
    tags?: string[];
  }): Promise<Document[]> {
    const queryParams = new URLSearchParams();

    // Backend uses skip/limit, not page/page_size
    const page = params?.page || 1;
    const pageSize = params?.page_size || DOCUMENT_CONFIG.PAGE_SIZE;
    const skip = (page - 1) * pageSize;

    queryParams.append('skip', String(skip));
    queryParams.append('limit', String(pageSize));

    if (params?.sort_by) {
      queryParams.append('sort_by', params.sort_by);
    }
    if (params?.sort_order) {
      queryParams.append('sort_order', params.sort_order);
    }
    if (params?.tags?.length) {
      params.tags.forEach(tag => queryParams.append('tags', tag));
    }

    return api.get<Document[]>(`/api/v1/documents?${queryParams.toString()}`);
  }

  /**
   * Get single document by ID
   */
  async getById(id: string): Promise<Document> {
    return api.get<Document>(`/api/v1/documents/${id}`);
  }

  /**
   * Upload document from local file URI
   */
  async upload(params: {
    uri: string;
    fileName: string;
    mimeType: string;
    title?: string;
    tags?: string[];
    metadata?: Record<string, any>;
  }): Promise<Document> {
    const formData = new FormData();

    // Add file
    const file: any = {
      uri: params.uri,
      name: params.fileName,
      type: params.mimeType,
    };
    formData.append('file', file);

    // Add optional metadata
    if (params.title) {
      formData.append('title', params.title);
    }
    if (params.tags?.length) {
      formData.append('tags', JSON.stringify(params.tags));
    }
    if (params.metadata) {
      formData.append('metadata', JSON.stringify(params.metadata));
    }

    return api.post<Document>('/api/v1/documents', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  }

  /**
   * Update document metadata
   */
  async update(
    id: string,
    data: {
      title?: string;
      tags?: string[];
      metadata?: Record<string, any>;
    }
  ): Promise<Document> {
    return api.patch<Document>(`/api/v1/documents/${id}`, data);
  }

  /**
   * Delete document
   */
  async delete(id: string): Promise<void> {
    await api.delete(`/api/v1/documents/${id}`);
  }

  /**
   * Download document to local storage
   */
  async download(document: Document): Promise<string> {
    try {
      // Create file path in temporary storage
      if (!FileSystem.cacheDirectory) {
        throw new Error('Cache directory not available');
      }

      const fileUri = FileSystem.cacheDirectory + document.original_filename;
      const downloadUrl = `${await this.getBaseUrl()}/api/v1/documents/${document.id}/download`;
      const headers = await this.getAuthHeaders();

      console.log('Downloading from:', downloadUrl);
      console.log('Download headers:', headers);
      console.log('Saving to:', fileUri);

      const downloadResult = await FileSystem.downloadAsync(
        downloadUrl,
        fileUri,
        {
          headers,
        }
      );

      console.log('Download result:', downloadResult);

      if (downloadResult.status !== 200) {
        throw new Error(`Download failed with status ${downloadResult.status}`);
      }

      return downloadResult.uri;
    } catch (error) {
      console.error('Download error:', error);
      throw error;
    }
  }

  /**
   * Get document download URL
   */
  async getDownloadUrl(documentId: string): Promise<string> {
    const baseUrl = await this.getBaseUrl();
    return `${baseUrl}/api/v1/documents/${documentId}/download`;
  }

  /**
   * Search documents
   */
  async search(request: SearchRequest): Promise<SearchResponse> {
    const queryParams = new URLSearchParams();

    queryParams.append('query', request.query);
    queryParams.append('page', String(request.page || 1));
    queryParams.append('page_size', String(request.page_size || DOCUMENT_CONFIG.PAGE_SIZE));

    if (request.filters?.tags?.length) {
      request.filters.tags.forEach(tag => queryParams.append('tags', tag));
    }
    if (request.filters?.date_from) {
      queryParams.append('date_from', request.filters.date_from);
    }
    if (request.filters?.date_to) {
      queryParams.append('date_to', request.filters.date_to);
    }

    return api.get<SearchResponse>(`/api/v1/search?${queryParams.toString()}`);
  }

  /**
   * Advanced semantic search
   */
  async advancedSearch(request: SearchRequest): Promise<SearchResponse> {
    const queryParams = new URLSearchParams();

    queryParams.append('query', request.query);
    queryParams.append('page', String(request.page || 1));
    queryParams.append('page_size', String(request.page_size || DOCUMENT_CONFIG.PAGE_SIZE));

    if (request.filters?.tags?.length) {
      request.filters.tags.forEach(tag => queryParams.append('tags', tag));
    }
    if (request.filters?.date_from) {
      queryParams.append('date_from', request.filters.date_from);
    }
    if (request.filters?.date_to) {
      queryParams.append('date_to', request.filters.date_to);
    }

    return api.get<SearchResponse>(`/api/v1/search/advanced?${queryParams.toString()}`);
  }

  /**
   * Get all available tags
   */
  async getTags(): Promise<string[]> {
    return api.get<string[]>('/api/v1/documents/tags');
  }

  // Helper methods
  private async getBaseUrl(): Promise<string> {
    const { storage } = await import('@utils/storage');
    const { AUTH_CONFIG, API_CONFIG } = await import('@config/constants');
    return (await storage.getItem(AUTH_CONFIG.API_URL_STORAGE_KEY)) || API_CONFIG.DEFAULT_URL;
  }

  private async getAuthHeaders(): Promise<Record<string, string>> {
    const { secureStorage } = await import('@utils/storage');
    const { AUTH_CONFIG } = await import('@config/constants');
    const token = await secureStorage.getItem(AUTH_CONFIG.TOKEN_STORAGE_KEY);
    return token ? { Authorization: `Bearer ${token}` } : {};
  }
}

export const documentService = new DocumentService();
export default documentService;
