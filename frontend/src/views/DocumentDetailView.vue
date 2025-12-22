<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Button from 'primevue/button'
import Card from 'primevue/card'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'
import Chip from 'primevue/chip'
import MultiSelect from 'primevue/multiselect'
import Dialog from 'primevue/dialog'
import ConfirmDialog from 'primevue/confirmdialog'
import { useConfirm } from 'primevue/useconfirm'
import { useToast } from 'primevue/usetoast'
import { documentService } from '@/services/documentService'
import { tagService, type Tag } from '@/services/tagService'
import type { Document } from '@/types/document'
import api from '@/services/api'

const route = useRoute()
const router = useRouter()
const confirm = useConfirm()
const toast = useToast()

const document = ref<Document | null>(null)
const loading = ref(false)
const editingTitle = ref(false)
const titleEdit = ref('')
const editingDescription = ref(false)
const descriptionEdit = ref('')

// Tags
const availableTags = ref<Tag[]>([])
const selectedTags = ref<Tag[]>([])
const showTagDialog = ref(false)

// PDF Blob URL for authenticated viewing
const pdfBlobUrl = ref<string>('')

const loadPdfBlob = async () => {
  if (!document.value || document.value.file_extension !== 'pdf') return

  try {
    // Fetch PDF as blob for viewing (not downloading)
    const response = await api.get(`/api/v1/documents/${document.value.id}/download`, {
      responseType: 'blob',
    })
    pdfBlobUrl.value = window.URL.createObjectURL(new Blob([response.data]))
  } catch (error) {
    console.error('Failed to load PDF:', error)
  }
}

const handleDownload = async () => {
  if (!document.value) return
  try {
    await documentService.downloadFile(document.value.id, document.value.original_filename)
    toast.add({
      severity: 'success',
      summary: 'Success',
      detail: 'Download started',
      life: 3000,
    })
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to download document',
      life: 3000,
    })
  }
}

const loadDocument = async () => {
  loading.value = true
  try {
    const id = route.params.id as string
    document.value = await documentService.get(id)
    titleEdit.value = document.value.title
    descriptionEdit.value = document.value.description || ''
    selectedTags.value = document.value.tags

    // Load PDF blob for viewing if it's a PDF
    if (document.value.file_extension === 'pdf') {
      await loadPdfBlob()
    }
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to load document',
      life: 3000,
    })
    router.push('/documents')
  } finally {
    loading.value = false
  }
}

const loadTags = async () => {
  try {
    availableTags.value = await tagService.list()
  } catch (error: any) {
    console.error('Failed to load tags:', error)
  }
}

const saveTitle = async () => {
  if (!document.value) return

  try {
    await documentService.update(document.value.id, { title: titleEdit.value })
    document.value.title = titleEdit.value
    editingTitle.value = false
    toast.add({
      severity: 'success',
      summary: 'Success',
      detail: 'Title updated successfully',
      life: 3000,
    })
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to update title',
      life: 3000,
    })
  }
}

const saveDescription = async () => {
  if (!document.value) return

  try {
    await documentService.update(document.value.id, { description: descriptionEdit.value })
    document.value.description = descriptionEdit.value
    editingDescription.value = false
    toast.add({
      severity: 'success',
      summary: 'Success',
      detail: 'Description updated successfully',
      life: 3000,
    })
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to update description',
      life: 3000,
    })
  }
}

const saveTags = async () => {
  if (!document.value) return

  try {
    const tagIds = selectedTags.value.map((t) => t.id)
    await tagService.addToDocument(document.value.id, tagIds)
    document.value.tags = selectedTags.value
    showTagDialog.value = false
    toast.add({
      severity: 'success',
      summary: 'Success',
      detail: 'Tags updated successfully',
      life: 3000,
    })
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to update tags',
      life: 3000,
    })
  }
}

const removeTag = async (tag: Tag) => {
  if (!document.value) return

  try {
    await tagService.removeFromDocument(document.value.id, tag.id)
    document.value.tags = document.value.tags.filter((t) => t.id !== tag.id)
    toast.add({
      severity: 'success',
      summary: 'Success',
      detail: 'Tag removed successfully',
      life: 3000,
    })
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to remove tag',
      life: 3000,
    })
  }
}

