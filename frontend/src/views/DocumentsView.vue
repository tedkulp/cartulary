<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Card from 'primevue/card'
import InputText from 'primevue/inputtext'
import IconField from 'primevue/iconfield'
import InputIcon from 'primevue/inputicon'
import ConfirmDialog from 'primevue/confirmdialog'
import { useConfirm } from 'primevue/useconfirm'
import { useToast } from 'primevue/usetoast'
import DocumentUpload from '@/components/DocumentUpload.vue'
import { documentService } from '@/services/documentService'
import { searchService } from '@/services/searchService'
import type { Document } from '@/types/document'

const router = useRouter()
const confirm = useConfirm()
const toast = useToast()

const documents = ref<Document[]>([])
const loading = ref(false)
const searchQuery = ref('')

const loadDocuments = async () => {
  loading.value = true
  try {
    documents.value = await documentService.list()
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to load documents',
      life: 3000,
    })
  } finally {
    loading.value = false
  }
}

const performSearch = async () => {
  if (!searchQuery.value.trim()) {
    loadDocuments()
    return
  }

  loading.value = true
  try {
    documents.value = await searchService.search(searchQuery.value)
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
  toast.add({
    severity: 'success',
    summary: 'Success',
    detail: 'Document uploaded successfully',
    life: 3000,
  })
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
  const date = new Date(dateString)
  return date.toLocaleString()
}

onMounted(() => {
  loadDocuments()
})
</script>

<template>
  <div class="documents-view p-6 max-w-7xl mx-auto">
    <ConfirmDialog />

    <div class="mb-6">
      <h1 class="text-3xl font-bold text-gray-900 mb-2">Documents</h1>
      <p class="text-gray-600">Upload and manage your documents</p>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- Upload Section -->
      <div class="lg:col-span-1">
        <Card>
          <template #title>Upload Document</template>
          <template #content>
            <DocumentUpload @uploaded="handleDocumentUploaded" />
          </template>
        </Card>
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
              <div class="mt-2 flex gap-2">
                <Button
                  label="Search"
                  icon="pi pi-search"
                  @click="performSearch"
                  :loading="loading"
                  size="small"
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
            <DataTable
              :value="documents"
              :loading="loading"
              striped-rows
              paginator
              :rows="10"
              :rows-per-page-options="[10, 25, 50]"
              current-page-report-template="Showing {first} to {last} of {totalRecords} documents"
              paginator-template="FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink CurrentPageReport RowsPerPageDropdown"
            >
              <template #empty>
                <div class="text-center py-8 text-gray-500">
                  No documents uploaded yet. Upload your first document to get started.
                </div>
              </template>

              <Column field="title" header="Title" sortable>
                <template #body="{ data }">
                  <div class="font-medium">{{ data.title }}</div>
                  <div class="text-sm text-gray-500">{{ data.original_filename }}</div>
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
</template>

<style scoped>
:deep(.p-datatable) {
  font-size: 0.875rem;
}
</style>
