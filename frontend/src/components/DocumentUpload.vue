<script setup lang="ts">
import { ref } from 'vue'
import FileUpload from 'primevue/fileupload'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import Message from 'primevue/message'
import { documentService } from '@/services/documentService'
import type { Document } from '@/types/document'
import type { FileUploadSelectEvent } from 'primevue/fileupload'

const emit = defineEmits<{
  uploaded: [document: Document]
}>()

const fileUploadRef = ref()
const uploading = ref(false)
const error = ref<string | null>(null)
const title = ref('')
const selectedFile = ref<File | null>(null)

const handleSelect = (event: FileUploadSelectEvent) => {
  if (event.files && event.files.length > 0) {
    selectedFile.value = event.files[0]
    error.value = null
  }
}

const handleUpload = async () => {
  if (!selectedFile.value) {
    error.value = 'Please select a file first'
    return
  }

  error.value = null
  uploading.value = true

  try {
    const document = await documentService.upload({
      file: selectedFile.value,
      title: title.value || undefined,
    })

    emit('uploaded', document)
    title.value = ''
    selectedFile.value = null
    if (fileUploadRef.value) {
      fileUploadRef.value.clear()
    }
  } catch (err: any) {
    if (err.response?.status === 409) {
      error.value = 'This document has already been uploaded'
    } else {
      error.value = err.response?.data?.detail || 'Failed to upload document'
    }
  } finally {
    uploading.value = false
  }
}

const clearError = () => {
  error.value = null
}
</script>

<template>
  <div class="document-upload space-y-4">
    <Message v-if="error" severity="error" :closable="true" @close="clearError">
      {{ error }}
    </Message>

    <div class="space-y-2">
      <label for="document-title" class="block text-sm font-medium text-gray-700">
        Title (Optional)
      </label>
      <InputText
        id="document-title"
        v-model="title"
        placeholder="Leave blank to use filename"
        class="w-full"
        :disabled="uploading"
      />
    </div>

    <FileUpload
      ref="fileUploadRef"
      mode="basic"
      name="file"
      accept=".pdf,.png,.jpg,.jpeg,.tiff,.tif"
      :max-file-size="100000000"
      :disabled="uploading"
      :auto="false"
      choose-label="Choose Document"
      @select="handleSelect"
    />

    <Button
      v-if="selectedFile"
      label="Upload"
      icon="pi pi-upload"
      :loading="uploading"
      :disabled="uploading"
      @click="handleUpload"
      class="w-full"
    />

    <p class="text-sm text-gray-500">
      Supported formats: PDF, PNG, JPG, TIFF (max 100MB)
    </p>
  </div>
</template>

<style scoped>
:deep(.p-fileupload) {
  width: 100%;
}
</style>
