<script setup lang="ts">
import { ref, onMounted } from 'vue'

const appName = ref('Trapper')
const status = ref('Checking...')

onMounted(async () => {
  try {
    const response = await fetch('/api/v1/')
    const data = await response.json()
    status.value = data.status
  } catch (error) {
    status.value = 'Error connecting to backend'
  }
})
</script>

<template>
  <div class="min-h-screen flex items-center justify-center">
    <div class="text-center">
      <h1 class="text-6xl font-bold text-gray-900 mb-4">
        {{ appName }}
      </h1>
      <p class="text-2xl text-gray-600 mb-8">
        Document Management System
      </p>
      <div class="inline-block px-6 py-3 bg-blue-100 rounded-lg">
        <p class="text-lg text-blue-800">
          Status: <span class="font-semibold">{{ status }}</span>
        </p>
      </div>
      <div class="mt-8 text-gray-500">
        <p>Phase 1: Project Scaffolding Complete</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
</style>
