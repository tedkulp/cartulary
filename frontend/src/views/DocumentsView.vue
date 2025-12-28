<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'
import { useRouter } from 'vue-router'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Card from 'primevue/card'
import InputText from 'primevue/inputtext'
import IconField from 'primevue/iconfield'
import InputIcon from 'primevue/inputicon'
import Select from 'primevue/select'
import ConfirmDialog from 'primevue/confirmdialog'
import { useConfirm } from 'primevue/useconfirm'
import { useToast } from 'primevue/usetoast'
import AppHeader from '@/components/AppHeader.vue'
import DocumentUpload from '@/components/DocumentUpload.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import EmptyState from '@/components/EmptyState.vue'
import ErrorBoundary from '@/components/ErrorBoundary.vue'
import RecentDocumentsWidget from '@/components/RecentDocumentsWidget.vue'
import ActivityLogWidget from '@/components/ActivityLogWidget.vue'
import { documentService } from '@/services/documentService'
import { searchService, type SearchMode } from '@/services/searchService'
import type { Document } from '@/types/document'
import { highlightText } from '@/utils/textHighlight'
import { formatDateTime } from '@/utils/dateFormat'
import { useWebSocket } from '@/composables/useWebSocket'

const router = useRouter()
const confirm = useConfirm()
const toast = useToast()
const { subscribe } = useWebSocket()

const documents = ref<Document[]>([])
const loading = ref(false)
const initialLoading = ref(true)
const error = ref<string | null>(null)
const searchQuery = ref('')
const searchMode = ref<SearchMode>('hybrid')
const searchModes = [
  { label: 'Hybrid (Best)', value: 'hybrid' },
  { label: 'Semantic (Meaning)', value: 'semantic' },
  { label: 'Keyword (Fast)', value: 'fulltext' },
]

// Sorting state
const sortField = ref<string>('created_at')
const sortOrder = ref<number>(-1) // -1 for descending, 1 for ascending

const hasDocuments = computed(() => documents.value.length > 0)
const isSearching = computed(() => searchQuery.value.trim().length > 0)

// Document statistics
const totalDocuments = computed(() => documents.value.length)

const totalFileSize = computed(() => {
  const bytes = documents.value.reduce((sum, doc) => sum + (doc.file_size || 0), 0)
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
})

const totalWords = computed(() => {
  return documents.value.reduce((sum, doc) => {
    if (doc.ocr_text) {
      // Count words by splitting on whitespace
      const words = doc.ocr_text.trim().split(/\s+/).filter(w => w.length > 0)
      return sum + words.length
    }
    return sum
  }, 0)
})

const averageFileSize = computed(() => {
  if (documents.value.length === 0) return '0 B'
  const avgBytes = documents.value.reduce((sum, doc) => sum + (doc.file_size || 0), 0) / documents.value.length
  if (avgBytes < 1024) return `${avgBytes.toFixed(0)} B`
  if (avgBytes < 1024 * 1024) return `${(avgBytes / 1024).toFixed(1)} KB`
  return `${(avgBytes / (1024 * 1024)).toFixed(1)} MB`
})

const loadDocuments = async () => {
  loading.value = true
  error.value = null
  try {
    // Convert PrimeVue sort order (-1/1) to backend format (desc/asc)
    const sortOrderStr = sortOrder.value === -1 ? 'desc' : 'asc'
    documents.value = await documentService.list(0, 1000, sortField.value, sortOrderStr)
  } catch (err: any) {
    error.value = err.response?.data?.detail || 'Failed to load documents'
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: error.value,
      life: 3000,
    })
  } finally {
    loading.value = false
    initialLoading.value = false
  }
}

const performSearch = async () => {
  if (!searchQuery.value.trim()) {
    loadDocuments()
    return
  }

  loading.value = true
  try {
    const results = await searchService.advancedSearch(
      searchQuery.value,
      searchMode.value
    )
    documents.value = results.map((r) => r.document)
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to search documents',
      life: 3000,
    })
  } finally {
    loading.value = false
  }
}

