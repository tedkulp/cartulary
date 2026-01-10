/**
 * Document sharing API service
 */

import type { AxiosInstance } from 'axios'
import type {
  DocumentShare,
  DocumentShareCreate,
  DocumentShareUpdate,
  SharedDocument
} from '../types/sharing'

/**
 * Sharing service with dependency injection
 */
export class SharingService {
  constructor(private api: AxiosInstance) {}

  /**
   * Get all shares for a document
   */
  async listDocumentShares(documentId: string): Promise<DocumentShare[]> {
    const { data } = await this.api.get<DocumentShare[]>(`/api/v1/documents/${documentId}/shares`)
    return data
  }

  /**
   * Share a document with a user
   */
  async createDocumentShare(
    documentId: string,
    shareData: DocumentShareCreate
  ): Promise<DocumentShare> {
    const { data } = await this.api.post<DocumentShare>(
      `/api/v1/documents/${documentId}/shares`,
      shareData
    )
    return data
  }

  /**
   * Update a document share (change permission level or expiration)
   */
  async updateDocumentShare(
    shareId: string,
    shareData: DocumentShareUpdate
  ): Promise<DocumentShare> {
    const { data } = await this.api.patch<DocumentShare>(`/api/v1/shares/${shareId}`, shareData)
    return data
  }

  /**
   * Revoke a document share
   */
  async deleteDocumentShare(shareId: string): Promise<void> {
    await this.api.delete(`/api/v1/shares/${shareId}`)
  }

  /**
   * Get all documents shared with the current user
   */
  async listSharedWithMe(skip = 0, limit = 100): Promise<SharedDocument[]> {
    const { data } = await this.api.get<SharedDocument[]>('/api/v1/shared-with-me', {
      params: { skip, limit }
    })
    return data
  }
}
