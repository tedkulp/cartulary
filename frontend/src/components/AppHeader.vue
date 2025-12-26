<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useTheme } from '@/composables/useTheme'
import { useGlobalShortcuts } from '@/composables/useKeyboardShortcuts'
import Button from 'primevue/button'
import KeyboardShortcutsDialog from './KeyboardShortcutsDialog.vue'

const router = useRouter()
const authStore = useAuthStore()
const { isDark, toggleTheme } = useTheme()
const showShortcuts = ref(false)

// Enable global keyboard shortcuts
useGlobalShortcuts()

const handleLogout = () => {
  authStore.logout()
  router.push('/login')
}
</script>

<template>
  <header class="shadow border-b">
    <div class="max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8">
      <div class="flex justify-between items-center">
        <h1 class="text-2xl font-bold cursor-pointer" @click="router.push('/')">
          Trapper
        </h1>
        <div class="flex items-center gap-4">
          <div class="text-sm">
            Welcome, <span class="font-medium">{{ authStore.user?.email }}</span>
          </div>
          <Button
            label="Documents"
            icon="pi pi-file"
            @click="router.push('/documents')"
            v-tooltip.bottom="'Go to Documents (Ctrl+D)'"
          />
          <Button
            label="Shared"
            icon="pi pi-share-alt"
            @click="router.push('/shared')"
            severity="secondary"
            outlined
            v-tooltip.bottom="'View shared documents'"
          />
          <Button
            v-if="authStore.isSuperuser"
            label="Admin"
            icon="pi pi-users"
            @click="router.push('/admin')"
            severity="secondary"
            outlined
            v-tooltip.bottom="'Administration panel'"
          />
          <Button
            label="Settings"
            icon="pi pi-cog"
            @click="router.push('/settings')"
            severity="secondary"
            outlined
            v-tooltip.bottom="'Settings (Ctrl+S)'"
          />
          <Button
            icon="pi pi-question-circle"
            @click="showShortcuts = true"
            severity="secondary"
            outlined
            v-tooltip.bottom="'Keyboard shortcuts (?)'"
            rounded
          />
          <Button
            :icon="isDark ? 'pi pi-sun' : 'pi pi-moon'"
            @click="toggleTheme"
            severity="secondary"
            outlined
            v-tooltip.bottom="isDark ? 'Switch to light mode' : 'Switch to dark mode'"
            rounded
          />
          <Button
            label="Logout"
            icon="pi pi-sign-out"
            severity="secondary"
            outlined
            @click="handleLogout"
            v-tooltip.bottom="'Sign out'"
          />
        </div>
      </div>
    </div>

    <!-- Keyboard Shortcuts Dialog -->
    <KeyboardShortcutsDialog v-model:visible="showShortcuts" />
  </header>
</template>