const clearSearch = () => {
  searchQuery.value = ''
  loadDocuments()
}

const handleDocumentUploaded = (document: Document) => {
  documents.value.unshift(document)
}

const handleBatchUploadComplete = (results: { successful: Document[], failed: Array<{ filename: string, error: string }> }) => {
  const { successful, failed } = results

  // Add successful documents to the list
  if (successful.length > 0) {
    toast.add({
      severity: 'success',
      summary: 'Upload Complete',
      detail: `${successful.length} file${successful.length !== 1 ? 's' : ''} uploaded successfully`,
      life: 5000,
    })

    // Refresh document list to get all new documents
    loadDocuments()
  }

  // Show errors for failed uploads
  if (failed.length > 0) {
    failed.forEach(({ filename, error }) => {
      toast.add({
        severity: 'warn',
        summary: `Failed: ${filename}`,
        detail: error,
        life: 5000,
      })
    })
  }
}

const handleDelete = (document: Document) => {
  confirm.require({
    message: `Are you sure you want to delete "${document.title}"?`,
    header: 'Confirm Delete',
    icon: 'pi pi-exclamation-triangle',
    accept: async () => {
      try {
        await documentService.delete(document.id)
        documents.value = documents.value.filter((d) => d.id !== document.id)
        toast.add({
          severity: 'success',
          summary: 'Success',
          detail: 'Document deleted',
          life: 3000,
        })
      } catch (error: any) {
        toast.add({
          severity: 'error',
          summary: 'Error',
          detail: 'Failed to delete document',
          life: 3000,
        })
      }
    },
  })
}

const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

const formatDate = (dateString: string): string => {
  return formatDateTime(dateString)
}

// Sorting functions
const onSort = (event: any) => {
  sortField.value = event.sortField
  sortOrder.value = event.sortOrder
  // Reload documents with new sort order
  loadDocuments()
}

const insertDocumentSorted = (_document: Document) => {
  // Add the new document and reload to get proper sort order from backend
  loadDocuments()
}

// WebSocket event handlers
const unsubscribers: (() => void)[] = []

onMounted(() => {
  loadDocuments()

  // Subscribe to document events
  unsubscribers.push(
    subscribe('document.created', async (event) => {
      // Check if document already exists in the list
      const exists = documents.value.some((d) => d.id === event.data.document_id)
      if (exists) {
        console.log('[DocumentsView] Document already in list, skipping:', event.data.document_id)
        return
      }

      // Reload to get full document data
      try {
        const newDoc = await documentService.get(event.data.document_id)
        insertDocumentSorted(newDoc)
      } catch (error) {
        console.error('Failed to load new document:', error)
      }
    })
  )

  // Subscribe to status changes
  unsubscribers.push(
    subscribe('document.status_changed', async (event) => {
      const doc = documents.value.find((d) => d.id === event.data.document_id)
      if (doc) {
        doc.processing_status = event.data.new_status

        // If status changed to llm_complete, reload the document to get tags
        if (event.data.new_status === 'llm_complete') {
          try {
            const updatedDoc = await documentService.get(event.data.document_id)
            const index = documents.value.findIndex((d) => d.id === event.data.document_id)
            if (index !== -1) {
              documents.value[index] = updatedDoc
            }
          } catch (error) {
            console.error('Failed to reload document after LLM completion:', error)
          }
        }
      }
    })
  )

  // Subscribe to document updates (e.g., tag changes)
  unsubscribers.push(
    subscribe('document.updated', async (event) => {
      console.log('[DocumentsView] Received document.updated event:', event)
      try {
        const updatedDoc = await documentService.get(event.data.document_id)
        console.log('[DocumentsView] Fetched updated document:', updatedDoc)
        const index = documents.value.findIndex((d) => d.id === event.data.document_id)
        if (index !== -1) {
          console.log('[DocumentsView] Replacing document at index:', index)
          documents.value[index] = updatedDoc
        } else {
          console.log('[DocumentsView] Document not found in list:', event.data.document_id)
        }
      } catch (error) {
        console.error('Failed to reload updated document:', error)
      }
    })
  )

  // Subscribe to deletions
  unsubscribers.push(
    subscribe('document.deleted', (event) => {
      documents.value = documents.value.filter((d) => d.id !== event.data.document_id)
    })
  )
})

