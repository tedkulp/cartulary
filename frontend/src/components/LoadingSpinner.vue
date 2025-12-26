<script setup lang="ts">
import { computed } from 'vue'
import ProgressSpinner from 'primevue/progressspinner'

const props = withDefaults(defineProps<{
  size?: 'small' | 'medium' | 'large'
  message?: string
  fullPage?: boolean
}>(), {
  size: 'medium',
  fullPage: false
})

const spinnerSize = computed(() => {
  switch (props.size) {
    case 'small': return '30px'
    case 'large': return '80px'
    default: return '50px'
  }
})
</script>

<template>
  <div
    :class="[
      'flex flex-col items-center justify-center gap-4',
      fullPage ? 'min-h-screen' : 'py-12'
    ]"
  >
    <ProgressSpinner
      :style="{ width: spinnerSize, height: spinnerSize }"
      strokeWidth="4"
    />
    <p v-if="message" class="text-muted-color">{{ message }}</p>
  </div>
</template>
