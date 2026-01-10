import { useState, useEffect } from 'react'
import { importSourceService } from '../services'
import type {
  ImportSource,
  ImportSourceCreate,
  ImportSourceType,
  ImportSourceStatus,
} from '@cartulary/shared'
import { toast } from 'sonner'
import { Folder, Mail, Plus, Pencil, Trash2, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

// Enum values from shared package
const ImportSourceTypeEnum = {
  DIRECTORY: 'directory' as ImportSourceType,
  IMAP: 'imap' as ImportSourceType,
}

const ImportSourceStatusEnum = {
  ACTIVE: 'active' as ImportSourceStatus,
  PAUSED: 'paused' as ImportSourceStatus,
  ERROR: 'error' as ImportSourceStatus,
}

export default function SettingsPage() {
  // State
  const [importSources, setImportSources] = useState<ImportSource[]>([])
  const [loading, setLoading] = useState(true)
  const [showDialog, setShowDialog] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [sourceToDelete, setSourceToDelete] = useState<ImportSource | null>(null)
  const [editingSource, setEditingSource] = useState<ImportSource | null>(null)

  // Form state
  const [formData, setFormData] = useState<ImportSourceCreate>({
    name: '',
    source_type: ImportSourceTypeEnum.DIRECTORY,
    status: ImportSourceStatusEnum.ACTIVE,
    watch_path: null,
    move_after_import: false,
    move_to_path: null,
    delete_after_import: false,
    imap_server: null,
    imap_port: null,
    imap_username: null,
    imap_password: null,
    imap_use_ssl: true,
    imap_mailbox: 'INBOX',
    imap_processed_folder: null,
  })

  // Load import sources
  const loadImportSources = async () => {
    setLoading(true)
    try {
      const sources = await importSourceService.list()
      setImportSources(sources)
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to load import sources')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadImportSources()
  }, [])

  // Dialog handlers
  const openCreateDialog = () => {
    setEditingSource(null)
    setFormData({
      name: '',
      source_type: ImportSourceTypeEnum.DIRECTORY,
      status: ImportSourceStatusEnum.ACTIVE,
      watch_path: null,
      move_after_import: false,
      move_to_path: null,
      delete_after_import: false,
      imap_server: null,
      imap_port: null,
      imap_username: null,
      imap_password: null,
      imap_use_ssl: true,
      imap_mailbox: 'INBOX',
      imap_processed_folder: null,
    })
    setShowDialog(true)
  }

  const openEditDialog = (source: ImportSource) => {
    setEditingSource(source)
    setFormData({
      name: source.name,
      source_type: source.source_type,
      status: source.status,
      watch_path: source.watch_path,
      move_after_import: source.move_after_import,
      move_to_path: source.move_to_path,
      delete_after_import: source.delete_after_import,
      imap_server: source.imap_server,
      imap_port: source.imap_port,
      imap_username: source.imap_username,
      imap_password: null, // Don't populate password for security
      imap_use_ssl: source.imap_use_ssl,
      imap_mailbox: source.imap_mailbox || 'INBOX',
      imap_processed_folder: source.imap_processed_folder,
    })
    setShowDialog(true)
  }

  const saveImportSource = async () => {
    try {
      if (editingSource) {
        await importSourceService.update(editingSource.id, formData)
        toast.success('Import source updated successfully')
      } else {
        await importSourceService.create(formData)
        toast.success('Import source created successfully')
      }
      setShowDialog(false)
      await loadImportSources()
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to save import source')
    }
  }

  const handleDeleteClick = (source: ImportSource) => {
    setSourceToDelete(source)
    setDeleteDialogOpen(true)
  }

  const deleteImportSource = async () => {
    if (!sourceToDelete) return

    try {
      await importSourceService.delete(sourceToDelete.id)
      toast.success('Import source deleted successfully')
      setDeleteDialogOpen(false)
      setSourceToDelete(null)
      await loadImportSources()
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to delete import source')
    }
  }

  const getStatusVariant = (status: ImportSourceStatus): 'default' | 'secondary' | 'destructive' => {
    switch (status) {
      case ImportSourceStatusEnum.ACTIVE:
        return 'default'
      case ImportSourceStatusEnum.PAUSED:
        return 'secondary'
      case ImportSourceStatusEnum.ERROR:
        return 'destructive'
      default:
        return 'secondary'
    }
  }

  return (
    <div className="container mx-auto py-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Settings</h1>
        <p className="text-muted-foreground">Configure import sources and application settings</p>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Import Sources</CardTitle>
              <CardDescription>
                Automatically import documents from directories or email
              </CardDescription>
            </div>
            <Button onClick={openCreateDialog}>
              <Plus className="mr-2 h-4 w-4" />
              Add Import Source
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : importSources.length === 0 ? (
            <div className="text-center py-8">
              <Folder className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <p className="text-muted-foreground mb-4">
                No import sources configured. Add your first import source to automatically import
                documents.
              </p>
              <Button onClick={openCreateDialog}>
                <Plus className="mr-2 h-4 w-4" />
                Add Import Source
              </Button>
            </div>
          ) : (
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Path/Server</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Last Run</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {importSources.map((source) => (
                    <TableRow key={source.id}>
                      <TableCell className="font-semibold">{source.name}</TableCell>
                      <TableCell>
                        <Badge variant={source.source_type === ImportSourceTypeEnum.DIRECTORY ? 'secondary' : 'default'}>
                          {source.source_type === ImportSourceTypeEnum.DIRECTORY ? (
                            <>
                              <Folder className="mr-1 h-3 w-3" />
                              Directory
                            </>
                          ) : (
                            <>
                              <Mail className="mr-1 h-3 w-3" />
                              IMAP Email
                            </>
                          )}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {source.source_type === ImportSourceTypeEnum.DIRECTORY
                          ? source.watch_path || '-'
                          : source.imap_server || '-'}
                      </TableCell>
                      <TableCell>
                        <Badge variant={getStatusVariant(source.status)}>
                          {source.status}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {source.last_run
                          ? new Date(source.last_run).toLocaleString()
                          : <span className="text-muted-foreground">Never</span>}
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-2">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => openEditDialog(source)}
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleDeleteClick(source)}
                          >
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Create/Edit Dialog */}
      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {editingSource ? 'Edit Import Source' : 'Create Import Source'}
            </DialogTitle>
            <DialogDescription>
              Configure an automated import source for documents
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            {/* Name */}
            <div>
              <Label htmlFor="name">Name</Label>
              <Input
                id="name"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="My Import Source"
              />
            </div>

            {/* Source Type */}
            <div>
              <Label htmlFor="source_type">Source Type</Label>
              <Select
                value={formData.source_type}
                onValueChange={(value) =>
                  setFormData({ ...formData, source_type: value as ImportSourceType })
                }
                disabled={!!editingSource}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ImportSourceTypeEnum.DIRECTORY}>Directory</SelectItem>
                  <SelectItem value={ImportSourceTypeEnum.IMAP}>IMAP Email</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Status */}
            <div>
              <Label htmlFor="status">Status</Label>
              <Select
                value={formData.status}
                onValueChange={(value) =>
                  setFormData({ ...formData, status: value as ImportSourceStatus })
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ImportSourceStatusEnum.ACTIVE}>Active</SelectItem>
                  <SelectItem value={ImportSourceStatusEnum.PAUSED}>Paused</SelectItem>
                  <SelectItem value={ImportSourceStatusEnum.ERROR}>Error</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Directory Fields */}
            {formData.source_type === ImportSourceTypeEnum.DIRECTORY && (
              <>
                <div>
                  <Label htmlFor="watch_path">Watch Path</Label>
                  <Input
                    id="watch_path"
                    value={formData.watch_path || ''}
                    onChange={(e) => setFormData({ ...formData, watch_path: e.target.value })}
                    placeholder="/path/to/watch"
                  />
                </div>

                <div className="flex items-center gap-2">
                  <Checkbox
                    id="move_after_import"
                    checked={formData.move_after_import}
                    onCheckedChange={(checked) =>
                      setFormData({ ...formData, move_after_import: checked as boolean })
                    }
                  />
                  <Label htmlFor="move_after_import" className="cursor-pointer">
                    Move files after import
                  </Label>
                </div>

                {formData.move_after_import && (
                  <div>
                    <Label htmlFor="move_to_path">Move To Path</Label>
                    <Input
                      id="move_to_path"
                      value={formData.move_to_path || ''}
                      onChange={(e) => setFormData({ ...formData, move_to_path: e.target.value })}
                      placeholder="/path/to/move"
                    />
                  </div>
                )}

                <div className="flex items-center gap-2">
                  <Checkbox
                    id="delete_after_import"
                    checked={formData.delete_after_import}
                    onCheckedChange={(checked) =>
                      setFormData({ ...formData, delete_after_import: checked as boolean })
                    }
                  />
                  <Label htmlFor="delete_after_import" className="cursor-pointer">
                    Delete files after import
                  </Label>
                </div>
              </>
            )}

            {/* IMAP Fields */}
            {formData.source_type === ImportSourceTypeEnum.IMAP && (
              <>
                <div>
                  <Label htmlFor="imap_server">IMAP Server</Label>
                  <Input
                    id="imap_server"
                    value={formData.imap_server || ''}
                    onChange={(e) => setFormData({ ...formData, imap_server: e.target.value })}
                    placeholder="imap.gmail.com"
                  />
                </div>

                <div>
                  <Label htmlFor="imap_port">IMAP Port</Label>
                  <Input
                    id="imap_port"
                    type="number"
                    value={formData.imap_port?.toString() || ''}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        imap_port: e.target.value ? parseInt(e.target.value, 10) : null,
                      })
                    }
                    placeholder="993"
                  />
                </div>

                <div>
                  <Label htmlFor="imap_username">Username</Label>
                  <Input
                    id="imap_username"
                    value={formData.imap_username || ''}
                    onChange={(e) => setFormData({ ...formData, imap_username: e.target.value })}
                    placeholder="user@example.com"
                  />
                </div>

                <div>
                  <Label htmlFor="imap_password">Password</Label>
                  <Input
                    id="imap_password"
                    type="password"
                    value={formData.imap_password || ''}
                    onChange={(e) => setFormData({ ...formData, imap_password: e.target.value })}
                    placeholder={
                      editingSource ? 'Leave blank to keep current password' : 'Password'
                    }
                  />
                </div>

                <div className="flex items-center gap-2">
                  <Checkbox
                    id="imap_use_ssl"
                    checked={formData.imap_use_ssl}
                    onCheckedChange={(checked) =>
                      setFormData({ ...formData, imap_use_ssl: checked as boolean })
                    }
                  />
                  <Label htmlFor="imap_use_ssl" className="cursor-pointer">
                    Use SSL
                  </Label>
                </div>

                <div>
                  <Label htmlFor="imap_mailbox">Mailbox</Label>
                  <Input
                    id="imap_mailbox"
                    value={formData.imap_mailbox || ''}
                    onChange={(e) => setFormData({ ...formData, imap_mailbox: e.target.value })}
                    placeholder="INBOX"
                  />
                </div>

                <div>
                  <Label htmlFor="imap_processed_folder">Processed Folder (optional)</Label>
                  <Input
                    id="imap_processed_folder"
                    value={formData.imap_processed_folder || ''}
                    onChange={(e) =>
                      setFormData({ ...formData, imap_processed_folder: e.target.value })
                    }
                    placeholder="Processed"
                  />
                </div>
              </>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDialog(false)}>
              Cancel
            </Button>
            <Button onClick={saveImportSource} disabled={!formData.name}>
              {editingSource ? 'Update' : 'Create'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirm Delete</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{sourceToDelete?.name}"? This action cannot be
              undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setSourceToDelete(null)}>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={deleteImportSource}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
