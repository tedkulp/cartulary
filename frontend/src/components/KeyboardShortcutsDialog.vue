<script setup lang="ts">
import { ref } from 'vue'
import Dialog from 'primevue/dialog'
import { useKeyboardShortcuts } from '@/composables/useKeyboardShortcuts'

const visible = defineModel<boolean>('visible', { default: false })

const shortcuts = [
  { keys: 'Ctrl + D', description: 'Go to Documents' },
  { keys: 'Ctrl + T', description: 'Go to Tags' },
  { keys: 'Ctrl + S', description: 'Go to Settings' },
  { keys: 'Ctrl + H', description: 'Go to Home' },
  { keys: 'Ctrl + /', description: 'Focus search' },
  { keys: '?', description: 'Show keyboard shortcuts' },
  { keys: 'Esc', description: 'Close dialog' }
]

// Show dialog with '?' key
useKeyboardShortcuts([
  {
    key: '?',
    shift: true,
    description: 'Show keyboard shortcuts',
    action: () => {
      visible.value = true
    }
  }
])
</script>

<template>
  <Dialog
    v-model:visible="visible"
    header="Keyboard Shortcuts"
    :modal="true"
    :style="{ width: '600px' }"
  >
    <div class="space-y-3">
      <div
        v-for="(shortcut, index) in shortcuts"
        :key="index"
        class="flex justify-between items-center py-2 border-b last:border-b-0"
      >
        <span class="text-sm">{{ shortcut.description }}</span>
        <kbd class="px-2 py-1 text-xs font-semibold rounded border">
          {{ shortcut.keys }}
        </kbd>
      </div>
    </div>

    <template #footer>
      <div class="text-sm text-muted-color">
        Press <kbd class="px-2 py-1 text-xs font-semibold rounded border">?</kbd> anytime to show this dialog
      </div>
    </template>
  </Dialog>
</template>

<style scoped>
kbd {
  background-color: var(--p-surface-100);
  border-color: var(--p-surface-300);
  color: var(--p-text-color);
}
</style>
