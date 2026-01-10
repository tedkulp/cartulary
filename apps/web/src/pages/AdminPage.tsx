import { useState, useEffect, useMemo } from 'react'
import { userService } from '../services'
import type { User, Role, Permission, UserCreate, RoleCreate } from '@cartulary/shared'
import { toast } from 'sonner'
import {
  Users,
  Shield,
  Lock,
  UserPlus,
  Trash2,
  UserCog,
  Plus,
  Loader2,
  CheckCircle2,
  XCircle,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Checkbox } from '@/components/ui/checkbox'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

export default function AdminPage() {
  // State
  const [users, setUsers] = useState<User[]>([])
  const [roles, setRoles] = useState<Role[]>([])
  const [permissions, setPermissions] = useState<Permission[]>([])
  const [initialLoading, setInitialLoading] = useState(true)

  // Dialog states
  const [userDialog, setUserDialog] = useState(false)
  const [roleDialog, setRoleDialog] = useState(false)
  const [assignRoleDialog, setAssignRoleDialog] = useState(false)
  const [deleteUserDialog, setDeleteUserDialog] = useState(false)
  const [deleteRoleDialog, setDeleteRoleDialog] = useState(false)

  // Selected items
  const [selectedUser, setSelectedUser] = useState<User | null>(null)
  const [selectedRole, setSelectedRole] = useState<Role | null>(null)
  const [selectedRoles, setSelectedRoles] = useState<string[]>([])

  // Form states
  const [userForm, setUserForm] = useState<UserCreate>({
    email: '',
    password: '',
    full_name: '',
    is_active: true,
    is_superuser: false,
  })

  const [roleForm, setRoleForm] = useState<RoleCreate>({
    name: '',
    description: '',
  })

  // Statistics
  const statistics = useMemo(
    () => ({
      totalUsers: users.length,
      activeUsers: users.filter((u) => u.is_active).length,
      superusers: users.filter((u) => u.is_superuser).length,
      totalRoles: roles.length,
      totalPermissions: permissions.length,
    }),
    [users, roles, permissions]
  )

  // Load data
  const loadData = async () => {
    setInitialLoading(true)
    try {
      const [usersData, rolesData, permissionsData] = await Promise.all([
        userService.listUsers(),
        userService.listRoles(),
        userService.listPermissions(),
      ])
      setUsers(usersData)
      setRoles(rolesData)
      setPermissions(permissionsData)
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to load admin data')
    } finally {
      setInitialLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  // User management
  const openUserDialog = () => {
    setUserForm({
      email: '',
      password: '',
      full_name: '',
      is_active: true,
      is_superuser: false,
    })
    setUserDialog(true)
  }

  const createUser = async () => {
    try {
      await userService.createUser(userForm)
      toast.success('User created successfully')
      setUserDialog(false)
      await loadData()
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to create user')
    }
  }

  const handleDeleteUserClick = (user: User) => {
    setSelectedUser(user)
    setDeleteUserDialog(true)
  }

  const deleteUser = async () => {
    if (!selectedUser) return

    try {
      await userService.deleteUser(selectedUser.id)
      toast.success('User deleted successfully')
      setDeleteUserDialog(false)
      setSelectedUser(null)
      await loadData()
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to delete user')
    }
  }

  // Role management
  const openRoleDialog = () => {
    setRoleForm({
      name: '',
      description: '',
    })
    setRoleDialog(true)
  }

  const createRole = async () => {
    try {
      await userService.createRole(roleForm)
      toast.success('Role created successfully')
      setRoleDialog(false)
      await loadData()
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to create role')
    }
  }

  const handleDeleteRoleClick = (role: Role) => {
    setSelectedRole(role)
    setDeleteRoleDialog(true)
  }

  const deleteRole = async () => {
    if (!selectedRole) return

    try {
      await userService.deleteRole(selectedRole.id)
      toast.success('Role deleted successfully')
      setDeleteRoleDialog(false)
      setSelectedRole(null)
      await loadData()
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to delete role')
    }
  }

  // Role assignment
  const openAssignRoleDialog = (user: User) => {
    setSelectedUser(user)
    setSelectedRoles(user.roles?.map((role) => role.id) || [])
    setAssignRoleDialog(true)
  }

  const toggleRole = (roleId: string) => {
    setSelectedRoles((prev) =>
      prev.includes(roleId) ? prev.filter((id) => id !== roleId) : [...prev, roleId]
    )
  }

  const assignRoles = async () => {
    if (!selectedUser) return

    try {
      const currentRoleIds = selectedUser.roles?.map((role) => role.id) || []
      const newRoleIds = selectedRoles

      const rolesToAdd = newRoleIds.filter((roleId) => !currentRoleIds.includes(roleId))
      const rolesToRemove = currentRoleIds.filter((roleId) => !newRoleIds.includes(roleId))

      for (const roleId of rolesToAdd) {
        await userService.assignRoleToUser(selectedUser.id, roleId)
      }

      for (const roleId of rolesToRemove) {
        await userService.removeRoleFromUser(selectedUser.id, roleId)
      }

      toast.success('Roles updated successfully')
      setAssignRoleDialog(false)
      setSelectedUser(null)
      await loadData()
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to update roles')
    }
  }

  return (
    <div className="container mx-auto py-6 space-y-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold">Administration</h1>
        <p className="text-muted-foreground">Manage users, roles, and permissions</p>
      </div>

      {initialLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <>
          {/* Statistics Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
            <Card>
              <CardContent className="pt-6">
                <div className="flex flex-col items-center text-center">
                  <Users className="h-10 w-10 text-blue-500 mb-2" />
                  <div className="text-3xl font-bold">{statistics.totalUsers}</div>
                  <div className="text-sm text-muted-foreground">Total Users</div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <div className="flex flex-col items-center text-center">
                  <CheckCircle2 className="h-10 w-10 text-green-500 mb-2" />
                  <div className="text-3xl font-bold">{statistics.activeUsers}</div>
                  <div className="text-sm text-muted-foreground">Active Users</div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <div className="flex flex-col items-center text-center">
                  <Shield className="h-10 w-10 text-purple-500 mb-2" />
                  <div className="text-3xl font-bold">{statistics.superusers}</div>
                  <div className="text-sm text-muted-foreground">Superusers</div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <div className="flex flex-col items-center text-center">
                  <UserCog className="h-10 w-10 text-orange-500 mb-2" />
                  <div className="text-3xl font-bold">{statistics.totalRoles}</div>
                  <div className="text-sm text-muted-foreground">Roles</div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <div className="flex flex-col items-center text-center">
                  <Lock className="h-10 w-10 text-red-500 mb-2" />
                  <div className="text-3xl font-bold">{statistics.totalPermissions}</div>
                  <div className="text-sm text-muted-foreground">Permissions</div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Tabs */}
          <Tabs defaultValue="users" className="space-y-4">
            <TabsList>
              <TabsTrigger value="users">Users</TabsTrigger>
              <TabsTrigger value="roles">Roles</TabsTrigger>
              <TabsTrigger value="permissions">Permissions</TabsTrigger>
            </TabsList>

            {/* Users Tab */}
            <TabsContent value="users">
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle>Users</CardTitle>
                      <CardDescription>Manage system users and their permissions</CardDescription>
                    </div>
                    <Button onClick={openUserDialog}>
                      <UserPlus className="mr-2 h-4 w-4" />
                      Create User
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  {users.length === 0 ? (
                    <div className="text-center py-8 text-muted-foreground">
                      No users yet. Create your first user to get started.
                    </div>
                  ) : (
                    <div className="rounded-md border">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Email</TableHead>
                            <TableHead>Full Name</TableHead>
                            <TableHead>Roles</TableHead>
                            <TableHead>Active</TableHead>
                            <TableHead>Superuser</TableHead>
                            <TableHead>Actions</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {users.map((user) => (
                            <TableRow key={user.id}>
                              <TableCell className="font-medium">{user.email}</TableCell>
                              <TableCell>{user.full_name || '-'}</TableCell>
                              <TableCell>
                                <div className="flex flex-wrap gap-1">
                                  {user.roles && user.roles.length > 0 ? (
                                    user.roles.map((role) => (
                                      <Badge key={role.id} variant="secondary">
                                        {role.name}
                                      </Badge>
                                    ))
                                  ) : (
                                    <span className="text-sm text-muted-foreground">No roles</span>
                                  )}
                                </div>
                              </TableCell>
                              <TableCell>
                                {user.is_active ? (
                                  <CheckCircle2 className="h-4 w-4 text-green-500" />
                                ) : (
                                  <XCircle className="h-4 w-4 text-red-500" />
                                )}
                              </TableCell>
                              <TableCell>
                                {user.is_superuser ? (
                                  <CheckCircle2 className="h-4 w-4 text-green-500" />
                                ) : (
                                  <XCircle className="h-4 w-4 text-red-500" />
                                )}
                              </TableCell>
                              <TableCell>
                                <div className="flex gap-2">
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => openAssignRoleDialog(user)}
                                  >
                                    <UserCog className="h-4 w-4" />
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => handleDeleteUserClick(user)}
                                  >
                                    <Trash2 className="h-4 w-4 text-destructive" />
                                  </Button>
                                </div>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            {/* Roles Tab */}
            <TabsContent value="roles">
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle>Roles</CardTitle>
                      <CardDescription>Create and manage user roles</CardDescription>
                    </div>
                    <Button onClick={openRoleDialog}>
                      <Plus className="mr-2 h-4 w-4" />
                      Create Role
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  {roles.length === 0 ? (
                    <div className="text-center py-8 text-muted-foreground">
                      No roles yet. Create your first role to organize permissions.
                    </div>
                  ) : (
                    <div className="rounded-md border">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Name</TableHead>
                            <TableHead>Description</TableHead>
                            <TableHead>Actions</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {roles.map((role) => (
                            <TableRow key={role.id}>
                              <TableCell className="font-medium">{role.name}</TableCell>
                              <TableCell>{role.description || '-'}</TableCell>
                              <TableCell>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  onClick={() => handleDeleteRoleClick(role)}
                                >
                                  <Trash2 className="h-4 w-4 text-destructive" />
                                </Button>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            {/* Permissions Tab */}
            <TabsContent value="permissions">
              <Card>
                <CardHeader>
                  <CardTitle>Permissions</CardTitle>
                  <CardDescription>System-defined permissions</CardDescription>
                </CardHeader>
                <CardContent>
                  {permissions.length === 0 ? (
                    <div className="text-center py-8 text-muted-foreground">
                      No permissions. Permissions are system-defined and cannot be created manually.
                    </div>
                  ) : (
                    <div className="rounded-md border">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Name</TableHead>
                            <TableHead>Description</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {permissions.map((permission) => (
                            <TableRow key={permission.id}>
                              <TableCell className="font-medium">{permission.name}</TableCell>
                              <TableCell>{permission.description || '-'}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </>
      )}

      {/* Create User Dialog */}
      <Dialog open={userDialog} onOpenChange={setUserDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create User</DialogTitle>
            <DialogDescription>Create a new user account</DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div>
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={userForm.email}
                onChange={(e) => setUserForm({ ...userForm, email: e.target.value })}
                placeholder="user@example.com"
              />
            </div>

            <div>
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                value={userForm.password}
                onChange={(e) => setUserForm({ ...userForm, password: e.target.value })}
                placeholder="••••••••"
              />
            </div>

            <div>
              <Label htmlFor="full_name">Full Name</Label>
              <Input
                id="full_name"
                value={userForm.full_name || ''}
                onChange={(e) => setUserForm({ ...userForm, full_name: e.target.value })}
                placeholder="John Doe"
              />
            </div>

            <div className="flex items-center gap-2">
              <Checkbox
                id="is_active"
                checked={userForm.is_active}
                onCheckedChange={(checked) =>
                  setUserForm({ ...userForm, is_active: checked as boolean })
                }
              />
              <Label htmlFor="is_active" className="cursor-pointer">
                Active
              </Label>
            </div>

            <div className="flex items-center gap-2">
              <Checkbox
                id="is_superuser"
                checked={userForm.is_superuser}
                onCheckedChange={(checked) =>
                  setUserForm({ ...userForm, is_superuser: checked as boolean })
                }
              />
              <Label htmlFor="is_superuser" className="cursor-pointer">
                Superuser
              </Label>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setUserDialog(false)}>
              Cancel
            </Button>
            <Button onClick={createUser} disabled={!userForm.email || !userForm.password}>
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Create Role Dialog */}
      <Dialog open={roleDialog} onOpenChange={setRoleDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Role</DialogTitle>
            <DialogDescription>Create a new role for organizing permissions</DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div>
              <Label htmlFor="role_name">Name</Label>
              <Input
                id="role_name"
                value={roleForm.name}
                onChange={(e) => setRoleForm({ ...roleForm, name: e.target.value })}
                placeholder="Editor"
              />
            </div>

            <div>
              <Label htmlFor="role_description">Description</Label>
              <Textarea
                id="role_description"
                value={roleForm.description || ''}
                onChange={(e) => setRoleForm({ ...roleForm, description: e.target.value })}
                rows={3}
                placeholder="Can edit documents..."
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setRoleDialog(false)}>
              Cancel
            </Button>
            <Button onClick={createRole} disabled={!roleForm.name}>
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Assign Roles Dialog */}
      <Dialog open={assignRoleDialog} onOpenChange={setAssignRoleDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Manage User Roles</DialogTitle>
            <DialogDescription>
              Manage roles for: <strong>{selectedUser?.email}</strong>
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2">
            <Label>Roles</Label>
            <div className="space-y-2 max-h-60 overflow-y-auto">
              {roles.map((role) => (
                <div key={role.id} className="flex items-center gap-2">
                  <Checkbox
                    id={`role-${role.id}`}
                    checked={selectedRoles.includes(role.id)}
                    onCheckedChange={() => toggleRole(role.id)}
                  />
                  <Label htmlFor={`role-${role.id}`} className="cursor-pointer flex-1">
                    <div className="font-medium">{role.name}</div>
                    {role.description && (
                      <div className="text-sm text-muted-foreground">{role.description}</div>
                    )}
                  </Label>
                </div>
              ))}
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setAssignRoleDialog(false)}>
              Cancel
            </Button>
            <Button onClick={assignRoles}>Save Changes</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete User Dialog */}
      <AlertDialog open={deleteUserDialog} onOpenChange={setDeleteUserDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirm Delete</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete user <strong>{selectedUser?.email}</strong>? This
              action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setSelectedUser(null)}>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={deleteUser}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Delete Role Dialog */}
      <AlertDialog open={deleteRoleDialog} onOpenChange={setDeleteRoleDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirm Delete</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete role <strong>{selectedRole?.name}</strong>? This
              action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setSelectedRole(null)}>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={deleteRole}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
