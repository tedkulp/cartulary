<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import TabView from 'primevue/tabview'
import TabPanel from 'primevue/tabpanel'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import ConfirmDialog from 'primevue/confirmdialog'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'
import Checkbox from 'primevue/checkbox'
import MultiSelect from 'primevue/multiselect'
import Card from 'primevue/card'
import Tag from 'primevue/tag'
import AppHeader from '@/components/AppHeader.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import EmptyState from '@/components/EmptyState.vue'
import userService from '@/services/userService'
import type { User, Role, Permission, UserCreate, RoleCreate } from '@/types/user'

const router = useRouter()
const toast = useToast()
const confirm = useConfirm()

// State
const users = ref<User[]>([])
const roles = ref<Role[]>([])
const permissions = ref<Permission[]>([])
const loading = ref(false)
const initialLoading = ref(true)
const error = ref<string | null>(null)

// Statistics
const statistics = computed(() => ({
  totalUsers: users.value.length,
  activeUsers: users.value.filter(u => u.is_active).length,
  superusers: users.value.filter(u => u.is_superuser).length,
  totalRoles: roles.value.length,
  totalPermissions: permissions.value.length
}))

// User dialog
const userDialog = ref(false)
const userForm = ref<UserCreate>({
  email: '',
  password: '',
  full_name: '',
  is_active: true,
  is_superuser: false
})

// Role dialog
const roleDialog = ref(false)
const roleForm = ref<RoleCreate>({
  name: '',
  description: ''
})

// User-Role assignment dialog
const assignRoleDialog = ref(false)
const selectedUser = ref<User | null>(null)
const selectedRoles = ref<string[]>([])

// Load data
const loadData = async () => {
  loading.value = true
  error.value = null
  try {
    const [usersData, rolesData, permissionsData] = await Promise.all([
      userService.listUsers(),
      userService.listRoles(),
      userService.listPermissions()
    ])
    users.value = usersData
    roles.value = rolesData
    permissions.value = permissionsData
  } catch (err: any) {
    error.value = err.response?.data?.detail || 'Failed to load admin data'
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: error.value,
      life: 3000
    })
  } finally {
    loading.value = false
    initialLoading.value = false
  }
}

// User management
const openUserDialog = () => {
  userForm.value = {
    email: '',
    password: '',
    full_name: '',
    is_active: true,
    is_superuser: false
  }
  userDialog.value = true
}

const createUser = async () => {
  try {
    await userService.createUser(userForm.value)
    toast.add({
      severity: 'success',
      summary: 'Success',
      detail: 'User created successfully',
      life: 3000
    })
    userDialog.value = false
    await loadData()
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: error.response?.data?.detail || 'Failed to create user',
      life: 3000
    })
  }
}

const deleteUser = async (user: User) => {
  confirm.require({
    message: `Are you sure you want to delete user ${user.email}?`,
    header: 'Confirm Delete',
    icon: 'pi pi-exclamation-triangle',
    accept: async () => {
      try {
        await userService.deleteUser(user.id)
        toast.add({
          severity: 'success',
          summary: 'Success',
          detail: 'User deleted successfully',
          life: 3000
        })
        await loadData()
      } catch (error: any) {
        toast.add({
          severity: 'error',
          summary: 'Error',
          detail: error.response?.data?.detail || 'Failed to delete user',
          life: 3000
        })
      }
    }
  })
}

// Role management
const openRoleDialog = () => {
  roleForm.value = {
    name: '',
    description: ''
  }
  roleDialog.value = true
}

const createRole = async () => {
  try {
    await userService.createRole(roleForm.value)
    toast.add({
      severity: 'success',
      summary: 'Success',
      detail: 'Role created successfully',
      life: 3000
    })
    roleDialog.value = false
    await loadData()
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: error.response?.data?.detail || 'Failed to create role',
      life: 3000
    })
  }
}

const deleteRole = async (role: Role) => {
  confirm.require({
    message: `Are you sure you want to delete role ${role.name}?`,
    header: 'Confirm Delete',
    icon: 'pi pi-exclamation-triangle',
    accept: async () => {
      try {
        await userService.deleteRole(role.id)
        toast.add({
          severity: 'success',
          summary: 'Success',
          detail: 'Role deleted successfully',
          life: 3000
        })
        await loadData()
      } catch (error: any) {
        toast.add({
          severity: 'error',
          summary: 'Error',
          detail: error.response?.data?.detail || 'Failed to delete role',
          life: 3000
        })
      }
    }
  })
}

// Role assignment
const openAssignRoleDialog = (user: User) => {
  selectedUser.value = user
  // Pre-select roles that the user already has
  selectedRoles.value = user.roles?.map(role => role.id) || []
  assignRoleDialog.value = true
}

