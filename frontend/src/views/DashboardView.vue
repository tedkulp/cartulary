<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import Button from 'primevue/button'

const router = useRouter()
const authStore = useAuthStore()

const appName = ref('Trapper')
const backendStatus = ref('Checking...')

onMounted(async () => {
  try {
    const response = await fetch('/')
    const data = await response.json()
    backendStatus.value = data.status
  } catch (error) {
    backendStatus.value = 'Error connecting to backend'
    console.error('Backend connection error:', error)
  }
})

const handleLogout = () => {
  authStore.logout()
  router.push('/login')
}
</script>

<template>
  <div class="min-h-screen bg-gray-50">
    <!-- Header -->
    <header class="bg-white shadow">
      <div class="max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8 flex justify-between items-center">
        <h1 class="text-2xl font-bold text-gray-900">{{ appName }}</h1>
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
            label="Logout"
            icon="pi pi-sign-out"
            severity="secondary"
            outlined
            @click="handleLogout"
          />
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main class="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
      <div class="text-center">
        <h2 class="text-4xl font-bold text-gray-900 mb-4">
          Document Management System
        </h2>
        <p class="text-lg text-gray-600 mb-8">
          Your intelligent document organizer with OCR and AI-powered search
        </p>

        <!-- Status Card -->
        <div class="inline-block mb-8">
          <div class="bg-white rounded-lg shadow px-6 py-4">
            <div class="flex items-center gap-4">
              <div>
                <p class="text-sm text-gray-500">Backend Status</p>
                <p class="text-lg font-semibold" :class="backendStatus === 'running' ? 'text-green-600' : 'text-red-600'">
                  {{ backendStatus }}
                </p>
              </div>
              <div class="border-l border-gray-300 pl-4">
                <p class="text-sm text-gray-500">User Email</p>
                <p class="text-lg font-semibold text-gray-900">
                  {{ authStore.user?.email }}
                </p>
              </div>
              <div v-if="authStore.isSuperuser" class="border-l border-gray-300 pl-4">
                <p class="text-sm text-gray-500">Role</p>
                <p class="text-lg font-semibold text-purple-600">
                  Superuser
                </p>
              </div>
            </div>
          </div>
        </div>

        <!-- Implementation Status -->
        <div class="bg-blue-50 rounded-lg p-6 max-w-2xl mx-auto">
          <h3 class="text-lg font-semibold text-blue-900 mb-3">
            ✅ Phase 1 Progress
          </h3>
          <ul class="text-left text-sm text-blue-800 space-y-2">
            <li class="flex items-start">
              <span class="text-green-600 mr-2">✓</span>
              <span>Project scaffolding and Docker environment</span>
            </li>
            <li class="flex items-start">
              <span class="text-green-600 mr-2">✓</span>
              <span>Database schema with migrations</span>
            </li>
            <li class="flex items-start">
              <span class="text-green-600 mr-2">✓</span>
              <span>JWT authentication system</span>
            </li>
            <li class="flex items-start">
              <span class="text-green-600 mr-2">✓</span>
              <span>User registration and login</span>
            </li>
            <li class="flex items-start">
              <span class="text-green-600 mr-2">✓</span>
              <span>Basic document upload</span>
            </li>
          </ul>
          <div class="mt-4 flex gap-3 justify-center">
            <Button
              label="Go to Documents"
              icon="pi pi-file"
              @click="router.push('/documents')"
            />
            <Button
              label="Manage Tags"
              icon="pi pi-tags"
              severity="secondary"
              @click="router.push('/tags')"
            />
          </div>
        </div>

        <!-- Next Steps -->
        <div class="bg-gray-100 rounded-lg p-6 max-w-2xl mx-auto mt-6">
          <h3 class="text-lg font-semibold text-gray-900 mb-3">
            📋 Coming Soon
          </h3>
          <ul class="text-left text-sm text-gray-700 space-y-2">
            <li class="flex items-start">
              <span class="text-gray-400 mr-2">○</span>
              <span>OCR processing with PaddleOCR</span>
            </li>
            <li class="flex items-start">
              <span class="text-gray-400 mr-2">○</span>
              <span>Semantic search with RAG</span>
            </li>
            <li class="flex items-start">
              <span class="text-gray-400 mr-2">○</span>
              <span>LLM-based metadata extraction</span>
            </li>
          </ul>
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
</style>
