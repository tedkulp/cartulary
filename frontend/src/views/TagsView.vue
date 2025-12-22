<script setup lang="ts">
import { ref, onMounted } from 'vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Card from 'primevue/card'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'
import ConfirmDialog from 'primevue/confirmdialog'
import { useConfirm } from 'primevue/useconfirm'
import { useToast } from 'primevue/usetoast'
import { tagService, type Tag, type TagCreate } from '@/services/tagService'

const confirm = useConfirm()
const toast = useToast()

const tags = ref<Tag[]>([])
const loading = ref(false)
const showDialog = ref(false)
const editingTag = ref<Tag | null>(null)

const tagForm = ref<TagCreate>({
  name: '',
  color: '#6366f1',
  description: '',
})

const loadTags = async () => {
  loading.value = true
  try {
    tags.value = await tagService.list()
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to load tags',
      life: 3000,
    })
  } finally {
    loading.value = false
  }
}

const openCreateDialog = () => {
  editingTag.value = null
  tagForm.value = {
    name: '',
    color: '#6366f1',
    description: '',
  }
  showDialog.value = true
}

const openEditDialog = (tag: Tag) => {
  editingTag.value = tag
  tagForm.value = {
    name: tag.name,
    color: tag.color || '#6366f1',
    description: tag.description || '',
  }
  showDialog.value = true
}

const saveTag = async () => {
  try {
    if (editingTag.value) {
      await tagService.update(editingTag.value.id, tagForm.value)
      toast.add({
        severity: 'success',
        summary: 'Success',
        detail: 'Tag updated successfully',
        life: 3000,
      })
    } else {
      await tagService.create(tagForm.value)
      toast.add({
        severity: 'success',
        summary: 'Success',
        detail: 'Tag created successfully',
        life: 3000,
      })
    }
    showDialog.value = false
    loadTags()
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: error.response?.data?.detail || 'Failed to save tag',
      life: 3000,
    })
  }
}

const handleDelete = (tag: Tag) => {
  confirm.require({
    message: `Are you sure you want to delete "${tag.name}"?`,
    header: 'Confirm Delete',
    icon: 'pi pi-exclamation-triangle',
    accept: async () => {
      try {
        await tagService.delete(tag.id)
        toast.add({
          severity: 'success',
          summary: 'Success',
          detail: 'Tag deleted successfully',
          life: 3000,
        })
        loadTags()
      } catch (error: any) {
        toast.add({
          severity: 'error',
          summary: 'Error',
          detail: 'Failed to delete tag',
          life: 3000,
        })
      }
    },
  })
}

onMounted(() => {
  loadTags()
})
</script>

<template>
  <div class="tags-view p-6 max-w-7xl mx-auto">
    <ConfirmDialog />

    <div class="mb-6 flex items-center justify-between">
      <div>
        <h1 class="text-3xl font-bold text-gray-900 mb-2">Tags</h1>
        <p class="text-gray-600">Organize your documents with tags</p>
      </div>
      <Button label="Create Tag" icon="pi pi-plus" @click="openCreateDialog" />
    </div>

    <Card>
      <template #content>
        <DataTable
          :value="tags"
          :loading="loading"
          striped-rows
          paginator
          :rows="25"
          :rows-per-page-options="[25, 50, 100]"
        >
          <template #empty>
            <div class="text-center py-8 text-gray-500">
              No tags created yet. Create your first tag to organize documents.
            </div>
          </template>

          <Column field="name" header="Name" sortable>
            <template #body="{ data }">
              <div class="flex items-center gap-2">
                <span
                  :style="{ backgroundColor: data.color || '#6366f1' }"
                  class="w-4 h-4 rounded"
                ></span>
                <span class="font-medium">{{ data.name }}</span>
              </div>
            </template>
          </Column>

          <Column field="description" header="Description">
            <template #body="{ data }">
              <span class="text-sm text-gray-600">{{
                data.description || 'No description'
              }}</span>
            </template>
          </Column>

          <Column field="color" header="Color">
            <template #body="{ data }">
              <span class="text-sm font-mono">{{ data.color || '#6366f1' }}</span>
            </template>
          </Column>

          <Column header="Actions">
            <template #body="{ data }">
              <div class="flex gap-2">
                <Button
                  icon="pi pi-pencil"
                  severity="info"
                  text
                  rounded
                  @click="openEditDialog(data)"
                />
                <Button
                  icon="pi pi-trash"
                  severity="danger"
                  text
                  rounded
                  @click="handleDelete(data)"
                />
              </div>
            </template>
          </Column>
        </DataTable>
      </template>
    </Card>

    <!-- Create/Edit Dialog -->
    <Dialog
      v-model:visible="showDialog"
      :header="editingTag ? 'Edit Tag' : 'Create Tag'"
      :modal="true"
      :style="{ width: '450px' }"
    >
      <div class="flex flex-col gap-4">
        <div>
          <label for="name" class="block text-sm font-medium text-gray-700 mb-1">
            Name *
          </label>
          <InputText
            id="name"
            v-model="tagForm.name"
            class="w-full"
            placeholder="Enter tag name"
          />
        </div>

        <div>
          <label for="color" class="block text-sm font-medium text-gray-700 mb-1">
            Color
          </label>
          <div class="flex gap-2 items-center">
            <input
              id="color"
              v-model="tagForm.color"
              type="color"
              class="h-10 w-20 border border-gray-300 rounded"
            />
            <InputText v-model="tagForm.color" class="flex-1" placeholder="#6366f1" />
          </div>
        </div>

        <div>
          <label for="description" class="block text-sm font-medium text-gray-700 mb-1">
            Description
          </label>
          <Textarea
            id="description"
            v-model="tagForm.description"
            rows="3"
            class="w-full"
            placeholder="Enter tag description (optional)"
          />
        </div>
      </div>

      <template #footer>
        <Button label="Cancel" severity="secondary" @click="showDialog = false" />
        <Button label="Save" @click="saveTag" :disabled="!tagForm.name" />
      </template>
    </Dialog>
  </div>
</template>
