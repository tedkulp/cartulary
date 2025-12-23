<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useToast } from 'primevue/usetoast'
import AppHeader from '@/components/AppHeader.vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Dropdown from 'primevue/dropdown'
import Checkbox from 'primevue/checkbox'
import Tag from 'primevue/tag'
import { importSourceService } from '@/services/importSourceService'
import { ImportSourceType, ImportSourceStatus } from '@/types/importSource'
import type { ImportSource, ImportSourceCreate } from '@/types/importSource'

const toast = useToast()

// State
const importSources = ref<ImportSource[]>([])
const loading = ref(false)
const showDialog = ref(false)
const editingSource = ref<ImportSource | null>(null)

// Form data
const formData = ref<ImportSourceCreate>({
  name: '',
  source_type: ImportSourceType.DIRECTORY,
  status: ImportSourceStatus.ACTIVE,
  watch_path: null,
  move_after_import: false,
  move_to_path: null,
  delete_after_import: false,
  imap_server: null,
  imap_port: null,
  imap_username: null,
  imap_password: null,
  imap_use_ssl: true,
  imap_mailbox: 'INBOX',
  imap_processed_folder: null
})

// Options
const sourceTypeOptions = [
  { label: 'Directory', value: ImportSourceType.DIRECTORY },
  { label: 'IMAP Email', value: ImportSourceType.IMAP }
]

const statusOptions = [
  { label: 'Active', value: ImportSourceStatus.ACTIVE },
  { label: 'Paused', value: ImportSourceStatus.PAUSED },
  { label: 'Error', value: ImportSourceStatus.ERROR }
]

// Methods
const loadImportSources = async () => {
  loading.value = true
  try {
    importSources.value = await importSourceService.list()
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: error.response?.data?.detail || 'Failed to load import sources',
      life: 3000
    })
  } finally {
    loading.value = false
  }
}

const openCreateDialog = () => {
  editingSource.value = null
  formData.value = {
    name: '',
    source_type: ImportSourceType.DIRECTORY,
    status: ImportSourceStatus.ACTIVE,
    watch_path: null,
    move_after_import: false,
    move_to_path: null,
    delete_after_import: false,
    imap_server: null,
    imap_port: null,
    imap_username: null,
    imap_password: null,
    imap_use_ssl: true,
    imap_mailbox: 'INBOX',
    imap_processed_folder: null
  }
  showDialog.value = true
}

const openEditDialog = (source: ImportSource) => {
  editingSource.value = source
  formData.value = {
    name: source.name,
    source_type: source.source_type,
    status: source.status,
    watch_path: source.watch_path,
    move_after_import: source.move_after_import,
    move_to_path: source.move_to_path,
    delete_after_import: source.delete_after_import,
    imap_server: source.imap_server,
    imap_port: source.imap_port,
    imap_username: source.imap_username,
    imap_password: null, // Don't populate password for security
    imap_use_ssl: source.imap_use_ssl,
    imap_mailbox: source.imap_mailbox,
    imap_processed_folder: source.imap_processed_folder
  }
  showDialog.value = true
}

const saveImportSource = async () => {
  try {
    if (editingSource.value) {
      // Update existing source
      await importSourceService.update(editingSource.value.id, formData.value)
      toast.add({
        severity: 'success',
        summary: 'Success',
        detail: 'Import source updated successfully',
        life: 3000
      })
    } else {
      // Create new source
      await importSourceService.create(formData.value)
      toast.add({
        severity: 'success',
        summary: 'Success',
        detail: 'Import source created successfully',
        life: 3000
      })
    }
    showDialog.value = false
    await loadImportSources()
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: error.response?.data?.detail || 'Failed to save import source',
      life: 3000
    })
  }
}

const deleteImportSource = async (source: ImportSource) => {
  if (!confirm(`Are you sure you want to delete "${source.name}"?`)) {
    return
  }

  try {
    await importSourceService.delete(source.id)
    toast.add({
      severity: 'success',
      summary: 'Success',
      detail: 'Import source deleted successfully',
      life: 3000
    })
    await loadImportSources()
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: error.response?.data?.detail || 'Failed to delete import source',
      life: 3000
    })
  }
}

