import type { AxiosInstance } from 'axios'
import type { ImportSource, ImportSourceCreate, ImportSourceUpdate } from '../types/importSource'

/**
 * Import source service with dependency injection
 */
export class ImportSourceService {
  constructor(private api: AxiosInstance) {}

  /**
   * List all import sources for the current user
   */
  async list(skip = 0, limit = 100): Promise<ImportSource[]> {
    const { data } = await this.api.get<ImportSource[]>('/api/v1/import-sources', {
      params: { skip, limit }
    })
    return data
  }

  /**
   * Get a specific import source by ID
   */
  async get(id: string): Promise<ImportSource> {
    const { data } = await this.api.get<ImportSource>(`/api/v1/import-sources/${id}`)
    return data
  }

  /**
   * Create a new import source
   */
  async create(importSource: ImportSourceCreate): Promise<ImportSource> {
    const { data } = await this.api.post<ImportSource>('/api/v1/import-sources', importSource)
    return data
  }

  /**
   * Update an existing import source
   */
  async update(id: string, importSource: ImportSourceUpdate): Promise<ImportSource> {
    const { data } = await this.api.patch<ImportSource>(`/api/v1/import-sources/${id}`, importSource)
    return data
  }

  /**
   * Delete an import source
   */
  async delete(id: string): Promise<void> {
    await this.api.delete(`/api/v1/import-sources/${id}`)
  }
}
