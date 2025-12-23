<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import Button from 'primevue/button'

const router = useRouter()
const authStore = useAuthStore()

const handleLogout = () => {
  authStore.logout()
  router.push('/login')
}
</script>

<template>
  <header class="bg-white shadow">
    <div class="max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8 flex justify-between items-center">
      <h1 class="text-2xl font-bold text-gray-900 cursor-pointer" @click="router.push('/')">
        Trapper
      </h1>
      <div class="flex items-center gap-4">
        <div class="text-sm text-gray-600">
          Welcome, <span class="font-medium">{{ authStore.user?.email }}</span>
        </div>
        <Button
          label="Documents"
          icon="pi pi-file"
          @click="router.push('/documents')"
        />
        <Button
          label="Shared"
          icon="pi pi-share-alt"
          @click="router.push('/shared')"
          severity="secondary"
          outlined
        />
        <Button
          v-if="authStore.isSuperuser"
          label="Admin"
          icon="pi pi-users"
          @click="router.push('/admin')"
          severity="secondary"
          outlined
        />
        <Button
          label="Settings"
          icon="pi pi-cog"
          @click="router.push('/settings')"
          severity="secondary"
          outlined
        />
        <Button
          label="Logout"
          icon="pi pi-sign-out"
          severity="secondary"
          outlined
          @click="handleLogout"
        />
      </div>
    </div>
  </header>
</template>
