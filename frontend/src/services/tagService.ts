import api from './api'

export interface Tag {
  id: string
  name: string
  color?: string
  description?: string
  created_at: string
}

export interface TagCreate {
  name: string
  color?: string
  description?: string
}

export interface TagUpdate {
  name?: string
  color?: string
  description?: string
}

export const tagService = {
  async list(skip = 0, limit = 10000): Promise<Tag[]> {
    const { data } = await api.get<Tag[]>('/api/v1/tags', {
      params: { skip, limit },
    })
    return data
  },

  async get(tagId: string): Promise<Tag> {
    const { data } = await api.get<Tag>(`/api/v1/tags/${tagId}`)
    return data
  },

  async create(tag: TagCreate): Promise<Tag> {
    const { data } = await api.post<Tag>('/api/v1/tags', tag)
    return data
  },

  async update(tagId: string, tag: TagUpdate): Promise<Tag> {
    const { data } = await api.patch<Tag>(`/api/v1/tags/${tagId}`, tag)
    return data
  },

  async delete(tagId: string): Promise<void> {
    await api.delete(`/api/v1/tags/${tagId}`)
  },

  async addToDocument(documentId: string, tagIds: string[]): Promise<void> {
    await api.post(`/api/v1/tags/documents/${documentId}/tags`, {
      tag_ids: tagIds,
    })
  },

  async removeFromDocument(documentId: string, tagId: string): Promise<void> {
    await api.delete(`/api/v1/tags/documents/${documentId}/tags/${tagId}`)
  },
}
