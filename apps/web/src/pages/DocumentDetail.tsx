import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useDocumentDetail, useWebSocket, useAuthStore } from '@cartulary/shared'
import { documentService, tagService, websocketService } from '../services'
import type { Tag } from '@cartulary/shared'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
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
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu'
import {
  ArrowLeft,
  Download,
  Trash2,
  Pencil,
  Check,
  X,
  Tag as TagIcon,
  RefreshCw,
  Sparkles,
  Wand2,
  Share2,
  Loader2,
  MoreVertical,
} from 'lucide-react'
import { toast } from 'sonner'
import api from '../services/api'

export default function DocumentDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated())
  const { subscribe } = useWebSocket(websocketService, isAuthenticated)

  const {
    document,
    loading,
    updateDocument,
    addTags,
    removeTag,
    reprocess,
    regenerateEmbeddings,
    regenerateMetadata,
    downloadFile,
  } = useDocumentDetail(documentService, tagService, id || '')

  // Editing states
  const [editingTitle, setEditingTitle] = useState(false)
  const [titleEdit, setTitleEdit] = useState('')
  const [editingDescription, setEditingDescription] = useState(false)
  const [descriptionEdit, setDescriptionEdit] = useState('')

  // Tag management
  const [availableTags, setAvailableTags] = useState<Tag[]>([])
  const [selectedTags, setSelectedTags] = useState<string[]>([])
  const [showTagDialog, setShowTagDialog] = useState(false)

  // Confirmation dialogs
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [reprocessDialogOpen, setReprocessDialogOpen] = useState(false)
  const [embeddingsDialogOpen, setEmbeddingsDialogOpen] = useState(false)
  const [metadataDialogOpen, setMetadataDialogOpen] = useState(false)

  // PDF blob for viewing
  const [pdfBlobUrl, setPdfBlobUrl] = useState<string>('')

  // Load PDF blob for authenticated viewing
  useEffect(() => {
    const loadPdfBlob = async () => {
      if (!document || document.file_extension !== 'pdf') return

      try {
        const response = await api.get(`/api/v1/documents/${document.id}/download`, {
          responseType: 'blob',
        })
        const url = window.URL.createObjectURL(new Blob([response.data]))
        setPdfBlobUrl(url)
      } catch (error) {
        console.error('Failed to load PDF:', error)
      }
    }

    loadPdfBlob()

    return () => {
      if (pdfBlobUrl) {
        window.URL.revokeObjectURL(pdfBlobUrl)
      }
    }
  }, [document])

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

  // Sync tag selection with document
  useEffect(() => {
    if (document?.tags) {
      setSelectedTags(document.tags.map(t => t.id))
    }
  }, [document])

  // Initialize edit values
  useEffect(() => {
    if (document) {
      setTitleEdit(document.title)
      setDescriptionEdit(document.description || '')
    }
  }, [document])

  // WebSocket subscriptions
  useEffect(() => {
    if (!document) return

    const unsubscribers: (() => void)[] = []

    // Status changes
    unsubscribers.push(
      subscribe('document.status_changed', (event) => {
        if (event.data.document_id === document.id) {
          // Will be handled by the hook's auto-refresh
        }
      })
    )

    // Document updates
    unsubscribers.push(
      subscribe('document.updated', (event) => {
        if (event.data.document_id === document.id) {
          // Will be handled by the hook's auto-refresh
        }
      })
    )

    return () => {
      unsubscribers.forEach(unsub => unsub())
    }
  }, [subscribe, document])

  const handleSaveTitle = async () => {
    try {
      await updateDocument({ title: titleEdit })
      setEditingTitle(false)
      toast.success('Title updated')
    } catch (error) {
      toast.error('Failed to update title')
    }
  }

  const handleSaveDescription = async () => {
    try {
      await updateDocument({ description: descriptionEdit })
      setEditingDescription(false)
      toast.success('Description updated')
    } catch (error) {
      toast.error('Failed to update description')
    }
  }

  const handleSaveTags = async () => {
    try {
      await addTags(selectedTags)
      setShowTagDialog(false)
      toast.success('Tags updated')
    } catch (error) {
      toast.error('Failed to update tags')
    }
  }

  const handleRemoveTag = async (tag: Tag) => {
    try {
      await removeTag(tag.id)
      toast.success('Tag removed')
    } catch (error) {
      toast.error('Failed to remove tag')
    }
  }

  const handleDownload = async () => {
    if (!document) return
    try {
      await downloadFile(document.original_filename)
      toast.success('Download started')
    } catch (error) {
      toast.error('Failed to download document')
    }
  }

  const handleDelete = async () => {
    if (!document) return
    try {
      await documentService.delete(document.id)
      toast.success('Document deleted')
      navigate('/')
    } catch (error) {
      toast.error('Failed to delete document')
    }
  }

  const handleReprocess = async () => {
    try {
      await reprocess()
      setReprocessDialogOpen(false)
      toast.success('Reprocessing started')
    } catch (error) {
      toast.error('Failed to reprocess document')
    }
  }

  const handleRegenerateEmbeddings = async () => {
    try {
      await regenerateEmbeddings()
      setEmbeddingsDialogOpen(false)
      toast.success('Embedding generation started')
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to regenerate embeddings')
    }
  }

  const handleRegenerateMetadata = async () => {
    try {
      await regenerateMetadata()
      setMetadataDialogOpen(false)
      toast.success('Metadata extraction started')
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to regenerate metadata')
    }
  }

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  const getStatusColor = (status: string) => {
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
  }

  const formatStatus = (status: string) => {
    return status
      .replace(/_/g, ' ')
      .replace(/ocr/gi, 'OCR')
      .replace(/llm/gi, 'LLM')
      .toUpperCase()
  }

  if (loading) {
    return (
      <div className="flex justify-center p-12">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  if (!document) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" onClick={() => navigate('/')}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back
        </Button>
        <Card className="p-8 text-center">
          <p className="text-muted-foreground">Document not found</p>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 space-y-4">
          <Button variant="ghost" onClick={() => navigate('/')}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Documents
          </Button>

          {/* Title */}
          {!editingTitle ? (
            <div className="flex items-center gap-2">
              <h1 className="text-3xl font-bold">{document.title}</h1>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setEditingTitle(true)}
              >
                <Pencil className="h-4 w-4" />
              </Button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <Input
                value={titleEdit}
                onChange={(e) => setTitleEdit(e.target.value)}
                className="text-2xl font-bold flex-1"
              />
              <Button size="icon" onClick={handleSaveTitle}>
                <Check className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="icon"
                onClick={() => {
                  setEditingTitle(false)
                  setTitleEdit(document.title)
                }}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          )}

          <p className="text-muted-foreground">{document.original_filename}</p>

          {/* Description */}
          {!editingDescription ? (
            <div className="flex items-start gap-2">
              <div className="flex-1">
                {document.description ? (
                  <p className="text-foreground">{document.description}</p>
                ) : (
                  <p className="text-muted-foreground italic">No description</p>
                )}
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setEditingDescription(true)}
              >
                <Pencil className="h-4 w-4" />
              </Button>
            </div>
          ) : (
            <div className="space-y-2">
              <Textarea
                value={descriptionEdit}
                onChange={(e) => setDescriptionEdit(e.target.value)}
                rows={3}
                placeholder="Add a description..."
              />
              <div className="flex gap-2">
                <Button size="sm" onClick={handleSaveDescription}>
                  <Check className="mr-2 h-4 w-4" />
                  Save
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setEditingDescription(false)
                    setDescriptionEdit(document.description || '')
                  }}
                >
                  <X className="mr-2 h-4 w-4" />
                  Cancel
                </Button>
              </div>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={handleDownload}>
            <Download className="mr-2 h-4 w-4" />
            Download
          </Button>
          <Button variant="outline" onClick={() => toast.info('Share coming soon')}>
            <Share2 className="mr-2 h-4 w-4" />
            Share
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="icon">
                <MoreVertical className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => setReprocessDialogOpen(true)}>
                <RefreshCw className="mr-2 h-4 w-4" />
                Reprocess OCR
              </DropdownMenuItem>
              {document.ocr_text && (
                <>
                  <DropdownMenuItem onClick={() => setEmbeddingsDialogOpen(true)}>
                    <Sparkles className="mr-2 h-4 w-4" />
                    Regenerate Embeddings
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => setMetadataDialogOpen(true)}>
                    <Wand2 className="mr-2 h-4 w-4" />
                    Regenerate Metadata
                  </DropdownMenuItem>
                </>
              )}
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onClick={() => setDeleteDialogOpen(true)}
                className="text-destructive focus:text-destructive"
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {/* Document Information */}
      <Card>
        <CardHeader>
          <CardTitle>Document Information</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-sm text-muted-foreground">File Size</p>
              <p className="font-medium">{formatFileSize(document.file_size)}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">File Type</p>
              <p className="font-medium">{document.file_extension.toUpperCase()}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Uploaded</p>
              <p className="font-medium">
                {new Date(document.created_at).toLocaleString()}
              </p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Status</p>
              <Badge variant="outline" className={getStatusColor(document.processing_status)}>
                {formatStatus(document.processing_status)}
              </Badge>
            </div>
          </div>

          {/* Tags */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm text-muted-foreground">Tags</p>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowTagDialog(true)}
              >
                <TagIcon className="mr-2 h-4 w-4" />
                Edit Tags
              </Button>
            </div>
            <div className="flex flex-wrap gap-2">
              {document.tags?.map((tag) => (
                <Badge
                  key={tag.id}
                  style={{ backgroundColor: tag.color }}
                  className="cursor-pointer"
                  onClick={() => handleRemoveTag(tag)}
                >
                  {tag.name}
                  <X className="ml-1 h-3 w-3" />
                </Badge>
              ))}
              {(!document.tags || document.tags.length === 0) && (
                <span className="text-sm text-muted-foreground">No tags</span>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* AI-Extracted Metadata */}
      {(document.extracted_title ||
        document.extracted_correspondent ||
        document.extracted_date ||
        document.extracted_document_type ||
        document.extracted_summary) && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-purple-500" />
              AI-Extracted Metadata
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {document.extracted_title && (
              <div>
                <p className="text-sm text-muted-foreground">Extracted Title</p>
                <p className="font-medium">{document.extracted_title}</p>
              </div>
            )}
            {document.extracted_correspondent && (
              <div>
                <p className="text-sm text-muted-foreground">Correspondent</p>
                <p className="font-medium">{document.extracted_correspondent}</p>
              </div>
            )}
            {document.extracted_date && (
              <div>
                <p className="text-sm text-muted-foreground">Document Date</p>
                <p className="font-medium">
                  {new Date(document.extracted_date).toLocaleDateString()}
                </p>
              </div>
            )}
            {document.extracted_document_type && (
              <div>
                <p className="text-sm text-muted-foreground">Document Type</p>
                <p className="font-medium capitalize">
                  {document.extracted_document_type}
                </p>
              </div>
            )}
            {document.extracted_summary && (
              <div>
                <p className="text-sm text-muted-foreground">Summary</p>
                <p className="leading-relaxed">{document.extracted_summary}</p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* PDF Viewer */}
      {document.file_extension === 'pdf' && pdfBlobUrl && (
        <Card>
          <CardHeader>
            <CardTitle>Document Preview</CardTitle>
          </CardHeader>
          <CardContent>
            <iframe
              src={pdfBlobUrl + '#view=FitH'}
              className="w-full h-[600px] border rounded"
              title="PDF Preview"
            />
          </CardContent>
        </Card>
      )}

      {/* OCR Text */}
      {document.ocr_text && (
        <Card>
          <CardHeader>
            <CardTitle>Extracted Text</CardTitle>
          </CardHeader>
          <CardContent>
            <Textarea
              value={document.ocr_text}
              readOnly
              rows={15}
              className="font-mono text-sm"
            />
          </CardContent>
        </Card>
      )}

      {/* Tag Dialog */}
      <Dialog open={showTagDialog} onOpenChange={setShowTagDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Manage Tags</DialogTitle>
            <DialogDescription>
              Select tags for this document
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            {availableTags.map((tag) => (
              <Badge
                key={tag.id}
                variant={selectedTags.includes(tag.id) ? 'default' : 'outline'}
                className="cursor-pointer mr-2"
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
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowTagDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleSaveTags}>Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Document</AlertDialogTitle>
            <AlertDialogDescription>
              Delete "{document.title}"? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} className="bg-destructive hover:bg-destructive/90">
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Reprocess Confirmation */}
      <AlertDialog open={reprocessDialogOpen} onOpenChange={setReprocessDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Reprocess Document</AlertDialogTitle>
            <AlertDialogDescription>
              Reprocess this document? This will retry OCR text extraction.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleReprocess}>Reprocess</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Regenerate Embeddings Confirmation */}
      <AlertDialog open={embeddingsDialogOpen} onOpenChange={setEmbeddingsDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Regenerate Embeddings</AlertDialogTitle>
            <AlertDialogDescription>
              Regenerate embeddings for this document? This will create new vector embeddings from the extracted text.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleRegenerateEmbeddings}>Regenerate</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Regenerate Metadata Confirmation */}
      <AlertDialog open={metadataDialogOpen} onOpenChange={setMetadataDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Regenerate AI Metadata</AlertDialogTitle>
            <AlertDialogDescription>
              Regenerate AI metadata for this document? This will extract title, correspondent, date, type, summary, and auto-generate tags.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleRegenerateMetadata}>Regenerate</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
