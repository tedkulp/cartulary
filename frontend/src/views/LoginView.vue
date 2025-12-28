<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { authService } from '@/services/authService'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import Button from 'primevue/button'
import Message from 'primevue/message'
import Divider from 'primevue/divider'

const router = useRouter()
const authStore = useAuthStore()

const email = ref('')
const password = ref('')
const oidcEnabled = ref(false)
const oidcLoading = ref(true)

const handleLogin = async () => {
  authStore.clearError()

  const success = await authStore.login({
    email: email.value,
    password: password.value,
  })

  if (success) {
    router.push('/documents')
  }
}

const handleOIDCLogin = async () => {
  try {
    await authService.initiateOIDCLogin()
  } catch (err: any) {
    console.error('OIDC login error:', err)
    authStore.error = err.response?.data?.detail || 'Failed to initiate OIDC login'
  }
}

onMounted(async () => {
  try {
    const config = await authService.getOIDCConfig()
    oidcEnabled.value = config.enabled
  } catch (error) {
    console.error('Failed to fetch OIDC config:', error)
  } finally {
    oidcLoading.value = false
  }
})
</script>

<template>
  <div class="min-h-screen flex items-center justify-center px-4">
    <div class="max-w-md w-full rounded-lg shadow-lg p-8">
      <div class="text-center mb-8">
        <h1 class="text-3xl font-bold mb-2">Cartulary</h1>
        <p class="text-muted-color">Sign in to your digital archive</p>
      </div>

      <Message v-if="authStore.error" severity="error" :closable="false" class="mb-4">
        {{ authStore.error }}
      </Message>

      <form @submit.prevent="handleLogin" class="space-y-6">
        <div class="space-y-2">
          <label for="email" class="block text-sm font-medium">
            Email
          </label>
          <InputText
            id="email"
            v-model="email"
            type="email"
            placeholder="you@example.com"
            class="w-full"
            required
            :disabled="authStore.loading"
          />
        </div>

        <div class="space-y-2">
          <label for="password" class="block text-sm font-medium">
            Password
          </label>
          <Password
            id="password"
            v-model="password"
            placeholder="Enter your password"
            class="w-full"
            :feedback="false"
            toggleMask
            required
            maxlength="32"
            :disabled="authStore.loading"
            :pt="{
              input: { class: 'w-full' }
            }"
          />
        </div>

        <Button
          type="submit"
          label="Sign In"
          class="w-full"
          :loading="authStore.loading"
          :disabled="authStore.loading"
        />
      </form>

      <div v-if="!oidcLoading && oidcEnabled">
        <Divider align="center">
          <span class="text-sm text-muted-color">OR</span>
        </Divider>

        <Button
          type="button"
          label="Sign in with SSO"
          icon="pi pi-sign-in"
          class="w-full"
          outlined
          @click="handleOIDCLogin"
        />
      </div>

      <div class="text-center text-sm text-muted-color mt-6">
        Don't have an account?
        <RouterLink to="/register" class="font-medium">
          Register here
        </RouterLink>
      </div>
    </div>
  </div>
</template>

<style scoped>
:deep(.p-inputtext),
:deep(.p-password-input) {
  width: 100%;
}
</style>
