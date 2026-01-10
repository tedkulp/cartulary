import type { AxiosInstance } from 'axios'
import type { Document, DocumentUploadData } from '../types/document'

/**
 * Document service with dependency injection for platform-agnostic usage
 */
export class DocumentService {
  constructor(private api: AxiosInstance) {}

  async upload(data: DocumentUploadData): Promise<Document> {
    const formData = new FormData()
    formData.append('file', data.file)
    if (data.title) {
      formData.append('title', data.title)
    }

    const response = await this.api.post<Document>('/api/v1/documents', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data
  }

  async list(skip = 0, limit = 1000, sortBy = 'created_at', sortOrder = 'desc'): Promise<Document[]> {
    const response = await this.api.get<Document[]>('/api/v1/documents', {
      params: {
        skip,
        limit,
        sort_by: sortBy,
        sort_order: sortOrder
      },
    })
    return response.data
  }

  async get(id: string): Promise<Document> {
    const response = await this.api.get<Document>(`/api/v1/documents/${id}`)
    return response.data
  }

  async update(id: string, data: { title?: string; description?: string }): Promise<Document> {
    const response = await this.api.patch<Document>(`/api/v1/documents/${id}`, data)
    return response.data
  }

  async delete(id: string): Promise<void> {
    await this.api.delete(`/api/v1/documents/${id}`)
  }

  async reprocess(id: string): Promise<void> {
    await this.api.post(`/api/v1/documents/${id}/reprocess`)
  }

  async regenerateEmbeddings(id: string): Promise<void> {
    await this.api.post(`/api/v1/documents/${id}/regenerate-embeddings`)
  }

  async regenerateMetadata(id: string): Promise<void> {
    await this.api.post(`/api/v1/documents/${id}/regenerate-metadata`)
  }

  getDownloadUrl(id: string): string {
    return `/api/v1/documents/${id}/download`
  }

  /**
   * Platform-specific file download
   * For web: creates blob and triggers download
   * For mobile: should use FileSystem API (not implemented here)
   */
  async downloadFile(id: string, filename: string): Promise<void> {
    // Check if we're in a browser environment
    if (typeof window !== 'undefined' && window.document) {
      // Web platform
      const response = await this.api.get(`/api/v1/documents/${id}/download`, {
        responseType: 'blob',
      })

      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', filename)
      document.body.appendChild(link)
      link.click()
      link.parentNode?.removeChild(link)
      window.URL.revokeObjectURL(url)
    } else {
      // Mobile/React Native platform
      // This should be implemented in the mobile-specific service wrapper
      throw new Error('downloadFile not implemented for this platform. Use platform-specific implementation.')
    }
  }
}
