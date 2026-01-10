import type { AxiosInstance } from 'axios'
import type { Document } from '../types/document'

export type SearchMode = 'fulltext' | 'semantic' | 'hybrid'

export interface SearchResult {
  document: Document
  score: number
}

/**
 * Search service with dependency injection
 */
export class SearchService {
  constructor(private api: AxiosInstance) {}

  async search(query: string, skip = 0, limit = 50): Promise<Document[]> {
    const { data } = await this.api.get<Document[]>('/api/v1/search', {
      params: { q: query, skip, limit },
    })
    return data
  }

  async count(query: string): Promise<number> {
    const { data } = await this.api.get<{ query: string; count: number }>(
      '/api/v1/search/count',
      {
        params: { q: query },
      }
    )
    return data.count
  }

  async advancedSearch(
    query: string,
    mode: SearchMode = 'hybrid',
    limit = 10
  ): Promise<SearchResult[]> {
    const { data } = await this.api.get<SearchResult[]>('/api/v1/search/advanced', {
      params: { q: query, mode, limit },
    })
    return data
  }
}
