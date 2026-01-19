import { useEffect, useState, useMemo, useCallback } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useDocuments, useWebSocket, useAuthStore } from '@cartulary/shared'
import { documentService, searchService, tagService, websocketService } from '../services'
import type { Document, Tag, SearchMode } from '@cartulary/shared'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import {
  Upload,
  Search,
  X,
  Trash2,
  ChevronUp,
  ChevronDown,
  Filter,
  Loader2,
  FileText,
  RotateCcw,
  Sparkles,
  Brain,
  HelpCircle,
} from 'lucide-react'
import { toast } from 'sonner'
import { Checkbox } from '@/components/ui/checkbox'
import UploadDialog from '@/components/UploadDialog'

// Helper function moved outside component for better performance
const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

export default function DocumentsList() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const { documents, loading, fetchDocuments, deleteDocument } = useDocuments(documentService)

  // Search state
  const [searchQuery, setSearchQuery] = useState('')
  const [searchMode, setSearchMode] = useState<SearchMode>('hybrid')
  const [searchResults, setSearchResults] = useState<Document[]>([])
  const [isSearching, setIsSearching] = useState(false)

  // Filter state
  const [showFilters, setShowFilters] = useState(false)
  const [nameFilter, setNameFilter] = useState('')
  const [selectedTags, setSelectedTags] = useState<string[]>([])
  const [availableTags, setAvailableTags] = useState<Tag[]>([])
  const [filterTagId, setFilterTagId] = useState<string | null>(null)
  const [selectedTag, setSelectedTag] = useState<Tag | null>(null)

  // Sorting state
  const [sortField, setSortField] = useState<string>('created_at')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')

  // Delete dialog state
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [documentToDelete, setDocumentToDelete] = useState<Document | null>(null)

  // Upload dialog state
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false)

  // Selection state
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [bulkDeleteDialogOpen, setBulkDeleteDialogOpen] = useState(false)
  const [bulkActionLoading, setBulkActionLoading] = useState(false)

  // WebSocket
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated())
  const { subscribe } = useWebSocket(websocketService, isAuthenticated)

  // Memoized filtered documents for better performance
  const filteredDocuments = useMemo(() => {
    let filtered = [...documents]

    // Apply tag filter from URL
    if (filterTagId) {
      filtered = filtered.filter(doc =>
        doc.tags?.some(tag => tag.id === filterTagId)
      )
    }

    // Apply name filter
    if (nameFilter.trim()) {
      const query = nameFilter.toLowerCase()
      filtered = filtered.filter(doc =>
        doc.title.toLowerCase().includes(query) ||
        doc.original_filename.toLowerCase().includes(query)
      )
    }

    // Apply tags filter
    if (selectedTags.length > 0) {
      filtered = filtered.filter(doc =>
        selectedTags.some(tagId =>
          doc.tags?.some(tag => tag.id === tagId)
        )
      )
    }

    return filtered
  }, [documents, filterTagId, nameFilter, selectedTags])

  // Get displayed documents (search results or filtered documents)
  const displayedDocuments = searchQuery ? searchResults : filteredDocuments

  // Memoized statistics for better performance
  const statistics = useMemo(() => {
    const totalDocuments = displayedDocuments.length
    const totalFileSize = displayedDocuments.reduce((sum, doc) => sum + (doc.file_size || 0), 0)
    const totalWords = displayedDocuments.reduce((sum, doc) => {
      if (doc.ocr_text) {
        const words = doc.ocr_text.trim().split(/\s+/).filter(w => w.length > 0)
        return sum + words.length
      }
      return sum
    }, 0)
    const averageFileSize = totalDocuments > 0 ? totalFileSize / totalDocuments : 0

    return { totalDocuments, totalFileSize, totalWords, averageFileSize }
  }, [displayedDocuments])

  const activeFilterCount = (nameFilter.trim() ? 1 : 0) + (selectedTags.length > 0 ? 1 : 0)

  // Load documents
  useEffect(() => {
    fetchDocuments({ sortBy: sortField, sortOrder })
  }, [fetchDocuments, sortField, sortOrder])

  // Load tags
  useEffect(() => {
    const loadTags = async () => {
      try {
        const tags = await tagService.list()
        setAvailableTags(tags)
      } catch (error) {
        console.error('Failed to load tags:', error)
      }
    }
    loadTags()
  }, [])

  // Handle tag filter from URL
  useEffect(() => {
    const tagParam = searchParams.get('tag')
    if (tagParam) {
      setFilterTagId(tagParam)
      const loadTag = async () => {
        try {
          const tag = await tagService.get(tagParam)
          setSelectedTag(tag)
        } catch (error) {
          console.error('Failed to load tag:', error)
          setFilterTagId(null)
        }
      }
      loadTag()
    } else {
      setFilterTagId(null)
      setSelectedTag(null)
    }
  }, [searchParams])

  // WebSocket subscriptions
  useEffect(() => {
    const unsubscribers: (() => void)[] = []

    // Document created
    unsubscribers.push(
      subscribe('document.created', async (event) => {
        const exists = documents.some(d => d.id === event.data.document_id)
        if (!exists && event.data.document_id) {
          try {
            await fetchDocuments({ sortBy: sortField, sortOrder })
            toast.success('New document added')
          } catch (error) {
            console.error('Failed to load new document:', error)
          }
        }
      })
    )

    // Document status changed
    unsubscribers.push(
      subscribe('document.status_changed', async (_event) => {
        await fetchDocuments({ sortBy: sortField, sortOrder })
      })
    )

    // Document updated
    unsubscribers.push(
      subscribe('document.updated', async (_event) => {
        await fetchDocuments({ sortBy: sortField, sortOrder })
      })
    )

    // Document deleted
    unsubscribers.push(
      subscribe('document.deleted', (_event) => {
        toast.info('Document deleted')
      })
    )

    return () => {
      unsubscribers.forEach(unsub => unsub())
    }
  }, [subscribe, documents, fetchDocuments, sortField, sortOrder])

  const performSearch = useCallback(async () => {
    if (!searchQuery.trim()) {
      setSearchResults([])
      return
    }

    setIsSearching(true)
    try {
      const results = await searchService.advancedSearch(searchQuery, searchMode)
      setSearchResults(results.map(r => r.document))
    } catch (error) {
      toast.error('Search failed')
      console.error('Search error:', error)
    } finally {
      setIsSearching(false)
    }
  }, [searchQuery, searchMode])

  const clearSearch = useCallback(() => {
    setSearchQuery('')
    setSearchResults([])
  }, [])

  const clearTagFilter = useCallback(() => {
    setFilterTagId(null)
    setSelectedTag(null)
    setSearchParams({})
  }, [setSearchParams])

  const clearAllFilters = useCallback(() => {
    setNameFilter('')
    setSelectedTags([])
    clearTagFilter()
  }, [clearTagFilter])

  const handleSort = useCallback((field: string) => {
    if (sortField === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortOrder('desc')
    }
  }, [sortField, sortOrder])

  const handleDelete = useCallback((doc: Document) => {
    setDocumentToDelete(doc)
    setDeleteDialogOpen(true)
  }, [])

  const confirmDelete = useCallback(async () => {
    if (!documentToDelete) return

    try {
      await deleteDocument(documentToDelete.id)
      toast.success('Document deleted')
      setDeleteDialogOpen(false)
      setDocumentToDelete(null)
    } catch (error) {
      toast.error('Failed to delete document')
    }
  }, [documentToDelete, deleteDocument])

  // Selection handlers
  const toggleSelect = useCallback((id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }, [])

  const toggleSelectAll = useCallback(() => {
    if (selectedIds.size === displayedDocuments.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(displayedDocuments.map(d => d.id)))
    }
  }, [selectedIds.size, displayedDocuments])

  const clearSelection = useCallback(() => {
    setSelectedIds(new Set())
  }, [])

  const isAllSelected = displayedDocuments.length > 0 && selectedIds.size === displayedDocuments.length
  const isPartiallySelected = selectedIds.size > 0 && selectedIds.size < displayedDocuments.length

  // Bulk action handlers
  const handleBulkDelete = useCallback(async () => {
    setBulkActionLoading(true)
    try {
      const deletePromises = Array.from(selectedIds).map(id => deleteDocument(id))
      await Promise.all(deletePromises)
      toast.success(`Deleted ${selectedIds.size} document(s)`)
      setSelectedIds(new Set())
      setBulkDeleteDialogOpen(false)
    } catch (error) {
      toast.error('Failed to delete some documents')
    } finally {
      setBulkActionLoading(false)
    }
  }, [selectedIds, deleteDocument])

  const handleBulkReprocess = useCallback(async () => {
    setBulkActionLoading(true)
    try {
      const promises = Array.from(selectedIds).map(id => documentService.reprocess(id))
      await Promise.all(promises)
      toast.success(`Reprocessing ${selectedIds.size} document(s)`)
    } catch (error) {
      toast.error('Failed to reprocess some documents')
    } finally {
      setBulkActionLoading(false)
    }
  }, [selectedIds])

  const handleBulkRegenerateEmbeddings = useCallback(async () => {
    setBulkActionLoading(true)
    try {
      const promises = Array.from(selectedIds).map(id => documentService.regenerateEmbeddings(id))
      await Promise.all(promises)
      toast.success(`Regenerating embeddings for ${selectedIds.size} document(s)`)
    } catch (error) {
      toast.error('Failed to regenerate embeddings for some documents')
    } finally {
      setBulkActionLoading(false)
    }
  }, [selectedIds])

  const handleBulkRegenerateMetadata = useCallback(async () => {
    setBulkActionLoading(true)
    try {
      const promises = Array.from(selectedIds).map(id => documentService.regenerateMetadata(id))
      await Promise.all(promises)
      toast.success(`Regenerating metadata for ${selectedIds.size} document(s)`)
    } catch (error) {
      toast.error('Failed to regenerate metadata for some documents')
    } finally {
      setBulkActionLoading(false)
    }
  }, [selectedIds])

  const getStatusColor = useCallback((status: string) => {
    switch (status) {
      case 'pending':
        return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300'
      case 'processing':
        return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300'
      case 'ocr_complete':
      case 'embedding_complete':
      case 'llm_complete':
        return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300'
      case 'failed':
      case 'ocr_failed':
        return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300'
      default:
        return 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-300'
    }
  }, [])

  const formatStatus = (status: string) => {
    return status
      .replace(/_/g, ' ')
      .replace(/ocr/gi, 'OCR')
      .replace(/llm/gi, 'LLM')
      .toUpperCase()
  }

  if (loading && documents.length === 0) {
    return (
      <div className="flex justify-center p-12">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Documents</h1>
          <p className="text-muted-foreground">Upload and manage your documents</p>
        </div>
        <Button onClick={() => setUploadDialogOpen(true)}>
          <Upload className="mr-2 h-4 w-4" />
          Upload
        </Button>
      </div>

      {/* Statistics */}
      {statistics.totalDocuments > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card>
            <CardContent className="p-4">
              <div className="text-sm text-muted-foreground mb-1">Total Documents</div>
              <div className="text-2xl font-bold">{statistics.totalDocuments.toLocaleString()}</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="text-sm text-muted-foreground mb-1">Total Size</div>
              <div className="text-2xl font-bold">{formatFileSize(statistics.totalFileSize)}</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="text-sm text-muted-foreground mb-1">Total Words</div>
              <div className="text-2xl font-bold">{statistics.totalWords.toLocaleString()}</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="text-sm text-muted-foreground mb-1">Avg. Size</div>
              <div className="text-2xl font-bold">{formatFileSize(statistics.averageFileSize)}</div>
            </CardContent>
          </Card>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Your Documents</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Tag Filter Banner */}
          {selectedTag && (
            <div className="flex items-center justify-between p-3 bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-md">
              <div className="flex items-center gap-2">
                <div
                  className="w-4 h-4 rounded"
                  style={{ backgroundColor: selectedTag.color || '#6366f1' }}
                />
                <span className="font-medium">Filtering by tag: {selectedTag.name}</span>
              </div>
              <Button variant="ghost" size="sm" onClick={clearTagFilter}>
                <X className="h-4 w-4" />
              </Button>
            </div>
          )}

          {/* Filters */}
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowFilters(!showFilters)}
              >
                <Filter className="mr-2 h-4 w-4" />
                {showFilters ? 'Hide Filters' : 'Show Filters'}
                {activeFilterCount > 0 && (
                  <Badge variant="secondary" className="ml-2">
                    {activeFilterCount}
                  </Badge>
                )}
              </Button>
              {activeFilterCount > 0 && (
                <Button variant="ghost" size="sm" onClick={clearAllFilters}>
                  Clear All Filters
                </Button>
              )}
            </div>

            {showFilters && (
              <Card>
                <CardContent className="p-4 space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Filter by Name</Label>
                      <Input
                        placeholder="Search in title or filename..."
                        value={nameFilter}
                        onChange={(e) => setNameFilter(e.target.value)}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Filter by Tags</Label>
                      <div className="flex flex-wrap gap-2">
                        {availableTags.map((tag) => (
                          <Badge
                            key={tag.id}
                            variant={selectedTags.includes(tag.id) ? 'default' : 'outline'}
                            className="cursor-pointer"
                            style={
                              selectedTags.includes(tag.id)
                                ? { backgroundColor: tag.color }
                                : undefined
                            }
                            onClick={() => {
                              setSelectedTags(prev =>
                                prev.includes(tag.id)
                                  ? prev.filter(id => id !== tag.id)
                                  : [...prev, tag.id]
                              )
                            }}
                          >
                            {tag.name}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>

          {/* Search */}
          <div className="space-y-2">
            <div className="flex gap-2">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search documents..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && performSearch()}
                  className="pl-9"
                />
              </div>
              <div className="flex items-center gap-1">
                <Select value={searchMode} onValueChange={(v) => setSearchMode(v as SearchMode)}>
                  <SelectTrigger className="w-48">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="hybrid">Hybrid (Best)</SelectItem>
                    <SelectItem value="semantic">Semantic (Meaning)</SelectItem>
                    <SelectItem value="fulltext">Keyword (Fast)</SelectItem>
                  </SelectContent>
                </Select>
                <Popover>
                  <PopoverTrigger asChild>
                    <button className="p-1 text-muted-foreground hover:text-foreground rounded-md hover:bg-accent transition-colors">
                      <HelpCircle className="h-4 w-4" />
                    </button>
                  </PopoverTrigger>
                  <PopoverContent className="w-80">
                    <div className="space-y-3">
                      <h4 className="font-medium">Search Modes</h4>
                      <div className="space-y-2 text-sm text-muted-foreground">
                        <div>
                          <span className="font-medium text-foreground">Hybrid</span> — Combines keyword and semantic search for best results. Documents matching your exact words AND related concepts are ranked together.
                        </div>
                        <div>
                          <span className="font-medium text-foreground">Semantic</span> — Finds documents by meaning, not just keywords. Great for finding related content even if exact words don't match.
                        </div>
                        <div>
                          <span className="font-medium text-foreground">Keyword</span> — Traditional text search. Fast and precise for finding exact words or phrases.
                        </div>
                      </div>
                    </div>
                  </PopoverContent>
                </Popover>
              </div>
              <Button onClick={performSearch} disabled={isSearching}>
                {isSearching ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
              </Button>
              {searchQuery && (
                <Button variant="outline" onClick={clearSearch}>
                  <X className="h-4 w-4" />
                </Button>
              )}
            </div>
          </div>

          {/* Bulk Action Toolbar */}
          {selectedIds.size > 0 && (
            <div className="flex items-center justify-between p-3 bg-muted rounded-md">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">
                  {selectedIds.size} document{selectedIds.size !== 1 ? 's' : ''} selected
                </span>
                <Button variant="ghost" size="sm" onClick={clearSelection}>
                  Clear
                </Button>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleBulkReprocess}
                  disabled={bulkActionLoading}
                >
                  {bulkActionLoading ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <RotateCcw className="mr-2 h-4 w-4" />
                  )}
                  Reprocess
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleBulkRegenerateEmbeddings}
                  disabled={bulkActionLoading}
                >
                  {bulkActionLoading ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Brain className="mr-2 h-4 w-4" />
                  )}
                  Regenerate Embeddings
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleBulkRegenerateMetadata}
                  disabled={bulkActionLoading}
                >
                  {bulkActionLoading ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Sparkles className="mr-2 h-4 w-4" />
                  )}
                  Regenerate Metadata
                </Button>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => setBulkDeleteDialogOpen(true)}
                  disabled={bulkActionLoading}
                >
                  {bulkActionLoading ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Trash2 className="mr-2 h-4 w-4" />
                  )}
                  Delete
                </Button>
              </div>
            </div>
          )}

          {/* Empty State */}
          {displayedDocuments.length === 0 && !loading && (
            <div className="text-center py-12">
              <FileText className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium mb-2">
                {searchQuery ? 'No results found' : 'No documents yet'}
              </h3>
              <p className="text-muted-foreground mb-4">
                {searchQuery
                  ? `No documents match "${searchQuery}"`
                  : 'Upload your first document to get started'}
              </p>
              {searchQuery && (
                <Button variant="outline" onClick={clearSearch}>
                  Clear Search
                </Button>
              )}
            </div>
          )}

          {/* Table */}
          {displayedDocuments.length > 0 && (
            <div className="border rounded-md">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-12">
                      <Checkbox
                        checked={isPartiallySelected ? 'indeterminate' : isAllSelected}
                        onCheckedChange={toggleSelectAll}
                        aria-label="Select all"
                      />
                    </TableHead>
                    <TableHead
                      className="cursor-pointer select-none"
                      onClick={() => handleSort('title')}
                    >
                      <div className="flex items-center gap-1">
                        Title
                        {sortField === 'title' && (
                          sortOrder === 'asc' ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />
                        )}
                      </div>
                    </TableHead>
                    <TableHead
                      className="cursor-pointer select-none"
                      onClick={() => handleSort('file_size')}
                    >
                      <div className="flex items-center gap-1">
                        Size
                        {sortField === 'file_size' && (
                          sortOrder === 'asc' ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />
                        )}
                      </div>
                    </TableHead>
                    <TableHead
                      className="cursor-pointer select-none"
                      onClick={() => handleSort('processing_status')}
                    >
                      <div className="flex items-center gap-1">
                        Status
                        {sortField === 'processing_status' && (
                          sortOrder === 'asc' ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />
                        )}
                      </div>
                    </TableHead>
                    <TableHead>Tags</TableHead>
                    <TableHead
                      className="cursor-pointer select-none"
                      onClick={() => handleSort('created_at')}
                    >
                      <div className="flex items-center gap-1">
                        Uploaded
                        {sortField === 'created_at' && (
                          sortOrder === 'asc' ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />
                        )}
                      </div>
                    </TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {displayedDocuments.map((doc) => (
                    <TableRow
                      key={doc.id}
                      className={`cursor-pointer ${selectedIds.has(doc.id) ? 'bg-muted/50' : ''}`}
                      onClick={() => navigate(`/documents/${doc.id}`)}
                    >
                      <TableCell onClick={(e) => e.stopPropagation()}>
                        <Checkbox
                          checked={selectedIds.has(doc.id)}
                          onCheckedChange={() => toggleSelect(doc.id)}
                          aria-label={`Select ${doc.title}`}
                        />
                      </TableCell>
                      <TableCell>
                        <div>
                          <div className="font-medium text-primary hover:underline">
                            {doc.title}
                          </div>
                          <div className="text-sm text-muted-foreground">
                            {doc.original_filename}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>{formatFileSize(doc.file_size)}</TableCell>
                      <TableCell>
                        <Badge variant="outline-nowrap" className={getStatusColor(doc.processing_status)}>
                          {formatStatus(doc.processing_status)}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {doc.tags?.map((tag) => (
                            <Badge
                              key={tag.id}
                              style={{ backgroundColor: tag.color }}
                              onClick={(e) => {
                                e.stopPropagation()
                                setSearchParams({ tag: tag.id })
                              }}
                              className="cursor-pointer"
                            >
                              {tag.name}
                            </Badge>
                          ))}
                          {(!doc.tags || doc.tags.length === 0) && (
                            <span className="text-xs text-muted-foreground">No tags</span>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="text-sm">
                        {new Date(doc.created_at).toLocaleDateString()}
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={(e) => {
                            e.stopPropagation()
                            handleDelete(doc)
                          }}
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Document</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{documentToDelete?.title}"? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDelete} className="bg-destructive hover:bg-destructive/90">
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Bulk Delete Confirmation Dialog */}
      <AlertDialog open={bulkDeleteDialogOpen} onOpenChange={setBulkDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {selectedIds.size} Document{selectedIds.size !== 1 ? 's' : ''}</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete {selectedIds.size} document{selectedIds.size !== 1 ? 's' : ''}? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={bulkActionLoading}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleBulkDelete}
              className="bg-destructive hover:bg-destructive/90"
              disabled={bulkActionLoading}
            >
              {bulkActionLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Deleting...
                </>
              ) : (
                'Delete'
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Upload Dialog */}
      <UploadDialog
        open={uploadDialogOpen}
        onOpenChange={setUploadDialogOpen}
        onUploadComplete={fetchDocuments}
      />
    </div >
  )
}
