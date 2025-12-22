import api from './api'
import type { Document } from '@/types/document'

export const searchService = {
  async search(query: string, skip = 0, limit = 50): Promise<Document[]> {
    const { data } = await api.get<Document[]>('/api/v1/search', {
      params: { q: query, skip, limit },
    })
    return data
  },

  async count(query: string): Promise<number> {
    const { data } = await api.get<{ query: string; count: number }>(
      '/api/v1/search/count',
      {
        params: { q: query },
      }
    )
    return data.count
  },
}
