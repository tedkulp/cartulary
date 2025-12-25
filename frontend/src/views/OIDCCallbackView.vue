<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useToast } from 'primevue/usetoast'
import { authService } from '@/services/authService'

const router = useRouter()
const route = useRoute()
const toast = useToast()
const loading = ref(true)
const error = ref<string | null>(null)

onMounted(async () => {
  try {
    // Get code and state from query parameters
    const code = route.query.code as string
    const state = route.query.state as string

    if (!code || !state) {
      throw new Error('Missing authorization code or state parameter')
    }

    // Exchange code for tokens
    const tokenResponse = await authService.handleOIDCCallback(code, state)

    // Store tokens
    localStorage.setItem('access_token', tokenResponse.access_token)
    if (tokenResponse.refresh_token) {
      localStorage.setItem('refresh_token', tokenResponse.refresh_token)
    }

    // Show success message
    toast.add({
      severity: 'success',
      summary: 'Login Successful',
      detail: 'You have been successfully logged in via OIDC',
      life: 3000
    })

    // Redirect to documents page
    router.push('/documents')
  } catch (err: any) {
    console.error('OIDC callback error:', err)
    error.value = err.response?.data?.detail || err.message || 'Authentication failed'

    toast.add({
      severity: 'error',
      summary: 'Authentication Failed',
      detail: error.value,
      life: 5000
    })

    // Redirect to login page after error
    setTimeout(() => {
      router.push('/login')
    }, 3000)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="flex items-center justify-center min-h-screen bg-gray-100">
    <div class="bg-white p-8 rounded-lg shadow-md max-w-md w-full text-center">
      <div v-if="loading" class="space-y-4">
        <i class="pi pi-spin pi-spinner text-4xl text-blue-500"></i>
        <h2 class="text-xl font-semibold text-gray-800">Authenticating...</h2>
        <p class="text-gray-600">Please wait while we complete your login</p>
      </div>

      <div v-else-if="error" class="space-y-4">
        <i class="pi pi-times-circle text-4xl text-red-500"></i>
        <h2 class="text-xl font-semibold text-gray-800">Authentication Failed</h2>
        <p class="text-gray-600">{{ error }}</p>
        <p class="text-sm text-gray-500">Redirecting to login page...</p>
      </div>

      <div v-else class="space-y-4">
        <i class="pi pi-check-circle text-4xl text-green-500"></i>
        <h2 class="text-xl font-semibold text-gray-800">Success!</h2>
        <p class="text-gray-600">Redirecting to dashboard...</p>
      </div>
    </div>
  </div>
</template>