const getStatusSeverity = (status: ImportSourceStatus) => {
  switch (status) {
    case ImportSourceStatus.ACTIVE:
      return 'success'
    case ImportSourceStatus.PAUSED:
      return 'warn'
    case ImportSourceStatus.ERROR:
      return 'danger'
    default:
      return 'info'
  }
}

onMounted(() => {
  loadImportSources()
})
</script>

<template>
  <div class="min-h-screen bg-gray-50">
    <AppHeader />

    <main class="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
      <div class="px-4 sm:px-0">
        <div class="flex justify-between items-center mb-6">
          <h2 class="text-2xl font-bold text-gray-900">Settings</h2>
        </div>

        <!-- Import Sources Section -->
        <div class="bg-white shadow rounded-lg p-6 mb-6">
          <div class="flex justify-between items-center mb-4">
            <h3 class="text-lg font-semibold text-gray-900">Import Sources</h3>
            <Button label="Add Import Source" icon="pi pi-plus" @click="openCreateDialog" />
          </div>

          <DataTable
            :value="importSources"
            :loading="loading"
            stripedRows
            showGridlines
            :paginator="true"
            :rows="10"
            class="mt-4"
          >
            <Column field="name" header="Name" sortable>
              <template #body="slotProps">
                <div class="font-semibold">{{ slotProps.data.name }}</div>
              </template>
            </Column>

            <Column field="source_type" header="Type" sortable>
              <template #body="slotProps">
                <Tag
                  :value="slotProps.data.source_type === ImportSourceType.DIRECTORY ? 'Directory' : 'IMAP Email'"
                  :severity="slotProps.data.source_type === ImportSourceType.DIRECTORY ? 'info' : 'primary'"
                />
              </template>
            </Column>

            <Column field="watch_path" header="Path/Server">
              <template #body="slotProps">
                <span v-if="slotProps.data.source_type === ImportSourceType.DIRECTORY">
                  {{ slotProps.data.watch_path || '-' }}
                </span>
                <span v-else>
                  {{ slotProps.data.imap_server || '-' }}
                </span>
              </template>
            </Column>

            <Column field="status" header="Status" sortable>
              <template #body="slotProps">
                <Tag
                  :value="slotProps.data.status"
                  :severity="getStatusSeverity(slotProps.data.status)"
                />
              </template>
            </Column>

            <Column field="last_run" header="Last Run" sortable>
              <template #body="slotProps">
                <span v-if="slotProps.data.last_run">
                  {{ new Date(slotProps.data.last_run).toLocaleString() }}
                </span>
                <span v-else class="text-gray-400">Never</span>
              </template>
            </Column>

            <Column header="Actions">
              <template #body="slotProps">
                <div class="flex gap-2">
                  <Button
                    icon="pi pi-pencil"
                    severity="secondary"
                    outlined
                    @click="openEditDialog(slotProps.data)"
                  />
                  <Button
                    icon="pi pi-trash"
                    severity="danger"
                    outlined
                    @click="deleteImportSource(slotProps.data)"
                  />
                </div>
              </template>
            </Column>
          </DataTable>
        </div>
      </div>
    </main>

    <!-- Create/Edit Dialog -->
    <Dialog
      v-model:visible="showDialog"
      :header="editingSource ? 'Edit Import Source' : 'Create Import Source'"
      :modal="true"
      :style="{ width: '50rem' }"
    >
      <div class="space-y-4">
        <!-- Name -->
        <div>
          <label for="name" class="block text-sm font-medium text-gray-700 mb-2">Name</label>
          <InputText
            id="name"
            v-model="formData.name"
            class="w-full"
            placeholder="My Import Source"
          />
        </div>

        <!-- Source Type -->
        <div>
          <label for="source_type" class="block text-sm font-medium text-gray-700 mb-2">
            Source Type
          </label>
          <Dropdown
            id="source_type"
            v-model="formData.source_type"
            :options="sourceTypeOptions"
            optionLabel="label"
            optionValue="value"
            class="w-full"
            :disabled="!!editingSource"
          />
        </div>

        <!-- Status -->
        <div>
          <label for="status" class="block text-sm font-medium text-gray-700 mb-2">Status</label>
          <Dropdown
            id="status"
            v-model="formData.status"
            :options="statusOptions"
            optionLabel="label"
            optionValue="value"
            class="w-full"
          />
        </div>

        <!-- Directory Fields -->
        <template v-if="formData.source_type === ImportSourceType.DIRECTORY">
          <div>
            <label for="watch_path" class="block text-sm font-medium text-gray-700 mb-2">
              Watch Path
            </label>
            <InputText
              id="watch_path"
              v-model="formData.watch_path"
              class="w-full"
              placeholder="/path/to/watch"
            />
          </div>

          <div class="flex items-center gap-2">
            <Checkbox
              id="move_after_import"
              v-model="formData.move_after_import"
              :binary="true"
            />
            <label for="move_after_import" class="text-sm font-medium text-gray-700">
              Move files after import
            </label>
          </div>

          <div v-if="formData.move_after_import">
            <label for="move_to_path" class="block text-sm font-medium text-gray-700 mb-2">
              Move To Path
            </label>
            <InputText
              id="move_to_path"
              v-model="formData.move_to_path"
              class="w-full"
              placeholder="/path/to/move"
            />
          </div>

          <div class="flex items-center gap-2">
            <Checkbox
              id="delete_after_import"
              v-model="formData.delete_after_import"
              :binary="true"
            />
            <label for="delete_after_import" class="text-sm font-medium text-gray-700">
              Delete files after import
            </label>
          </div>
        </template>

        <!-- IMAP Fields -->
        <template v-if="formData.source_type === ImportSourceType.IMAP">
          <div>
            <label for="imap_server" class="block text-sm font-medium text-gray-700 mb-2">
              IMAP Server
            </label>
            <InputText
              id="imap_server"
              v-model="formData.imap_server"
              class="w-full"
              placeholder="imap.gmail.com"
            />
          </div>

          <div>
            <label for="imap_port" class="block text-sm font-medium text-gray-700 mb-2">
              IMAP Port
            </label>
            <InputText
              id="imap_port"
              v-model.number="formData.imap_port"
              class="w-full"
              placeholder="993"
              type="number"
            />
          </div>

          <div>
            <label for="imap_username" class="block text-sm font-medium text-gray-700 mb-2">
              Username
            </label>
            <InputText
              id="imap_username"
              v-model="formData.imap_username"
              class="w-full"
              placeholder="user@example.com"
            />
          </div>

          <div>
            <label for="imap_password" class="block text-sm font-medium text-gray-700 mb-2">
              Password
            </label>
            <InputText
              id="imap_password"
              v-model="formData.imap_password"
              class="w-full"
              type="password"
              :placeholder="editingSource ? 'Leave blank to keep current password' : 'Password'"
            />
          </div>

          <div class="flex items-center gap-2">
            <Checkbox id="imap_use_ssl" v-model="formData.imap_use_ssl" :binary="true" />
            <label for="imap_use_ssl" class="text-sm font-medium text-gray-700">Use SSL</label>
          </div>

          <div>
            <label for="imap_mailbox" class="block text-sm font-medium text-gray-700 mb-2">
              Mailbox
            </label>
            <InputText
              id="imap_mailbox"
              v-model="formData.imap_mailbox"
              class="w-full"
              placeholder="INBOX"
            />
          </div>

          <div>
            <label for="imap_processed_folder" class="block text-sm font-medium text-gray-700 mb-2">
              Processed Folder (optional)
            </label>
            <InputText
              id="imap_processed_folder"
              v-model="formData.imap_processed_folder"
              class="w-full"
              placeholder="Processed"
            />
          </div>
        </template>
      </div>

      <template #footer>
        <Button label="Cancel" severity="secondary" outlined @click="showDialog = false" />
        <Button label="Save" @click="saveImportSource" />
      </template>
    </Dialog>
  </div>
</template>
