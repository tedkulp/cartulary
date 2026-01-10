import { useState, useCallback } from 'react'
import type { SearchService, SearchMode, SearchResult } from '../services/search.service'
import type { Document } from '../types/document'

/**
 * React hook for search functionality
 * @param searchService - The search service instance
 */
export function useSearch(searchService: SearchService) {
  const [results, setResults] = useState<Document[]>([])
  const [advancedResults, setAdvancedResults] = useState<SearchResult[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [resultCount, setResultCount] = useState<number>(0)

  const search = useCallback(
    async (query: string, skip = 0, limit = 50) => {
      if (!query.trim()) {
        setResults([])
        setResultCount(0)
        return
      }

      setLoading(true)
      setError(null)

      try {
        const docs = await searchService.search(query, skip, limit)
        setResults(docs)
        setResultCount(docs.length)
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Search failed'
        setError(errorMessage)
        console.error('Error searching:', err)
      } finally {
        setLoading(false)
      }
    },
    [searchService]
  )

  const advancedSearch = useCallback(
    async (query: string, mode: SearchMode = 'hybrid', limit = 10) => {
      if (!query.trim()) {
        setAdvancedResults([])
        return
      }

      setLoading(true)
      setError(null)

      try {
        const searchResults = await searchService.advancedSearch(query, mode, limit)
        setAdvancedResults(searchResults)
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Advanced search failed'
        setError(errorMessage)
        console.error('Error in advanced search:', err)
      } finally {
        setLoading(false)
      }
    },
    [searchService]
  )

  const count = useCallback(
    async (query: string) => {
      if (!query.trim()) {
        setResultCount(0)
        return 0
      }

      try {
        const count = await searchService.count(query)
        setResultCount(count)
        return count
      } catch (err) {
        console.error('Error counting results:', err)
        return 0
      }
    },
    [searchService]
  )

  const clearResults = useCallback(() => {
    setResults([])
    setAdvancedResults([])
    setResultCount(0)
    setError(null)
  }, [])

  const clearError = useCallback(() => {
    setError(null)
  }, [])

  return {
    results,
    advancedResults,
    loading,
    error,
    resultCount,
    search,
    advancedSearch,
    count,
    clearResults,
    clearError
  }
}
