<script setup lang="ts">
import Skeleton from 'primevue/skeleton'

const props = withDefaults(defineProps<{
  rows?: number
}>(), {
  rows: 5
})
</script>

<template>
  <div class="space-y-4">
    <div
      v-for="i in rows"
      :key="i"
      class="flex items-center gap-4 p-4 border rounded"
    >
      <!-- Icon -->
      <Skeleton shape="circle" size="3rem" />

      <!-- Content -->
      <div class="flex-1 space-y-2">
        <Skeleton width="60%" height="1.5rem" />
        <Skeleton width="40%" height="1rem" />
      </div>

      <!-- Actions -->
      <div class="flex gap-2">
        <Skeleton width="2rem" height="2rem" borderRadius="50%" />
        <Skeleton width="2rem" height="2rem" borderRadius="50%" />
      </div>
    </div>
  </div>
</template>