onBeforeUnmount(() => {
  unsubscribers.forEach((unsub) => unsub())
})
</script>

<template>
  <div class="min-h-screen">
    <AppHeader />
    <ConfirmDialog />

    <div class="documents-view p-6 max-w-7xl mx-auto">

    <div class="mb-6">
      <h1 class="text-3xl font-bold mb-2">Documents</h1>
      <p class="text-muted-color">Upload and manage your documents</p>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- Upload Section -->
      <div class="lg:col-span-1 space-y-6">
        <Card>
          <template #title>Upload Documents</template>
          <template #content>
            <DocumentUpload
              @uploaded="handleDocumentUploaded"
              @batch-complete="handleBatchUploadComplete"
            />
          </template>
        </Card>

        <!-- Recent Documents Widget -->
        <RecentDocumentsWidget />

        <!-- Activity Log Widget -->
        <ActivityLogWidget />
      </div>

      <!-- Documents List -->
      <div class="lg:col-span-2">
        <Card>
          <template #title>
            <div class="flex items-center justify-between">
              <span>Your Documents</span>
            </div>
          </template>
          <template #content>
            <!-- Statistics Panel -->
            <div v-if="hasDocuments && !initialLoading" class="mb-4 grid grid-cols-2 md:grid-cols-4 gap-4">
              <div class="bg-surface-100 dark:bg-surface-800 p-4 rounded-lg border border-surface-200 dark:border-surface-700">
                <div class="text-sm text-muted-color mb-1">Total Documents</div>
                <div class="text-2xl font-bold">{{ totalDocuments.toLocaleString() }}</div>
              </div>
              <div class="bg-surface-100 dark:bg-surface-800 p-4 rounded-lg border border-surface-200 dark:border-surface-700">
                <div class="text-sm text-muted-color mb-1">Total Size</div>
                <div class="text-2xl font-bold">{{ totalFileSize }}</div>
              </div>
              <div class="bg-surface-100 dark:bg-surface-800 p-4 rounded-lg border border-surface-200 dark:border-surface-700">
                <div class="text-sm text-muted-color mb-1">Total Words</div>
                <div class="text-2xl font-bold">{{ totalWords.toLocaleString() }}</div>
              </div>
              <div class="bg-surface-100 dark:bg-surface-800 p-4 rounded-lg border border-surface-200 dark:border-surface-700">
                <div class="text-sm text-muted-color mb-1">Avg. Size</div>
                <div class="text-2xl font-bold">{{ averageFileSize }}</div>
              </div>
            </div>

            <!-- Search Bar -->
            <div class="mb-4">
              <IconField iconPosition="left">
                <InputIcon class="pi pi-search" />
                <InputText
                  v-model="searchQuery"
                  placeholder="Search documents..."
                  class="w-full"
                  @keyup.enter="performSearch"
                />
              </IconField>
              <div class="mt-2 flex gap-2 items-center">
                <Button
                  label="Search"
                  icon="pi pi-search"
                  @click="performSearch"
                  :loading="loading"
                  size="small"
                />
                <Select
                  v-model="searchMode"
                  :options="searchModes"
                  optionLabel="label"
                  optionValue="value"
                  placeholder="Search Mode"
                  class="w-48"
                />
                <Button
                  v-if="searchQuery"
                  label="Clear"
                  icon="pi pi-times"
                  @click="clearSearch"
                  severity="secondary"
                  size="small"
                  outlined
                />
              </div>
            </div>
            <!-- Initial Loading State -->
            <LoadingSpinner
              v-if="initialLoading"
              message="Loading documents..."
            />

            <!-- Error State -->
            <EmptyState
              v-else-if="error"
              icon="pi pi-exclamation-circle"
              title="Failed to load documents"
              :description="error"
              action-label="Try Again"
              action-icon="pi pi-refresh"
              @action="loadDocuments"
            />

            <!-- Empty State -->
            <EmptyState
              v-else-if="!hasDocuments && !loading && !isSearching"
              icon="pi pi-file"
              title="No documents yet"
              description="Upload your first document to get started. You can drag and drop files or click the upload button."
            />

            <!-- Search Results Empty -->
            <EmptyState
              v-else-if="isSearching && !hasDocuments && !loading"
              icon="pi pi-search"
              title="No results found"
              :description="`No documents match '${searchQuery}'`"
              action-label="Clear Search"
              action-icon="pi pi-times"
              @action="clearSearch"
            />

            <!-- Data Table -->
            <DataTable
              v-else-if="hasDocuments"
              :value="documents"
              :loading="loading"
              striped-rows
              paginator
              :rows="10"
              :rows-per-page-options="[10, 25, 50]"
              current-page-report-template="Showing {first} to {last} of {totalRecords} documents"
              paginator-template="FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink CurrentPageReport RowsPerPageDropdown"
              sort-mode="single"
              :sort-field="sortField"
              :sort-order="sortOrder"
              @sort="onSort"
            >

              <Column field="title" header="Title" sortable>
                <template #body="{ data }">
                  <div>
                    <router-link
                      :to="`/documents/${data.id}`"
                      class="font-medium text-blue-600 hover:text-blue-800 hover:underline"
                    >
                      <span v-if="searchQuery" v-html="highlightText(data.title, searchQuery)"></span>
                      <span v-else>{{ data.title }}</span>
                    </router-link>
                    <div class="text-sm text-muted-color">
                      <span v-if="searchQuery" v-html="highlightText(data.original_filename, searchQuery)"></span>
                      <span v-else>{{ data.original_filename }}</span>
                    </div>
                  </div>
                </template>
              </Column>

              <Column field="file_size" header="Size" sortable>
                <template #body="{ data }">
                  {{ formatFileSize(data.file_size) }}
                </template>
              </Column>

              <Column field="processing_status" header="Status" sortable>
                <template #body="{ data }">
                  <span
                    :class="{
                      'bg-yellow-100 text-yellow-800':
                        data.processing_status === 'pending',
                      'bg-blue-100 text-blue-800':
                        data.processing_status === 'processing',
                      'bg-green-100 text-green-800':
                        data.processing_status === 'ocr_complete' ||
                        data.processing_status === 'embedding_complete' ||
                        data.processing_status === 'llm_complete',
                      'bg-red-100 text-red-800':
                        data.processing_status === 'ocr_failed' ||
                        data.processing_status === 'failed',
                    }"
                    class="px-2 py-1 rounded text-xs font-medium uppercase"
                  >
                    {{
                      data.processing_status
                        .replace('_', ' ')
                        .replace('ocr', 'OCR')
                        .replace('llm', 'LLM')
                    }}
                  </span>
                </template>
              </Column>

              <Column field="tags" header="Tags">
                <template #body="{ data }">
                  <div class="flex flex-wrap gap-1">
                    <span
                      v-for="tag in data.tags"
                      :key="tag.id"
                      :style="{ backgroundColor: tag.color || '#6366f1', color: '#fff' }"
                      class="px-2 py-1 rounded text-xs font-medium"
                    >
                      {{ tag.name }}
                    </span>
                    <span v-if="!data.tags || data.tags.length === 0" class="text-gray-400 text-xs">
                      No tags
                    </span>
                  </div>
                </template>
              </Column>

              <Column field="created_at" header="Uploaded" sortable>
                <template #body="{ data }">
                  <span class="text-sm">{{ formatDate(data.created_at) }}</span>
                </template>
              </Column>

              <Column header="Actions">
                <template #body="{ data }">
                  <Button
                    icon="pi pi-trash"
                    severity="danger"
                    text
                    rounded
                    @click="handleDelete(data)"
                  />
                </template>
              </Column>
            </DataTable>
          </template>
        </Card>
      </div>
    </div>
    </div>
  </div>
</template>

<style scoped>
:deep(.p-datatable) {
  font-size: 0.875rem;
}
</style>
