<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useToast } from 'primevue/usetoast'
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'
import Select from 'primevue/select'
import DatePicker from 'primevue/datepicker'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Tag from 'primevue/tag'
import sharingService from '@/services/sharingService'
import userService from '@/services/userService'
import type { DocumentShare, PermissionLevel } from '@/types/sharing'
import type { User } from '@/types/user'

const props = defineProps<{
  documentId: string
  visible: boolean
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  'shared': []
}>()

const toast = useToast()

const users = ref<User[]>([])
const shares = ref<DocumentShare[]>([])
const loading = ref(false)

const selectedUser = ref<User | null>(null)
const selectedPermission = ref<PermissionLevel>('read')
const expirationDate = ref<Date | null>(null)

const permissionOptions = [
  { label: 'Read Only', value: 'read' },
  { label: 'Read & Write', value: 'write' },
  { label: 'Admin', value: 'admin' }
]

const getPermissionSeverity = (level: string) => {
  switch (level) {
    case 'admin':
      return 'danger'
    case 'write':
      return 'warning'
    case 'read':
      return 'info'
    default:
      return null
  }
}

const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleDateString()
}

const getUserEmail = (userId: string) => {
  const user = users.value.find(u => u.id === userId)
  return user?.email || 'Unknown'
}

const loadData = async () => {
  loading.value = true
  try {
    const [usersData, sharesData] = await Promise.all([
      userService.listUsers(),
      sharingService.listDocumentShares(props.documentId)
    ])
    users.value = usersData
    shares.value = sharesData
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: error.response?.data?.detail || 'Failed to load sharing data',
      life: 3000
    })
  } finally {
    loading.value = false
  }
}

const shareDocument = async () => {
  if (!selectedUser.value) {
    toast.add({
      severity: 'warn',
      summary: 'Warning',
      detail: 'Please select a user',
      life: 3000
    })
    return
  }

  try {
    await sharingService.createDocumentShare(props.documentId, {
      shared_with_user_id: selectedUser.value.id,
      permission_level: selectedPermission.value,
      expires_at: expirationDate.value?.toISOString() || null
    })

    toast.add({
      severity: 'success',
      summary: 'Success',
      detail: 'Document shared successfully',
      life: 3000
    })

    selectedUser.value = null
    selectedPermission.value = 'read'
    expirationDate.value = null

    await loadData()
    emit('shared')
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: error.response?.data?.detail || 'Failed to share document',
      life: 3000
    })
  }
}

const revokeShare = async (share: DocumentShare) => {
  if (confirm('Are you sure you want to revoke this share?')) {
    try {
      await sharingService.deleteDocumentShare(share.id)
      toast.add({
        severity: 'success',
        summary: 'Success',
        detail: 'Share revoked successfully',
        life: 3000
      })
      await loadData()
    } catch (error: any) {
      toast.add({
        severity: 'error',
        summary: 'Error',
        detail: error.response?.data?.detail || 'Failed to revoke share',
        life: 3000
      })
    }
  }
}

const dialogVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value)
})

onMounted(() => {
  if (props.visible) {
    loadData()
  }
})
</script>

<template>
  <Dialog
    v-model:visible="dialogVisible"
    header="Share Document"
    :modal="true"
    :style="{ width: '800px' }"
    @show="loadData"
  >
    <div class="flex flex-col gap-6">
      <!-- Share Form -->
      <div class="border-b pb-4">
        <h3 class="font-semibold mb-4">Share with User</h3>
        <div class="grid grid-cols-1 gap-4">
          <div>
            <label for="user" class="block mb-2">User</label>
            <Select
              id="user"
              v-model="selectedUser"
              :options="users"
              optionLabel="email"
              placeholder="Select a user"
              class="w-full"
              filter
            >
              <template #value="slotProps">
                <span v-if="slotProps.value">{{ slotProps.value.email }}</span>
                <span v-else>{{ slotProps.placeholder }}</span>
              </template>
              <template #option="slotProps">
                <div>
                  <div>{{ slotProps.option.email }}</div>
                  <div class="text-sm text-gray-500">{{ slotProps.option.full_name }}</div>
                </div>
              </template>
            </Select>
          </div>

          <div>
            <label for="permission" class="block mb-2">Permission Level</label>
            <Select
              id="permission"
              v-model="selectedPermission"
              :options="permissionOptions"
              optionLabel="label"
              optionValue="value"
              placeholder="Select permission"
              class="w-full"
            />
          </div>

          <div>
            <label for="expiration" class="block mb-2">Expiration (Optional)</label>
            <DatePicker
              id="expiration"
              v-model="expirationDate"
              :showIcon="true"
              :minDate="new Date()"
              placeholder="Never expires"
              class="w-full"
            />
          </div>

          <div>
            <Button
              label="Share Document"
              icon="pi pi-share-alt"
              @click="shareDocument"
              :disabled="!selectedUser"
            />
          </div>
        </div>
      </div>

      <!-- Existing Shares -->
      <div>
        <h3 class="font-semibold mb-4">Current Shares</h3>
        <DataTable :value="shares" :loading="loading" stripedRows>
          <Column header="User">
            <template #body="slotProps">
              {{ getUserEmail(slotProps.data.shared_with_user_id) }}
            </template>
          </Column>

          <Column field="permission_level" header="Permission">
            <template #body="slotProps">
              <Tag
                :value="slotProps.data.permission_level.toUpperCase()"
                :severity="getPermissionSeverity(slotProps.data.permission_level)"
              />
            </template>
          </Column>

          <Column field="created_at" header="Shared On">
            <template #body="slotProps">
              {{ formatDate(slotProps.data.created_at) }}
            </template>
          </Column>

          <Column field="expires_at" header="Expires">
            <template #body="slotProps">
              <span v-if="slotProps.data.expires_at">
                {{ formatDate(slotProps.data.expires_at) }}
              </span>
              <span v-else class="text-gray-400">Never</span>
            </template>
          </Column>

          <Column header="Actions">
            <template #body="slotProps">
              <Button
                icon="pi pi-trash"
                class="p-button-sm p-button-text p-button-danger"
                v-tooltip="'Revoke'"
                @click="revokeShare(slotProps.data)"
              />
            </template>
          </Column>

          <template #empty>
            <div class="text-center py-4 text-gray-500">
              No shares yet. Share this document with users above.
            </div>
          </template>
        </DataTable>
      </div>
    </div>

    <template #footer>
      <Button label="Close" icon="pi pi-times" @click="dialogVisible = false" class="p-button-text" />
    </template>
  </Dialog>
</template>
