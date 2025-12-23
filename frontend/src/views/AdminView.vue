<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useToast } from 'primevue/usetoast'
import TabView from 'primevue/tabview'
import TabPanel from 'primevue/tabpanel'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'
import Checkbox from 'primevue/checkbox'
import MultiSelect from 'primevue/multiselect'
import AppHeader from '@/components/AppHeader.vue'
import userService from '@/services/userService'
import type { User, Role, Permission, UserCreate, RoleCreate } from '@/types/user'

const router = useRouter()
const toast = useToast()

// State
const users = ref<User[]>([])
const roles = ref<Role[]>([])
const permissions = ref<Permission[]>([])
const loading = ref(false)

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
  try {
    const [usersData, rolesData, permissionsData] = await Promise.all([
      userService.listUsers(),
      userService.listRoles(),
      userService.listPermissions()
    ])
    users.value = usersData
    roles.value = rolesData
    permissions.value = permissionsData
  } catch (error) {
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to load admin data',
      life: 3000
    })
  } finally {
    loading.value = false
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
  if (confirm(`Are you sure you want to delete user ${user.email}?`)) {
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
  if (confirm(`Are you sure you want to delete role ${role.name}?`)) {
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
  <div class="min-h-screen bg-gray-50">
    <AppHeader />

    <div class="admin-view p-6">
      <div class="mb-6">
      <h1 class="text-3xl font-bold mb-2">Administration</h1>
      <p class="text-gray-600">Manage users, roles, and permissions</p>
    </div>

    <TabView>
      <!-- Users Tab -->
      <TabPanel header="Users">
        <div class="mb-4">
          <Button label="Create User" icon="pi pi-plus" @click="openUserDialog" />
        </div>

        <DataTable :value="users" :loading="loading" stripedRows>
          <Column field="email" header="Email" sortable></Column>
          <Column field="full_name" header="Full Name" sortable></Column>
          <Column header="Roles">
            <template #body="slotProps">
              <div class="flex flex-wrap gap-1">
                <span
                  v-for="role in slotProps.data.roles"
                  :key="role.id"
                  class="px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs font-medium"
                >
                  {{ role.name }}
                </span>
                <span v-if="!slotProps.data.roles || slotProps.data.roles.length === 0" class="text-gray-400 text-sm">
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

        <DataTable :value="roles" :loading="loading" stripedRows>
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
        <DataTable :value="permissions" :loading="loading" stripedRows>
          <Column field="name" header="Name" sortable></Column>
          <Column field="description" header="Description"></Column>
        </DataTable>
      </TabPanel>
    </TabView>

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
