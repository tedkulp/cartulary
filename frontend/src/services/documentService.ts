import type { Document, DocumentUploadData } from '@/types/document'
import api from './api'

export const documentService = {
  async upload(data: DocumentUploadData): Promise<Document> {
    const formData = new FormData()
    formData.append('file', data.file)
    if (data.title) {
      formData.append('title', data.title)
    }

    const response = await api.post<Document>('/api/v1/documents', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data
  },

  async list(skip = 0, limit = 50): Promise<Document[]> {
    const response = await api.get<Document[]>('/api/v1/documents', {
      params: { skip, limit },
    })
    return response.data
  },

  async get(id: string): Promise<Document> {
    const response = await api.get<Document>(`/api/v1/documents/${id}`)
    return response.data
  },

  async update(id: string, data: { title?: string }): Promise<Document> {
    const response = await api.patch<Document>(`/api/v1/documents/${id}`, data)
    return response.data
  },

  async delete(id: string): Promise<void> {
    await api.delete(`/api/v1/documents/${id}`)
  },

  async reprocess(id: string): Promise<void> {
    await api.post(`/api/v1/documents/${id}/reprocess`)
  },

  getDownloadUrl(id: string): string {
    return `/api/v1/documents/${id}/download`
  },
}
