<script setup lang="ts">
import Button from 'primevue/button'
import Card from 'primevue/card'

defineProps<{
  icon?: string
  title: string
  description?: string
  actionLabel?: string
  actionIcon?: string
}>()

const emit = defineEmits<{
  action: []
}>()
</script>

<template>
  <Card>
    <template #content>
      <div class="flex flex-col items-center justify-center py-12 px-4 text-center p-component">
        <i v-if="icon" :class="icon" class="text-6xl text-muted-color mb-4"></i>
        <h3 class="text-xl font-semibold mb-2">{{ title }}</h3>
        <p v-if="description" class="text-muted-color mb-6 max-w-md">{{ description }}</p>
        <Button
          v-if="actionLabel"
          :label="actionLabel"
          :icon="actionIcon"
          @click="emit('action')"
        />
      </div>
   </template>
  </Card>
</template>
