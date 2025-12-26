<script setup lang="ts">
import { ref, onMounted } from 'vue'
import Card from 'primevue/card'
import Skeleton from 'primevue/skeleton'
import { documentService } from '@/services/documentService'
import type { Document } from '@/types/document'
import { formatRelativeTime } from '@/utils/dateFormat'

const recentDocuments = ref<Document[]>([])
const loading = ref(true)

const loadRecentDocuments = async () => {
  try {
    const docs = await documentService.list()
    // Get the 5 most recent documents
    recentDocuments.value = docs
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
      .slice(0, 5)
  } catch (error) {
    console.error('Failed to load recent documents:', error)
  } finally {
    loading.value = false
  }
}

const formatDate = (dateString: string): string => {
  return formatRelativeTime(dateString)
}

const getStatusIcon = (status: string): string => {
  if (status === 'pending' || status === 'processing') return 'pi-clock'
  if (status.includes('failed')) return 'pi-exclamation-circle'
  return 'pi-check-circle'
}

const getStatusColor = (status: string): string => {
  if (status === 'pending' || status === 'processing') return 'text-blue-500'
  if (status.includes('failed')) return 'text-red-500'
  return 'text-green-500'
}

onMounted(() => {
  loadRecentDocuments()
})
</script>

<template>
  <Card>
    <template #title>
      <span>Recent Documents</span>
    </template>
    <template #content>
      <!-- Loading State -->
      <div v-if="loading" class="space-y-3">
        <div v-for="i in 5" :key="i" class="flex items-center gap-3">
          <Skeleton shape="circle" size="2.5rem" />
          <div class="flex-1">
            <Skeleton width="70%" height="1rem" class="mb-2" />
            <Skeleton width="40%" height="0.75rem" />
          </div>
        </div>
      </div>

      <!-- Empty State -->
      <div v-else-if="recentDocuments.length === 0" class="text-center py-8 text-muted-color">
        <i class="pi pi-file text-4xl mb-3"></i>
        <p>No documents yet</p>
      </div>

      <!-- Documents List -->
      <div v-else class="space-y-3">
        <div
          v-for="doc in recentDocuments"
          :key="doc.id"
        >
          <RouterLink
            :to="`/documents/${doc.id}`"
            class="flex items-start gap-3 p-3 rounded hover:bg-surface-100 dark:hover:bg-surface-800 cursor-pointer transition-colors"
            style="text-decoration: none; color: inherit"
          >
            <!-- Status Icon -->
            <i
              :class="['pi', getStatusIcon(doc.processing_status), getStatusColor(doc.processing_status), 'text-xl']"
            ></i>

            <!-- Document Info -->
            <div class="flex-1 min-w-0">
              <div class="font-medium truncate">{{ doc.title }}</div>
              <div class="text-sm text-muted-color">{{ formatDate(doc.created_at) }}</div>
            </div>

            <!-- Arrow Icon -->
            <i class="pi pi-chevron-right text-muted-color"></i>
          </RouterLink>
        </div>
      </div>
    </template>
  </Card>
</template>

