<script setup lang="ts">
import { ref, computed } from 'vue'
import FileUpload from 'primevue/fileupload'
import Button from 'primevue/button'
import ProgressBar from 'primevue/progressbar'
import Message from 'primevue/message'
import Badge from 'primevue/badge'
import { documentService } from '@/services/documentService'
import type { Document } from '@/types/document'
import type { FileUploadSelectEvent, FileUploadRemoveEvent } from 'primevue/fileupload'

const emit = defineEmits<{
  uploaded: [document: Document]
  batchComplete: [results: { successful: Document[], failed: Array<{ filename: string, error: string }> }]
}>()

const fileUploadRef = ref()
const selectedFiles = ref<File[]>([])
const uploading = ref(false)
const uploadProgress = ref<Map<string, { progress: number, status: 'pending' | 'uploading' | 'success' | 'error', error?: string }>>(new Map())

const handleSelect = (event: FileUploadSelectEvent) => {
  if (event.files && event.files.length > 0) {
    selectedFiles.value = Array.from(event.files)

    // Initialize progress tracking for each file
    selectedFiles.value.forEach(file => {
      uploadProgress.value.set(file.name, { progress: 0, status: 'pending' })
    })
  }
}

const handleRemove = (event: FileUploadRemoveEvent) => {
  const file = event.file as File
  selectedFiles.value = selectedFiles.value.filter(f => f.name !== file.name)
  uploadProgress.value.delete(file.name)
}

const handleClear = () => {
  selectedFiles.value = []
  uploadProgress.value.clear()
}

const uploadSingleFile = async (file: File): Promise<{ success: boolean, document?: Document, error?: string, documentId?: string }> => {
  try {
    uploadProgress.value.set(file.name, { progress: 0, status: 'uploading' })

    const document = await documentService.upload({ file })

    uploadProgress.value.set(file.name, { progress: 100, status: 'success' })

    return { success: true, document }
  } catch (err: any) {
    let errorMessage = 'Upload failed'
    let documentId: string | undefined

    if (err.response?.status === 409) {
      errorMessage = 'Already uploaded'
      // Extract document_id from the 409 response
      // The API returns: { error: "duplicate", message: "...", document_id: "..." }
      documentId = err.response?.data?.detail?.document_id || err.response?.data?.document_id

      // If we got the document ID, fetch the existing document and treat it as success
      if (documentId) {
        try {
          const existingDoc = await documentService.get(documentId)
          uploadProgress.value.set(file.name, { progress: 100, status: 'success' })
          return { success: true, document: existingDoc, documentId }
        } catch (fetchErr) {
          console.error('Failed to fetch existing document:', fetchErr)
          // Fall through to error handling
        }
      }
    } else if (err.response?.data?.detail) {
      errorMessage = err.response.data.detail
    }

    uploadProgress.value.set(file.name, { progress: 0, status: 'error', error: errorMessage })

    return { success: false, error: errorMessage, documentId }
  }
}

const handleUpload = async () => {
  if (selectedFiles.value.length === 0) {
    return
  }

  uploading.value = true

  const results = await Promise.allSettled(
    selectedFiles.value.map(file => uploadSingleFile(file))
  )

  const successful: Document[] = []
  const failed: Array<{ filename: string, error: string }> = []

  results.forEach((result, index) => {
    const filename = selectedFiles.value[index].name

    if (result.status === 'fulfilled' && result.value.success && result.value.document) {
      successful.push(result.value.document)
      emit('uploaded', result.value.document)
    } else if (result.status === 'fulfilled' && !result.value.success) {
      failed.push({ filename, error: result.value.error || 'Unknown error' })
    } else if (result.status === 'rejected') {
      failed.push({ filename, error: result.reason?.message || 'Upload failed' })
    }
  })

  emit('batchComplete', { successful, failed })

  uploading.value = false

  // Clear successful files after a delay
  setTimeout(() => {
    selectedFiles.value = selectedFiles.value.filter(file => {
      const progress = uploadProgress.value.get(file.name)
      return progress?.status === 'error'
    })

    // Clear progress for successful uploads
    uploadProgress.value.forEach((value, key) => {
      if (value.status === 'success') {
        uploadProgress.value.delete(key)
      }
    })

    // Clear the file upload component if all were successful
    if (selectedFiles.value.length === 0 && fileUploadRef.value) {
      fileUploadRef.value.clear()
      uploadProgress.value.clear()
    }
  }, 2000)
}

const overallProgress = computed(() => {
  if (uploadProgress.value.size === 0) return 0

  let totalProgress = 0
  uploadProgress.value.forEach(item => {
    totalProgress += item.progress
  })

  return Math.round(totalProgress / uploadProgress.value.size)
})

const getFileIcon = (filename: string): string => {
  const ext = filename.toLowerCase().split('.').pop()
  switch (ext) {
    case 'pdf': return 'pi-file-pdf'
    case 'jpg':
    case 'jpeg':
    case 'png': return 'pi-image'
    case 'tiff':
    case 'tif': return 'pi-file'
    default: return 'pi-file'
  }
}

const getStatusIcon = (status: string): string => {
  switch (status) {
    case 'pending': return 'pi-clock'
    case 'uploading': return 'pi-spin pi-spinner'
    case 'success': return 'pi-check-circle'
    case 'error': return 'pi-times-circle'
    default: return 'pi-circle'
  }
}

