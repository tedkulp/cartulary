import { useState, useCallback, useEffect } from 'react'
import type { DocumentService } from '../services/document.service'
import type { TagService } from '../services/tag.service'
import type { Document } from '../types/document'

/**
 * React hook for single document detail management
 * @param documentService - The document service instance
 * @param tagService - The tag service instance
 * @param documentId - The ID of the document to load
 */
export function useDocumentDetail(
  documentService: DocumentService,
  tagService: TagService,
  documentId: string
) {
  const [document, setDocument] = useState<Document | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchDocument = useCallback(async () => {
    if (!documentId) return

    setLoading(true)
    setError(null)

    try {
      const doc = await documentService.get(documentId)
      setDocument(doc)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch document'
      setError(errorMessage)
      console.error('Error fetching document:', err)
    } finally {
      setLoading(false)
    }
  }, [documentService, documentId])

  const updateDocument = useCallback(
    async (data: { title?: string; description?: string }) => {
      if (!documentId) return

      try {
        const updated = await documentService.update(documentId, data)
        setDocument(updated)
        return updated
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to update document'
        setError(errorMessage)
        console.error('Error updating document:', err)
        throw err
      }
    },
    [documentService, documentId]
  )

  const addTags = useCallback(
    async (tagIds: string[]) => {
      if (!documentId) return

      try {
        await tagService.addToDocument(documentId, tagIds)
        // Refresh document to get updated tags
        await fetchDocument()
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to add tags'
        setError(errorMessage)
        console.error('Error adding tags:', err)
        throw err
      }
    },
    [tagService, documentId, fetchDocument]
  )

  const removeTag = useCallback(
    async (tagId: string) => {
      if (!documentId) return

      try {
        await tagService.removeFromDocument(documentId, tagId)
        // Refresh document to get updated tags
        await fetchDocument()
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to remove tag'
        setError(errorMessage)
        console.error('Error removing tag:', err)
        throw err
      }
    },
    [tagService, documentId, fetchDocument]
  )

  const reprocess = useCallback(async () => {
    if (!documentId) return

    try {
      await documentService.reprocess(documentId)
      // Update document status
      if (document) {
        setDocument({ ...document, processing_status: 'pending' })
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to reprocess document'
      setError(errorMessage)
      console.error('Error reprocessing document:', err)
      throw err
    }
  }, [documentService, documentId, document])

  const regenerateEmbeddings = useCallback(async () => {
    if (!documentId) return

    try {
      await documentService.regenerateEmbeddings(documentId)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to regenerate embeddings'
      setError(errorMessage)
      console.error('Error regenerating embeddings:', err)
      throw err
    }
  }, [documentService, documentId])

  const regenerateMetadata = useCallback(async () => {
    if (!documentId) return

    try {
      await documentService.regenerateMetadata(documentId)
      // Refresh to get new metadata
      await fetchDocument()
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to regenerate metadata'
      setError(errorMessage)
      console.error('Error regenerating metadata:', err)
      throw err
    }
  }, [documentService, documentId, fetchDocument])

  const downloadFile = useCallback(
    async (filename: string) => {
      if (!documentId) return

      try {
        await documentService.downloadFile(documentId, filename)
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to download file'
        setError(errorMessage)
        console.error('Error downloading file:', err)
        throw err
      }
    },
    [documentService, documentId]
  )

  const clearError = useCallback(() => {
    setError(null)
  }, [])

  // Auto-fetch on mount or when documentId changes
  useEffect(() => {
    fetchDocument()
  }, [fetchDocument])

  return {
    document,
    loading,
    error,
    fetchDocument,
    updateDocument,
    addTags,
    removeTag,
    reprocess,
    regenerateEmbeddings,
    regenerateMetadata,
    downloadFile,
    clearError
  }
}
