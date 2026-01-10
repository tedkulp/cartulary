import { useState, useCallback } from 'react'
import type { DocumentService } from '../services/document.service'
import type { Document } from '../types/document'

/**
 * React hook for document list management
 * @param documentService - The document service instance
 */
export function useDocuments(documentService: DocumentService) {
  const [documents, setDocuments] = useState<Document[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchDocuments = useCallback(
    async (params?: {
      skip?: number
      limit?: number
      sortBy?: string
      sortOrder?: 'asc' | 'desc'
    }) => {
      setLoading(true)
      setError(null)

      try {
        const docs = await documentService.list(
          params?.skip,
          params?.limit,
          params?.sortBy,
          params?.sortOrder
        )
        setDocuments(docs)
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to fetch documents'
        setError(errorMessage)
        console.error('Error fetching documents:', err)
      } finally {
        setLoading(false)
      }
    },
    [documentService]
  )

  const deleteDocument = useCallback(
    async (id: string) => {
      try {
        await documentService.delete(id)
        setDocuments((prev) => prev.filter((doc) => doc.id !== id))
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to delete document'
        setError(errorMessage)
        console.error('Error deleting document:', err)
        throw err
      }
    },
    [documentService]
  )

  const updateDocument = useCallback(
    async (id: string, data: { title?: string; description?: string }) => {
      try {
        const updated = await documentService.update(id, data)
        setDocuments((prev) =>
          prev.map((doc) => (doc.id === id ? updated : doc))
        )
        return updated
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to update document'
        setError(errorMessage)
        console.error('Error updating document:', err)
        throw err
      }
    },
    [documentService]
  )

  const reprocessDocument = useCallback(
    async (id: string) => {
      try {
        await documentService.reprocess(id)
        // Update the document status in the list
        setDocuments((prev) =>
          prev.map((doc) =>
            doc.id === id ? { ...doc, processing_status: 'pending' } : doc
          )
        )
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to reprocess document'
        setError(errorMessage)
        console.error('Error reprocessing document:', err)
        throw err
      }
    },
    [documentService]
  )

  const regenerateEmbeddings = useCallback(
    async (id: string) => {
      try {
        await documentService.regenerateEmbeddings(id)
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to regenerate embeddings'
        setError(errorMessage)
        console.error('Error regenerating embeddings:', err)
        throw err
      }
    },
    [documentService]
  )

  const regenerateMetadata = useCallback(
    async (id: string) => {
      try {
        await documentService.regenerateMetadata(id)
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to regenerate metadata'
        setError(errorMessage)
        console.error('Error regenerating metadata:', err)
        throw err
      }
    },
    [documentService]
  )

  const clearError = useCallback(() => {
    setError(null)
  }, [])

  return {
    documents,
    loading,
    error,
    fetchDocuments,
    deleteDocument,
    updateDocument,
    reprocessDocument,
    regenerateEmbeddings,
    regenerateMetadata,
    clearError
  }
}
