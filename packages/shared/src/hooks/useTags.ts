import { useState, useCallback } from 'react'
import type { TagService } from '../services/tag.service'
import type { Tag, TagCreate, TagUpdate } from '../types/document'

/**
 * React hook for tag management
 * @param tagService - The tag service instance
 */
export function useTags(tagService: TagService) {
  const [tags, setTags] = useState<Tag[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchTags = useCallback(
    async (params?: { skip?: number; limit?: number }) => {
      setLoading(true)
      setError(null)

      try {
        const tagsList = await tagService.list(params?.skip, params?.limit)
        setTags(tagsList)
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to fetch tags'
        setError(errorMessage)
        console.error('Error fetching tags:', err)
      } finally {
        setLoading(false)
      }
    },
    [tagService]
  )

  const createTag = useCallback(
    async (tag: TagCreate) => {
      try {
        const created = await tagService.create(tag)
        setTags((prev) => [...prev, created])
        return created
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to create tag'
        setError(errorMessage)
        console.error('Error creating tag:', err)
        throw err
      }
    },
    [tagService]
  )

  const updateTag = useCallback(
    async (tagId: string, tag: TagUpdate) => {
      try {
        const updated = await tagService.update(tagId, tag)
        setTags((prev) => prev.map((t) => (t.id === tagId ? updated : t)))
        return updated
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to update tag'
        setError(errorMessage)
        console.error('Error updating tag:', err)
        throw err
      }
    },
    [tagService]
  )

  const deleteTag = useCallback(
    async (tagId: string) => {
      try {
        await tagService.delete(tagId)
        setTags((prev) => prev.filter((t) => t.id !== tagId))
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to delete tag'
        setError(errorMessage)
        console.error('Error deleting tag:', err)
        throw err
      }
    },
    [tagService]
  )

  const clearError = useCallback(() => {
    setError(null)
  }, [])

  return {
    tags,
    loading,
    error,
    fetchTags,
    createTag,
    updateTag,
    deleteTag,
    clearError,
  }
}
