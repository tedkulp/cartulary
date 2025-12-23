<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useToast } from 'primevue/usetoast'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Tag from 'primevue/tag'
import Button from 'primevue/button'
import AppHeader from '@/components/AppHeader.vue'
import sharingService from '@/services/sharingService'
import type { SharedDocument } from '@/types/sharing'

const router = useRouter()
const toast = useToast()

const sharedDocuments = ref<SharedDocument[]>([])
const loading = ref(false)

const loadSharedDocuments = async () => {
  loading.value = true
  try {
    sharedDocuments.value = await sharingService.listSharedWithMe()
  } catch (error) {
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to load shared documents',
      life: 3000
    })
  } finally {
    loading.value = false
  }
}

const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleDateString()
}

const getPermissionSeverity = (level: string) => {
  switch (level) {
    case 'admin':
      return 'danger'
    case 'write':
      return 'warning'
    case 'read':
      return 'info'
    default:
      return null
  }
}

const viewDocument = (doc: SharedDocument) => {
  router.push({ name: 'document-detail', params: { id: doc.document.id } })
}

onMounted(() => {
  loadSharedDocuments()
})
</script>

<template>
  <div class="min-h-screen bg-gray-50">
    <AppHeader />

    <div class="shared-documents-view p-6">
      <div class="mb-6">
      <h1 class="text-3xl font-bold mb-2">Shared with Me</h1>
      <p class="text-gray-600">Documents that other users have shared with you</p>
    </div>

    <DataTable
      :value="sharedDocuments"
      :loading="loading"
      stripedRows
      :paginator="true"
      :rows="20"
      paginatorTemplate="FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink CurrentPageReport RowsPerPageDropdown"
      :rowsPerPageOptions="[10, 20, 50]"
      currentPageReportTemplate="Showing {first} to {last} of {totalRecords} documents"
    >
      <Column field="document.title" header="Title" sortable>
        <template #body="slotProps">
          <div v-if="slotProps.data.document">
            <div class="font-semibold">{{ slotProps.data.document.title }}</div>
            <div class="text-sm text-gray-500">{{ slotProps.data.document.original_filename }}</div>
          </div>
        </template>
      </Column>

      <Column field="share.permission_level" header="Permission" sortable>
        <template #body="slotProps">
          <Tag
            v-if="slotProps.data.share"
            :value="slotProps.data.share.permission_level.toUpperCase()"
            :severity="getPermissionSeverity(slotProps.data.share.permission_level)"
          />
        </template>
      </Column>

      <Column field="share.created_at" header="Shared On" sortable>
        <template #body="slotProps">
          <span v-if="slotProps.data.share">{{ formatDate(slotProps.data.share.created_at) }}</span>
        </template>
      </Column>

      <Column field="share.expires_at" header="Expires" sortable>
        <template #body="slotProps">
          <span v-if="slotProps.data.share?.expires_at">
            {{ formatDate(slotProps.data.share.expires_at) }}
          </span>
          <span v-else class="text-gray-400">Never</span>
        </template>
      </Column>

      <Column field="document.processing_status" header="Status" sortable>
        <template #body="slotProps">
          <Tag
            v-if="slotProps.data.document?.processing_status === 'llm_complete'"
            value="Ready"
            severity="success"
          />
          <Tag
            v-else-if="slotProps.data.document?.processing_status === 'processing'"
            value="Processing"
            severity="warning"
          />
          <Tag v-else-if="slotProps.data.document" :value="slotProps.data.document.processing_status" />
        </template>
      </Column>

      <Column header="Actions">
        <template #body="slotProps">
          <Button
            icon="pi pi-eye"
            label="View"
            class="p-button-sm"
            @click="viewDocument(slotProps.data)"
          />
        </template>
      </Column>

      <template #empty>
        <div class="text-center py-8 text-gray-500">
          <i class="pi pi-inbox text-4xl mb-3"></i>
          <p>No documents have been shared with you yet.</p>
        </div>
      </template>
    </DataTable>
    </div>
  </div>
</template>

<style scoped>
.shared-documents-view {
  max-width: 1200px;
  margin: 0 auto;
}
</style>
