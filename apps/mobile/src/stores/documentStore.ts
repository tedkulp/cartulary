import { create } from 'zustand';
import { documentService } from '@services/document.service';
import type { Document } from '@cartulary/shared';

// Mobile-specific search result type
interface SearchResult {
  document: Document;
  score: number;
  highlights?: string[];
}

interface DocumentState {
  documents: Document[];
  currentDocument: Document | null;
  totalDocuments: number;
  currentPage: number;
  totalPages: number;
  isLoading: boolean;
  isRefreshing: boolean;
  error: string | null;

  // Search state
  searchResults: SearchResult[];
  searchQuery: string;
  isSearching: boolean;
  searchTotal: number;

  // Actions
  fetchDocuments: (params?: {
    page?: number;
    refresh?: boolean;
    sort_by?: string;
    sort_order?: 'asc' | 'desc';
  }) => Promise<void>;
  fetchDocumentById: (id: string) => Promise<void>;
  uploadDocument: (params: {
    uri: string;
    fileName: string;
    mimeType: string;
    title?: string;
    tags?: string[];
  }) => Promise<Document>;
  updateDocument: (
    id: string,
    data: {
      title?: string;
      description?: string;
      tags?: string[];
      metadata?: Record<string, any>;
    }
  ) => Promise<void>;
  deleteDocument: (id: string) => Promise<void>;
  search: (query: string, advanced?: boolean) => Promise<void>;
  clearSearch: () => void;
  clearError: () => void;
  reset: () => void;
}

const initialState = {
  documents: [],
  currentDocument: null,
  totalDocuments: 0,
  currentPage: 1,
  totalPages: 1,
  isLoading: false,
  isRefreshing: false,
  error: null,
  searchResults: [],
  searchQuery: '',
  isSearching: false,
  searchTotal: 0,
};

export const useDocumentStore = create<DocumentState>((set, get) => ({
  ...initialState,

  fetchDocuments: async (params) => {
    try {
      const isRefresh = params?.refresh ?? false;
      const page = params?.page ?? 1;

      set({
        isLoading: !isRefresh,
        isRefreshing: isRefresh,
        error: null,
      });

      console.log('Fetching documents with params:', params);

      const newDocuments = await documentService.list({
        page,
        sort_by: params?.sort_by,
        sort_order: params?.sort_order,
      });

      console.log('Documents response:', newDocuments);
      console.log('Documents count:', newDocuments?.length);

      // Since backend returns a simple array without pagination metadata,
      // we'll estimate pagination based on the response size
      const { DOCUMENT_CONFIG } = await import('@config/constants');
      const pageSize = DOCUMENT_CONFIG.PAGE_SIZE; // 20
      const hasMorePages = newDocuments.length === pageSize;

      console.log('Page size:', pageSize, 'Has more pages:', hasMorePages);

      const currentDocs = get().documents;
      const updatedDocuments = isRefresh
        ? newDocuments
        : page === 1
        ? newDocuments
        : [...currentDocs, ...newDocuments];

      const newState = {
        documents: updatedDocuments,
        totalDocuments: updatedDocuments.length, // Total documents loaded so far
        currentPage: page,
        // If we got a full page, there might be more; if we got fewer, we're at the end
        totalPages: hasMorePages ? page + 1 : page,
        isLoading: false,
        isRefreshing: false,
      };

      console.log('Updating state:', {
        documentsCount: newState.documents.length,
        currentPage: newState.currentPage,
        totalPages: newState.totalPages,
        hasMorePages
      });

      set(newState);
    } catch (error: any) {
      console.error('Failed to fetch documents:', error);
      set({
        isLoading: false,
        isRefreshing: false,
        error: error.detail || 'Failed to fetch documents',
      });
      throw error;
    }
  },

  fetchDocumentById: async (id: string) => {
    try {
      set({ isLoading: true, error: null });

      const document = await documentService.getById(id);

      set({
        currentDocument: document,
        isLoading: false,
      });
    } catch (error: any) {
      set({
        isLoading: false,
        error: error.detail || 'Failed to fetch document',
      });
      throw error;
    }
  },

  uploadDocument: async (params) => {
    try {
      set({ isLoading: true, error: null });

      const document = await documentService.upload(params);

      // Add to beginning of documents list
      set((state) => ({
        documents: [document, ...state.documents],
        totalDocuments: state.totalDocuments + 1,
        isLoading: false,
      }));

      return document;
    } catch (error: any) {
      set({
        isLoading: false,
        error: error.detail || 'Failed to upload document',
      });
      throw error;
    }
  },

  updateDocument: async (id, data) => {
    try {
      set({ isLoading: true, error: null });

      const updatedDoc = await documentService.update(id, data);

      // Update in documents list
      set((state) => ({
        documents: state.documents.map((doc) =>
          doc.id === id ? updatedDoc : doc
        ),
        currentDocument:
          state.currentDocument?.id === id ? updatedDoc : state.currentDocument,
        isLoading: false,
      }));
    } catch (error: any) {
      set({
        isLoading: false,
        error: error.detail || 'Failed to update document',
      });
      throw error;
    }
  },

  deleteDocument: async (id) => {
    try {
      set({ isLoading: true, error: null });

      await documentService.delete(id);

      // Remove from documents list
      set((state) => ({
        documents: state.documents.filter((doc) => doc.id !== id),
        totalDocuments: state.totalDocuments - 1,
        currentDocument:
          state.currentDocument?.id === id ? null : state.currentDocument,
        isLoading: false,
      }));
    } catch (error: any) {
      set({
        isLoading: false,
        error: error.detail || 'Failed to delete document',
      });
      throw error;
    }
  },

  search: async (query, advanced = false) => {
    try {
      set({ isSearching: true, error: null, searchQuery: query });

      const searchFn = advanced
        ? documentService.advancedSearch
        : documentService.search;

      const response = await searchFn.call(documentService, { query });

      set({
        searchResults: response.results,
        searchTotal: response.total,
        isSearching: false,
      });
    } catch (error: any) {
      set({
        isSearching: false,
        error: error.detail || 'Search failed',
      });
      throw error;
    }
  },

  clearSearch: () => {
    set({
      searchResults: [],
      searchQuery: '',
      searchTotal: 0,
    });
  },

  clearError: () => set({ error: null }),

  reset: () => set(initialState),
}));
