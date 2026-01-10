import type { AxiosInstance } from 'axios'
import type { Tag, TagCreate, TagUpdate } from '../types/document'

/**
 * Tag service with dependency injection
 */
export class TagService {
  constructor(private api: AxiosInstance) {}

  async list(skip = 0, limit = 10000): Promise<Tag[]> {
    const { data } = await this.api.get<Tag[]>('/api/v1/tags', {
      params: { skip, limit },
    })
    return data
  }

  async get(tagId: string): Promise<Tag> {
    const { data } = await this.api.get<Tag>(`/api/v1/tags/${tagId}`)
    return data
  }

  async create(tag: TagCreate): Promise<Tag> {
    const { data } = await this.api.post<Tag>('/api/v1/tags', tag)
    return data
  }

  async update(tagId: string, tag: TagUpdate): Promise<Tag> {
    const { data } = await this.api.patch<Tag>(`/api/v1/tags/${tagId}`, tag)
    return data
  }

  async delete(tagId: string): Promise<void> {
    await this.api.delete(`/api/v1/tags/${tagId}`)
  }

  async addToDocument(documentId: string, tagIds: string[]): Promise<void> {
    await this.api.post(`/api/v1/tags/documents/${documentId}/tags`, {
      tag_ids: tagIds,
    })
  }

  async removeFromDocument(documentId: string, tagId: string): Promise<void> {
    await this.api.delete(`/api/v1/tags/documents/${documentId}/tags/${tagId}`)
  }
}