const handleReprocess = () => {
  if (!document.value) return

  confirm.require({
    message: 'Reprocess this document? This will retry OCR text extraction.',
    header: 'Confirm Reprocess',
    icon: 'pi pi-refresh',
    accept: async () => {
      try {
        await documentService.reprocess(document.value!.id)
        toast.add({
          severity: 'success',
          summary: 'Success',
          detail: 'Document reprocessing started',
          life: 3000,
        })
        // Reload document after a delay
        setTimeout(loadDocument, 2000)
      } catch (error: any) {
        toast.add({
          severity: 'error',
          summary: 'Error',
          detail: 'Failed to reprocess document',
          life: 3000,
        })
      }
    },
  })
}

const handleDelete = () => {
  if (!document.value) return

  confirm.require({
    message: `Delete "${document.value.title}"? This action cannot be undone.`,
    header: 'Confirm Delete',
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    accept: async () => {
      try {
        await documentService.delete(document.value!.id)
        toast.add({
          severity: 'success',
          summary: 'Success',
          detail: 'Document deleted successfully',
          life: 3000,
        })
        router.push('/documents')
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
  loadDocument()
  loadTags()
})
</script>

<template>
  <div class="document-detail-view p-6 max-w-7xl mx-auto">
    <ConfirmDialog />

    <div v-if="loading" class="text-center py-8">
      <i class="pi pi-spin pi-spinner text-4xl text-blue-500"></i>
    </div>

    <div v-else-if="document" class="space-y-6">
      <!-- Header -->
      <div class="flex items-start justify-between">
        <div class="flex-1">
          <Button
            icon="pi pi-arrow-left"
            label="Back to Documents"
            text
            @click="router.push('/documents')"
            class="mb-4"
          />

          <div v-if="!editingTitle" class="flex items-center gap-2">
            <h1 class="text-3xl font-bold text-gray-900">{{ document.title }}</h1>
            <Button icon="pi pi-pencil" text rounded @click="editingTitle = true" />
          </div>
          <div v-else class="flex items-center gap-2">
            <InputText v-model="titleEdit" class="text-2xl font-bold flex-1" />
            <Button icon="pi pi-check" text rounded @click="saveTitle" />
            <Button
              icon="pi pi-times"
              text
              rounded
              severity="secondary"
              @click="editingTitle = false"
            />
          </div>

          <p class="text-gray-600 mt-2">{{ document.original_filename }}</p>

          <!-- Description -->
          <div class="mt-4">
            <div v-if="!editingDescription" class="flex items-start gap-2">
              <div class="flex-1">
                <p v-if="document.description" class="text-gray-700">
                  {{ document.description }}
                </p>
                <p v-else class="text-gray-400 italic">No description</p>
              </div>
              <Button
                icon="pi pi-pencil"
                text
                rounded
                size="small"
                @click="editingDescription = true"
              />
            </div>
            <div v-else class="flex flex-col gap-2">
              <Textarea
                v-model="descriptionEdit"
                rows="3"
                class="w-full"
                placeholder="Add a description..."
              />
              <div class="flex gap-2">
                <Button
                  icon="pi pi-check"
                  label="Save"
                  size="small"
                  @click="saveDescription"
                />
                <Button
                  icon="pi pi-times"
                  label="Cancel"
                  size="small"
                  severity="secondary"
                  @click="editingDescription = false"
                />
              </div>
            </div>
          </div>
        </div>

        <div class="flex gap-2">
          <Button
            v-if="
              document.processing_status === 'ocr_failed' ||
              document.processing_status === 'failed'
            "
            label="Reprocess"
            icon="pi pi-refresh"
            @click="handleReprocess"
            severity="warning"
          />
          <Button
            label="Download"
            icon="pi pi-download"
            @click="handleDownload"
            severity="secondary"
          />
          <Button
            label="Delete"
            icon="pi pi-trash"
            @click="handleDelete"
            severity="danger"
          />
        </div>
      </div>

      <!-- Metadata Card -->
      <Card>
        <template #title>Document Information</template>
        <template #content>
          <div class="grid grid-cols-2 gap-4">
            <div>
              <p class="text-sm text-gray-500">File Size</p>
              <p class="font-medium">{{ formatFileSize(document.file_size) }}</p>
            </div>
            <div>
              <p class="text-sm text-gray-500">File Type</p>
              <p class="font-medium">{{ document.file_extension.toUpperCase() }}</p>
            </div>
            <div>
              <p class="text-sm text-gray-500">Uploaded</p>
              <p class="font-medium">{{ formatDate(document.created_at) }}</p>
            </div>
            <div>
              <p class="text-sm text-gray-500">Status</p>
              <span
                :class="{
                  'bg-yellow-100 text-yellow-800': document.processing_status === 'pending',
                  'bg-blue-100 text-blue-800': document.processing_status === 'processing',
                  'bg-green-100 text-green-800':
                    document.processing_status === 'ocr_complete' ||
                    document.processing_status === 'embedding_complete' ||
                    document.processing_status === 'llm_complete',
                  'bg-red-100 text-red-800':
                    document.processing_status === 'ocr_failed' ||
                    document.processing_status === 'failed',
                }"
                class="px-2 py-1 rounded text-xs font-medium uppercase"
              >
                {{
                  document.processing_status
                    .replace('_', ' ')
                    .replace('ocr', 'OCR')
                    .replace('llm', 'LLM')
                }}
              </span>
            </div>
          </div>

          <!-- Tags -->
          <div class="mt-4">
            <div class="flex items-center justify-between mb-2">
              <p class="text-sm text-gray-500">Tags</p>
              <Button
                label="Edit Tags"
                icon="pi pi-tag"
                size="small"
                text
                @click="showTagDialog = true"
              />
            </div>
            <div class="flex flex-wrap gap-2">
              <Chip
                v-for="tag in document.tags"
                :key="tag.id"
                :label="tag.name"
                :style="{ backgroundColor: tag.color || '#6366f1', color: '#fff' }"
                removable
                @remove="removeTag(tag)"
              />
              <span v-if="document.tags.length === 0" class="text-gray-400 text-sm">
                No tags
              </span>
            </div>
          </div>
        </template>
      </Card>

      <!-- PDF Viewer -->
      <Card v-if="document.file_extension === 'pdf' && pdfBlobUrl">
        <template #title>Document Preview</template>
        <template #content>
          <iframe
            :src="pdfBlobUrl"
            class="w-full h-[600px] border rounded"
            title="PDF Preview"
          ></iframe>
        </template>
      </Card>

      <!-- OCR Text -->
      <Card v-if="document.ocr_text">
        <template #title>Extracted Text</template>
        <template #content>
          <Textarea
            :value="document.ocr_text"
            rows="15"
            class="w-full font-mono text-sm"
            readonly
          />
        </template>
      </Card>

      <!-- No OCR Text Message -->
      <Card v-else-if="document.processing_status === 'ocr_complete'">
        <template #content>
          <div class="text-center py-8 text-gray-500">
            <i class="pi pi-info-circle text-4xl mb-2"></i>
            <p>No text was extracted from this document.</p>
          </div>
        </template>
      </Card>
    </div>

    <!-- Tag Selection Dialog -->
    <Dialog
      v-model:visible="showTagDialog"
      header="Manage Tags"
      :modal="true"
      :style="{ width: '450px' }"
    >
      <div class="flex flex-col gap-4">
        <MultiSelect
          v-model="selectedTags"
          :options="availableTags"
          optionLabel="name"
          placeholder="Select tags"
          class="w-full"
          display="chip"
        >
          <template #chip="{ value }">
            <Chip
              :label="value.name"
              :style="{ backgroundColor: value.color || '#6366f1', color: '#fff' }"
            />
          </template>
        </MultiSelect>
      </div>

      <template #footer>
        <Button label="Cancel" severity="secondary" @click="showTagDialog = false" />
        <Button label="Save" @click="saveTags" />
      </template>
    </Dialog>
  </div>
</template>
