<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import Card from 'primevue/card'
import Timeline from 'primevue/timeline'
import Skeleton from 'primevue/skeleton'
import { activityService } from '@/services/activityService'
import type { ActivityLog } from '@/types/activity'
import { formatRelativeTime } from '@/utils/dateFormat'

const activities = ref<ActivityLog[]>([])
const loading = ref(true)

const loadActivities = async () => {
  try {
    const data = await activityService.getMyActivities({ limit: 10 })
    console.log('Loaded activities (raw):', data)

    // Filter out activities with invalid dates
    activities.value = data.filter(activity => {
      if (!activity.created_at) {
        console.warn('Activity without created_at:', activity)
        return false
      }
      const date = new Date(activity.created_at)
      if (isNaN(date.getTime())) {
        console.warn('Activity with invalid date:', activity.created_at, activity)
        return false
      }
      return true
    })

    console.log('Filtered activities:', activities.value)
  } catch (error) {
    console.error('Failed to load activities:', error)
  } finally {
    loading.value = false
  }
}

const getActionIcon = (action?: string): string => {
  if (!action) return 'pi-info-circle'
  if (action.includes('upload')) return 'pi-cloud-upload'
  if (action.includes('delete')) return 'pi-trash'
  if (action.includes('share')) return 'pi-share-alt'
  if (action.includes('login')) return 'pi-sign-in'
  if (action.includes('create')) return 'pi-plus'
  if (action.includes('update')) return 'pi-pencil'
  return 'pi-info-circle'
}

const getActionColor = (action?: string): string => {
  if (!action) return 'text-gray-500'
  if (action.includes('delete')) return 'text-red-500'
  if (action.includes('upload') || action.includes('create')) return 'text-green-500'
  if (action.includes('share')) return 'text-blue-500'
  if (action.includes('login')) return 'text-purple-500'
  return 'text-gray-500'
}


onMounted(() => {
  loadActivities()
})
</script>

<template>
  <Card>
    <template #title>Recent Activity</template>
    <template #content>
      <!-- Loading State -->
      <div v-if="loading" class="space-y-4">
        <div v-for="i in 5" :key="i" class="flex gap-3">
          <Skeleton shape="circle" size="2.5rem" />
          <div class="flex-1">
            <Skeleton width="70%" height="1rem" class="mb-2" />
            <Skeleton width="40%" height="0.75rem" />
          </div>
        </div>
      </div>

      <!-- Empty State -->
      <div v-else-if="!activities || activities.length === 0" class="text-center py-8 text-muted-color">
        <i class="pi pi-history text-4xl mb-3"></i>
        <p>No recent activity</p>
      </div>

      <!-- Timeline -->
      <Timeline v-else :value="activities" class="activity-timeline">
        <template #marker="{ item }">
          <div
            class="flex items-center justify-center w-8 h-8 rounded-full border-2"
            :class="getActionColor(item.action)"
            style="border-color: currentColor; background-color: var(--p-surface-0)"
          >
            <i :class="['pi', getActionIcon(item.action), 'text-sm']"></i>
          </div>
        </template>
        <template #content="{ item }">
          <div class="pb-4">
            <div class="font-medium">{{ item.description }}</div>
            <div class="text-sm text-muted-color mt-1">
              {{ formatRelativeTime(item.created_at) }}
            </div>
          </div>
        </template>
      </Timeline>
    </template>
  </Card>
</template>

<style scoped>
.activity-timeline :deep(.p-timeline-event-opposite) {
  display: none;
}

.activity-timeline :deep(.p-timeline) {
  padding-left: 0;
}
</style>
