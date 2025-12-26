<script setup lang="ts">
import { RouterView } from 'vue-router'
import Toast from 'primevue/toast'
</script>

<template>
  <div id="app" class="min-h-screen">
    <Toast />
    <RouterView />
  </div>
</template>

<style scoped>
</style>
