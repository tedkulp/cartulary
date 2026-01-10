import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { sharingService } from '../services'
import type { SharedDocument } from '@cartulary/shared'
import { toast } from 'sonner'
import { Eye, Loader2, Inbox } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

export default function SharedDocuments() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  // Pagination state from URL
  const currentPage = parseInt(searchParams.get('page') || '1', 10)
  const [rowsPerPage, setRowsPerPage] = useState(20)

  // State
  const [sharedDocuments, setSharedDocuments] = useState<SharedDocument[]>([])
  const [loading, setLoading] = useState(true)

  // Load shared documents
  const loadSharedDocuments = async () => {
    setLoading(true)
    try {
      const documents = await sharingService.listSharedWithMe()
      setSharedDocuments(documents)
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to load shared documents')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadSharedDocuments()
  }, [])

  // Pagination
  const totalPages = Math.ceil(sharedDocuments.length / rowsPerPage)
  const startIndex = (currentPage - 1) * rowsPerPage
  const endIndex = startIndex + rowsPerPage
  const paginatedDocuments = sharedDocuments.slice(startIndex, endIndex)

  const handlePageChange = (newPage: number) => {
    setSearchParams({ page: newPage.toString() })
  }

  const handleRowsPerPageChange = (value: string) => {
    setRowsPerPage(parseInt(value, 10))
    setSearchParams({ page: '1' })
  }

  const viewDocument = (doc: SharedDocument) => {
    if (doc.document?.id) {
      navigate(`/documents/${doc.document.id}`)
    }
  }

  const getPermissionVariant = (
    level: string
  ): 'default' | 'secondary' | 'destructive' | 'outline' => {
    switch (level) {
      case 'admin':
        return 'destructive'
      case 'write':
        return 'default'
      case 'read':
        return 'secondary'
      default:
        return 'outline'
    }
  }

  const getStatusBadge = (status?: string) => {
    if (!status) return null

    switch (status) {
      case 'llm_complete':
      case 'complete':
        return (
          <Badge variant="default" className="bg-green-600">
            Ready
          </Badge>
        )
      case 'processing':
        return <Badge variant="secondary">Processing</Badge>
      case 'failed':
        return <Badge variant="destructive">Failed</Badge>
      default:
        return <Badge variant="outline">{status}</Badge>
    }
  }

  return (
    <div className="container mx-auto py-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Shared with Me</h1>
        <p className="text-muted-foreground">Documents that other users have shared with you</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Shared Documents</CardTitle>
          <CardDescription>
            {sharedDocuments.length} {sharedDocuments.length === 1 ? 'document' : 'documents'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : sharedDocuments.length === 0 ? (
            <div className="text-center py-8">
              <Inbox className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <p className="text-muted-foreground">No documents have been shared with you yet.</p>
            </div>
          ) : (
            <>
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Title</TableHead>
                      <TableHead>Permission</TableHead>
                      <TableHead>Shared On</TableHead>
                      <TableHead>Expires</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {paginatedDocuments.map((sharedDoc) => (
                      <TableRow key={sharedDoc.share.id}>
                        <TableCell>
                          {sharedDoc.document ? (
                            <div>
                              <div className="font-semibold">{sharedDoc.document.title}</div>
                              <div className="text-sm text-muted-foreground">
                                {sharedDoc.document.original_filename}
                              </div>
                            </div>
                          ) : (
                            <span className="text-muted-foreground">-</span>
                          )}
                        </TableCell>
                        <TableCell>
                          {sharedDoc.share ? (
                            <Badge variant={getPermissionVariant(sharedDoc.share.permission_level)}>
                              {sharedDoc.share.permission_level.toUpperCase()}
                            </Badge>
                          ) : (
                            <span className="text-muted-foreground">-</span>
                          )}
                        </TableCell>
                        <TableCell>
                          {sharedDoc.share
                            ? new Date(sharedDoc.share.created_at).toLocaleDateString()
                            : '-'}
                        </TableCell>
                        <TableCell>
                          {sharedDoc.share?.expires_at ? (
                            new Date(sharedDoc.share.expires_at).toLocaleDateString()
                          ) : (
                            <span className="text-muted-foreground">Never</span>
                          )}
                        </TableCell>
                        <TableCell>
                          {getStatusBadge(sharedDoc.document?.processing_status)}
                        </TableCell>
                        <TableCell>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => viewDocument(sharedDoc)}
                          >
                            <Eye className="mr-2 h-4 w-4" />
                            View
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              {/* Pagination Controls */}
              <div className="flex items-center justify-between mt-4">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-muted-foreground">Rows per page:</span>
                  <Select value={rowsPerPage.toString()} onValueChange={handleRowsPerPageChange}>
                    <SelectTrigger className="w-20">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="10">10</SelectItem>
                      <SelectItem value="20">20</SelectItem>
                      <SelectItem value="50">50</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="flex items-center gap-2">
                  <span className="text-sm text-muted-foreground">
                    Showing {startIndex + 1} to {Math.min(endIndex, sharedDocuments.length)} of{' '}
                    {sharedDocuments.length}
                  </span>
                  <div className="flex gap-1">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handlePageChange(currentPage - 1)}
                      disabled={currentPage === 1}
                    >
                      Previous
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handlePageChange(currentPage + 1)}
                      disabled={currentPage >= totalPages}
                    >
                      Next
                    </Button>
                  </div>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