const getStatusColor = (status: string): string => {
  switch (status) {
    case 'pending': return 'text-gray-500'
    case 'uploading': return 'text-blue-500'
    case 'success': return 'text-green-500'
    case 'error': return 'text-red-500'
    default: return 'text-gray-500'
  }
}

const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}
</script>

<template>
  <div class="document-upload space-y-4">
    <FileUpload
      ref="fileUploadRef"
      mode="advanced"
      :multiple="true"
      name="files"
      accept=".pdf,.png,.jpg,.jpeg,.tiff,.tif"
      :max-file-size="100000000"
      :disabled="uploading"
      :auto="false"
      :custom-upload="true"
      choose-label="Choose Files"
      upload-label="Upload All"
      cancel-label="Clear All"
      @select="handleSelect"
      @remove="handleRemove"
      @uploader="handleUpload"
    >
      <template #header="{ chooseCallback, clearCallback }">
        <div class="flex items-center justify-between gap-2 p-4 border-b border-surface-200 dark:border-surface-700">
          <div class="flex gap-2">
            <Button
              icon="pi pi-plus"
              label="Choose Files"
              severity="secondary"
              @click="chooseCallback"
              :disabled="uploading"
            />
            <Button
              v-if="selectedFiles.length > 0"
              icon="pi pi-upload"
              label="Upload All"
              @click="handleUpload"
              :loading="uploading"
              :disabled="uploading"
            />
            <Button
              v-if="selectedFiles.length > 0"
              icon="pi pi-times"
              label="Clear All"
              severity="secondary"
              outlined
              @click="() => { clearCallback(); handleClear(); }"
              :disabled="uploading"
            />
          </div>
          <Badge
            v-if="selectedFiles.length > 0"
            :value="`${selectedFiles.length} file${selectedFiles.length !== 1 ? 's' : ''}`"
            severity="info"
          />
        </div>
      </template>

      <template #content>
        <div v-if="selectedFiles.length > 0" class="p-4">
          <!-- Overall Progress -->
          <div v-if="uploading" class="mb-4">
            <div class="flex justify-between items-center mb-2">
              <span class="text-sm font-medium">Uploading...</span>
              <span class="text-sm text-muted-color">{{ overallProgress }}%</span>
            </div>
            <ProgressBar :value="overallProgress" :show-value="false" />
          </div>

          <!-- File List -->
          <div class="space-y-2">
            <div
              v-for="file in selectedFiles"
              :key="file.name"
              class="flex items-center gap-3 p-3 rounded border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900"
            >
              <!-- File Icon -->
              <i :class="['pi', getFileIcon(file.name), 'text-2xl', 'text-muted-color']"></i>

              <!-- File Info -->
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2">
                  <p class="font-medium text-sm truncate">{{ file.name }}</p>
                  <Badge
                    v-if="uploadProgress.get(file.name)"
                    :value="uploadProgress.get(file.name)?.status"
                    :severity="uploadProgress.get(file.name)?.status === 'success' ? 'success' : uploadProgress.get(file.name)?.status === 'error' ? 'danger' : 'info'"
                    class="text-xs"
                  />
                </div>
                <p class="text-xs text-muted-color">{{ formatFileSize(file.size) }}</p>

                <!-- Error Message -->
                <Message
                  v-if="uploadProgress.get(file.name)?.status === 'error'"
                  severity="error"
                  :closable="false"
                  class="mt-2"
                >
                  <span class="text-xs">{{ uploadProgress.get(file.name)?.error }}</span>
                </Message>

                <!-- Progress Bar -->
                <ProgressBar
                  v-if="uploadProgress.get(file.name)?.status === 'uploading'"
                  :value="uploadProgress.get(file.name)?.progress || 0"
                  :show-value="false"
                  class="mt-2"
                  style="height: 4px"
                />
              </div>

              <!-- Status Icon -->
              <i
                :class="[
                  'pi',
                  getStatusIcon(uploadProgress.get(file.name)?.status || 'pending'),
                  getStatusColor(uploadProgress.get(file.name)?.status || 'pending'),
                  'text-xl'
                ]"
              ></i>
            </div>
          </div>
        </div>
      </template>

      <template #empty>
        <div class="flex flex-col items-center justify-center py-12 text-muted-color">
          <i class="pi pi-cloud-upload text-6xl mb-4 opacity-50"></i>
          <p class="text-lg font-medium mb-2">Drag and drop files here</p>
          <p class="text-sm">or click "Choose Files" to browse</p>
          <p class="text-xs mt-4">Supported: PDF, PNG, JPG, TIFF (max 100MB each)</p>
        </div>
      </template>
    </FileUpload>
  </div>
</template>

<style scoped>
:deep(.p-fileupload) {
  border: 2px dashed var(--p-surface-300);
  border-radius: var(--p-border-radius);
  background: transparent;
}

:deep(.p-fileupload-content) {
  padding: 0;
  border: none;
  background: transparent;
}

:deep(.p-fileupload-buttonbar) {
  padding: 0;
  border: none;
  background: transparent;
}

:deep(.p-fileupload):hover {
  border-color: var(--p-primary-color);
}

.dark-mode :deep(.p-fileupload) {
  border-color: var(--p-surface-700);
}
</style>
