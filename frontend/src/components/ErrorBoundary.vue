<script setup lang="ts">
import { ref, onErrorCaptured } from 'vue'
import Button from 'primevue/button'
import Message from 'primevue/message'

const error = ref<Error | null>(null)
const errorInfo = ref<string>('')

onErrorCaptured((err, instance, info) => {
  error.value = err
  errorInfo.value = info
  console.error('Error caught by boundary:', err, info)
  // Prevent error from propagating
  return false
})

const reset = () => {
  error.value = null
  errorInfo.value = ''
}
</script>

<template>
  <div v-if="error" class="p-6 max-w-2xl mx-auto">
    <Message severity="error" :closable="false" class="mb-4">
      <div class="flex flex-col gap-4">
        <div>
          <h3 class="font-semibold text-lg mb-2">Something went wrong</h3>
          <p class="text-sm mb-2">{{ error.message }}</p>
          <details v-if="errorInfo" class="text-xs">
            <summary class="cursor-pointer">Technical details</summary>
            <pre class="mt-2 p-2 bg-gray-100 dark:bg-gray-800 rounded overflow-auto">{{ errorInfo }}</pre>
          </details>
        </div>
        <div class="flex gap-2">
          <Button label="Try Again" icon="pi pi-refresh" @click="reset" size="small" />
          <Button label="Go Home" icon="pi pi-home" @click="$router.push('/')" severity="secondary" outlined size="small" />
        </div>
      </div>
    </Message>
  </div>
  <slot v-else />
</template>
