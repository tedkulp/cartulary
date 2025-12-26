<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import Button from 'primevue/button'
import Message from 'primevue/message'

const router = useRouter()
const authStore = useAuthStore()

const email = ref('')
const password = ref('')
const fullName = ref('')

const handleRegister = async () => {
  authStore.clearError()

  const success = await authStore.register({
    email: email.value,
    password: password.value,
    full_name: fullName.value || undefined,
  })

  if (success) {
    router.push('/')
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center px-4">
    <div class="max-w-md w-full rounded-lg shadow-lg p-8">
      <div class="text-center mb-8">
        <h1 class="text-3xl font-bold mb-2">Trapper</h1>
        <p class="text-muted-color">Create your account</p>
      </div>

      <Message v-if="authStore.error" severity="error" :closable="false" class="mb-4">
        {{ authStore.error }}
      </Message>

      <form @submit.prevent="handleRegister" class="space-y-6">
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
          <label for="fullName" class="block text-sm font-medium">
            Full Name (Optional)
          </label>
          <InputText
            id="fullName"
            v-model="fullName"
            placeholder="Your full name"
            class="w-full"
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
            placeholder="Enter your password (8-32 characters)"
            class="w-full"
            toggleMask
            required
            minlength="8"
            maxlength="32"
            :disabled="authStore.loading"
            :pt="{
              input: { class: 'w-full' }
            }"
          />
        </div>

        <Button
          type="submit"
          label="Create Account"
          class="w-full"
          :loading="authStore.loading"
          :disabled="authStore.loading"
        />

        <div class="text-center text-sm text-muted-color">
          Already have an account?
          <RouterLink to="/login" class="font-medium">
            Sign in here
          </RouterLink>
        </div>
      </form>
    </div>
  </div>
</template>

<style scoped>
:deep(.p-inputtext),
:deep(.p-password-input) {
  width: 100%;
}
</style>