const assignRoles = async () => {
  if (!selectedUser.value) return

  try {
    const currentRoleIds = selectedUser.value.roles?.map(role => role.id) || []
    const newRoleIds = selectedRoles.value

    // Find roles to add (in new but not in current)
    const rolesToAdd = newRoleIds.filter(roleId => !currentRoleIds.includes(roleId))

    // Find roles to remove (in current but not in new)
    const rolesToRemove = currentRoleIds.filter(roleId => !newRoleIds.includes(roleId))

    // Add new roles
    for (const roleId of rolesToAdd) {
      await userService.assignRoleToUser(selectedUser.value.id, roleId)
    }

    // Remove roles
    for (const roleId of rolesToRemove) {
      await userService.removeRoleFromUser(selectedUser.value.id, roleId)
    }

    toast.add({
      severity: 'success',
      summary: 'Success',
      detail: 'Roles updated successfully',
      life: 3000
    })
    assignRoleDialog.value = false
    await loadData()
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: error.response?.data?.detail || 'Failed to update roles',
      life: 3000
    })
  }
}

onMounted(() => {
  loadData()
})
</script>

<template>
  <div class="min-h-screen">
    <AppHeader />
    <ConfirmDialog />

    <div class="admin-view p-6">
      <div class="mb-6">
        <h1 class="text-3xl font-bold mb-2">Administration</h1>
        <p class="text-muted-color">Manage users, roles, and permissions</p>
      </div>

      <!-- Initial Loading State -->
      <LoadingSpinner v-if="initialLoading" message="Loading admin data..." />

      <!-- Error State -->
      <EmptyState
        v-else-if="error"
        icon="pi pi-exclamation-circle"
        title="Failed to load admin data"
        :description="error"
        action-label="Try Again"
        action-icon="pi pi-refresh"
        @action="loadData"
      />

      <div v-else>
        <!-- Statistics Cards -->
        <div class="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-6">
          <Card>
            <template #content>
              <div class="flex flex-col items-center text-center">
                <i class="pi pi-users text-4xl text-blue-500 mb-2"></i>
                <div class="text-3xl font-bold">{{ statistics.totalUsers }}</div>
                <div class="text-sm text-muted-color">Total Users</div>
              </div>
            </template>
          </Card>

          <Card>
            <template #content>
              <div class="flex flex-col items-center text-center">
                <i class="pi pi-check-circle text-4xl text-green-500 mb-2"></i>
                <div class="text-3xl font-bold">{{ statistics.activeUsers }}</div>
                <div class="text-sm text-muted-color">Active Users</div>
              </div>
            </template>
          </Card>

          <Card>
            <template #content>
              <div class="flex flex-col items-center text-center">
                <i class="pi pi-shield text-4xl text-purple-500 mb-2"></i>
                <div class="text-3xl font-bold">{{ statistics.superusers }}</div>
                <div class="text-sm text-muted-color">Superusers</div>
              </div>
            </template>
          </Card>

          <Card>
            <template #content>
              <div class="flex flex-col items-center text-center">
                <i class="pi pi-tag text-4xl text-orange-500 mb-2"></i>
                <div class="text-3xl font-bold">{{ statistics.totalRoles }}</div>
                <div class="text-sm text-muted-color">Roles</div>
              </div>
            </template>
          </Card>

          <Card>
            <template #content>
              <div class="flex flex-col items-center text-center">
                <i class="pi pi-lock text-4xl text-red-500 mb-2"></i>
                <div class="text-3xl font-bold">{{ statistics.totalPermissions }}</div>
                <div class="text-sm text-muted-color">Permissions</div>
              </div>
            </template>
          </Card>
        </div>

        <TabView>
      <!-- Users Tab -->
      <TabPanel header="Users">
        <div class="mb-4">
          <Button label="Create User" icon="pi pi-plus" @click="openUserDialog" />
        </div>

        <EmptyState
          v-if="users.length === 0 && !loading"
          icon="pi pi-users"
          title="No users yet"
          description="Create your first user to get started."
          action-label="Create User"
          action-icon="pi pi-plus"
          @action="openUserDialog"
        />

        <DataTable v-else :value="users" :loading="loading" stripedRows>
          <Column field="email" header="Email" sortable></Column>
          <Column field="full_name" header="Full Name" sortable></Column>
          <Column header="Roles">
            <template #body="slotProps">
              <div class="flex flex-wrap gap-1">
                <Tag
                  v-for="role in slotProps.data.roles"
                  :key="role.id"
                  :value="role.name"
                  severity="info"
                />
                <span v-if="!slotProps.data.roles || slotProps.data.roles.length === 0" class="text-muted-color text-sm">
                  No roles
                </span>
              </div>
            </template>
          </Column>
          <Column field="is_active" header="Active" sortable>
            <template #body="slotProps">
              <i :class="slotProps.data.is_active ? 'pi pi-check text-green-500' : 'pi pi-times text-red-500'"></i>
            </template>
          </Column>
          <Column field="is_superuser" header="Superuser" sortable>
            <template #body="slotProps">
              <i :class="slotProps.data.is_superuser ? 'pi pi-check text-green-500' : 'pi pi-times text-red-500'"></i>
            </template>
          </Column>
          <Column header="Actions">
            <template #body="slotProps">
              <Button
                icon="pi pi-users"
                class="p-button-sm p-button-text"
                v-tooltip="'Assign Roles'"
                @click="openAssignRoleDialog(slotProps.data)"
              />
              <Button
                icon="pi pi-trash"
                class="p-button-sm p-button-text p-button-danger"
                v-tooltip="'Delete'"
                @click="deleteUser(slotProps.data)"
              />
            </template>
          </Column>
        </DataTable>
      </TabPanel>

      <!-- Roles Tab -->
      <TabPanel header="Roles">
        <div class="mb-4">
          <Button label="Create Role" icon="pi pi-plus" @click="openRoleDialog" />
        </div>

        <EmptyState
          v-if="roles.length === 0 && !loading"
          icon="pi pi-tag"
          title="No roles yet"
          description="Create your first role to organize permissions."
          action-label="Create Role"
          action-icon="pi pi-plus"
          @action="openRoleDialog"
        />

        <DataTable v-else :value="roles" :loading="loading" stripedRows>
          <Column field="name" header="Name" sortable></Column>
          <Column field="description" header="Description"></Column>
          <Column header="Actions">
            <template #body="slotProps">
              <Button
                icon="pi pi-trash"
                class="p-button-sm p-button-text p-button-danger"
                v-tooltip="'Delete'"
                @click="deleteRole(slotProps.data)"
              />
            </template>
          </Column>
        </DataTable>
      </TabPanel>

      <!-- Permissions Tab -->
      <TabPanel header="Permissions">
        <EmptyState
          v-if="permissions.length === 0 && !loading"
          icon="pi pi-lock"
          title="No permissions"
          description="Permissions are system-defined and cannot be created manually."
        />

        <DataTable v-else :value="permissions" :loading="loading" stripedRows>
          <Column field="name" header="Name" sortable></Column>
          <Column field="description" header="Description"></Column>
        </DataTable>
      </TabPanel>
    </TabView>
      </div>

    <!-- Create User Dialog -->
    <Dialog v-model:visible="userDialog" header="Create User" :modal="true" :style="{ width: '500px' }">
      <div class="flex flex-col gap-4">
        <div>
          <label for="email" class="block mb-2">Email</label>
          <InputText id="email" v-model="userForm.email" class="w-full" />
        </div>
        <div>
          <label for="password" class="block mb-2">Password</label>
          <InputText id="password" v-model="userForm.password" type="password" class="w-full" />
        </div>
        <div>
          <label for="full_name" class="block mb-2">Full Name</label>
          <InputText id="full_name" v-model="userForm.full_name" class="w-full" />
        </div>
        <div class="flex items-center gap-2">
          <Checkbox id="is_active" v-model="userForm.is_active" :binary="true" />
          <label for="is_active">Active</label>
        </div>
        <div class="flex items-center gap-2">
          <Checkbox id="is_superuser" v-model="userForm.is_superuser" :binary="true" />
          <label for="is_superuser">Superuser</label>
        </div>
      </div>

      <template #footer>
        <Button label="Cancel" icon="pi pi-times" @click="userDialog = false" class="p-button-text" />
        <Button label="Create" icon="pi pi-check" @click="createUser" />
      </template>
    </Dialog>

    <!-- Create Role Dialog -->
    <Dialog v-model:visible="roleDialog" header="Create Role" :modal="true" :style="{ width: '500px' }">
      <div class="flex flex-col gap-4">
        <div>
          <label for="role_name" class="block mb-2">Name</label>
          <InputText id="role_name" v-model="roleForm.name" class="w-full" />
        </div>
        <div>
          <label for="role_description" class="block mb-2">Description</label>
          <Textarea id="role_description" v-model="roleForm.description" class="w-full" rows="3" />
        </div>
      </div>

      <template #footer>
        <Button label="Cancel" icon="pi pi-times" @click="roleDialog = false" class="p-button-text" />
        <Button label="Create" icon="pi pi-check" @click="createRole" />
      </template>
    </Dialog>

    <!-- Assign Roles Dialog -->
    <Dialog v-model:visible="assignRoleDialog" header="Manage User Roles" :modal="true" :style="{ width: '500px' }">
      <div class="flex flex-col gap-4">
        <p>Manage roles for: <strong>{{ selectedUser?.email }}</strong></p>
        <div>
          <label for="roles" class="block mb-2">Roles</label>
          <MultiSelect
            id="roles"
            v-model="selectedRoles"
            :options="roles"
            optionLabel="name"
            optionValue="id"
            placeholder="Select roles"
            class="w-full"
          />
        </div>
      </div>

      <template #footer>
        <Button label="Cancel" icon="pi pi-times" @click="assignRoleDialog = false" class="p-button-text" />
        <Button label="Save Changes" icon="pi pi-check" @click="assignRoles" />
      </template>
    </Dialog>
    </div>
  </div>
</template>

<style scoped>
.admin-view {
  max-width: 1200px;
  margin: 0 auto;
}
</style>
