import { useState, useCallback } from 'react'
import type { DocumentService } from '../services/document.service'
import type { Document, DocumentUploadData } from '../types/document'

export interface UploadProgress {
  file: File
  title?: string
  status: 'pending' | 'uploading' | 'success' | 'error' | 'duplicate'
  progress: number
  error?: string
  document?: Document
  duplicateId?: string
}

/**
 * React hook for document upload functionality
 * @param documentService - The document service instance
 */
export function useDocumentUpload(documentService: DocumentService) {
  const [uploads, setUploads] = useState<Map<string, UploadProgress>>(new Map())
  const [isUploading, setIsUploading] = useState(false)

  const uploadFile = useCallback(
    async (file: File, title?: string) => {
      const fileId = `${file.name}-${file.size}-${Date.now()}`

      // Add to uploads with pending status
      setUploads((prev) => {
        const newUploads = new Map(prev)
        newUploads.set(fileId, {
          file,
          title,
          status: 'pending',
          progress: 0
        })
        return newUploads
      })

      setIsUploading(true)

      try {
        // Update to uploading
        setUploads((prev) => {
          const newUploads = new Map(prev)
          const upload = newUploads.get(fileId)
          if (upload) {
            newUploads.set(fileId, { ...upload, status: 'uploading', progress: 50 })
          }
          return newUploads
        })

        const uploadData: DocumentUploadData = { file, title }
        const document = await documentService.upload(uploadData)

        // Update to success
        setUploads((prev) => {
          const newUploads = new Map(prev)
          newUploads.set(fileId, {
            file,
            title,
            status: 'success',
            progress: 100,
            document
          })
          return newUploads
        })

        return { success: true, document, fileId }
      } catch (err: any) {
        // Check for duplicate error (409 status)
        if (err.response?.status === 409) {
          const duplicateId = err.response?.data?.document_id

          setUploads((prev) => {
            const newUploads = new Map(prev)
            newUploads.set(fileId, {
              file,
              title,
              status: 'duplicate',
              progress: 100,
              duplicateId,
              error: 'This document already exists'
            })
            return newUploads
          })

          return { success: false, duplicate: true, duplicateId, fileId }
        }

        // Regular error
        const errorMessage = err.response?.data?.detail || err.message || 'Upload failed'

        setUploads((prev) => {
          const newUploads = new Map(prev)
          newUploads.set(fileId, {
            file,
            title,
            status: 'error',
            progress: 0,
            error: errorMessage
          })
          return newUploads
        })

        return { success: false, error: errorMessage, fileId }
      } finally {
        setIsUploading(false)
      }
    },
    [documentService]
  )

  const uploadMultiple = useCallback(
    async (files: File[]) => {
      setIsUploading(true)

      const results = await Promise.allSettled(
        files.map((file) => uploadFile(file))
      )

      setIsUploading(false)

      return results.map((result, index) => {
        if (result.status === 'fulfilled') {
          return result.value
        } else {
          return {
            success: false,
            error: result.reason?.message || 'Upload failed',
            fileId: `error-${index}`
          }
        }
      })
    },
    [uploadFile]
  )

  const removeUpload = useCallback((fileId: string) => {
    setUploads((prev) => {
      const newUploads = new Map(prev)
      newUploads.delete(fileId)
      return newUploads
    })
  }, [])

  const clearUploads = useCallback(() => {
    setUploads(new Map())
  }, [])

  const clearCompletedUploads = useCallback(() => {
    setUploads((prev) => {
      const newUploads = new Map(prev)
      Array.from(newUploads.entries()).forEach(([id, upload]) => {
        if (upload.status === 'success' || upload.status === 'duplicate') {
          newUploads.delete(id)
        }
      })
      return newUploads
    })
  }, [])

  return {
    uploads: Array.from(uploads.values()),
    uploadsMap: uploads,
    isUploading,
    uploadFile,
    uploadMultiple,
    removeUpload,
    clearUploads,
    clearCompletedUploads
  }
}
