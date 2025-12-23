import api from './api'
import type { ImportSource, ImportSourceCreate, ImportSourceUpdate } from '@/types/importSource'

export const importSourceService = {
  /**
   * List all import sources for the current user
   */
  async list(skip = 0, limit = 100): Promise<ImportSource[]> {
    const { data } = await api.get<ImportSource[]>('/api/v1/import-sources', {
      params: { skip, limit }
    })
    return data
  },

  /**
   * Get a specific import source by ID
   */
  async get(id: string): Promise<ImportSource> {
    const { data } = await api.get<ImportSource>(`/api/v1/import-sources/${id}`)
    return data
  },

  /**
   * Create a new import source
   */
  async create(importSource: ImportSourceCreate): Promise<ImportSource> {
    const { data } = await api.post<ImportSource>('/api/v1/import-sources', importSource)
    return data
  },

  /**
   * Update an existing import source
   */
  async update(id: string, importSource: ImportSourceUpdate): Promise<ImportSource> {
    const { data } = await api.patch<ImportSource>(`/api/v1/import-sources/${id}`, importSource)
    return data
  },

  /**
   * Delete an import source
   */
  async delete(id: string): Promise<void> {
    await api.delete(`/api/v1/import-sources/${id}`)
  }
}
