/**
 * User and role management API service
 */

import type { AxiosInstance } from 'axios'
import type {
  User,
  UserCreate,
  UserUpdate,
  Role,
  RoleCreate,
  RoleUpdate,
  Permission,
  UserGroup,
  UserGroupCreate,
  UserGroupUpdate
} from '../types/user'

/**
 * User service with dependency injection
 */
export class UserService {
  constructor(private api: AxiosInstance) {}

  // ===== Users =====

  async listUsers(skip = 0, limit = 100): Promise<User[]> {
    const { data } = await this.api.get<User[]>('/api/v1/users', { params: { skip, limit } })
    return data
  }

  async getCurrentUser(): Promise<User> {
    const { data } = await this.api.get<User>('/api/v1/users/me')
    return data
  }

  async getUser(userId: string): Promise<User> {
    const { data } = await this.api.get<User>(`/api/v1/users/${userId}`)
    return data
  }

  async createUser(userData: UserCreate): Promise<User> {
    const { data } = await this.api.post<User>('/api/v1/users', userData)
    return data
  }

  async updateUser(userId: string, userData: UserUpdate): Promise<User> {
    const { data} = await this.api.patch<User>(`/api/v1/users/${userId}`, userData)
    return data
  }

  async deleteUser(userId: string): Promise<void> {
    await this.api.delete(`/api/v1/users/${userId}`)
  }

  // ===== Roles =====

  async listRoles(): Promise<Role[]> {
    const { data } = await this.api.get<Role[]>('/api/v1/roles')
    return data
  }

  async getRole(roleId: string): Promise<Role> {
    const { data } = await this.api.get<Role>(`/api/v1/roles/${roleId}`)
    return data
  }

  async createRole(roleData: RoleCreate): Promise<Role> {
    const { data } = await this.api.post<Role>('/api/v1/roles', roleData)
    return data
  }

  async updateRole(roleId: string, roleData: RoleUpdate): Promise<Role> {
    const { data } = await this.api.patch<Role>(`/api/v1/roles/${roleId}`, roleData)
    return data
  }

  async deleteRole(roleId: string): Promise<void> {
    await this.api.delete(`/api/v1/roles/${roleId}`)
  }

  // ===== Permissions =====

  async listPermissions(): Promise<Permission[]> {
    const { data } = await this.api.get<Permission[]>('/api/v1/permissions')
    return data
  }

  // ===== Role-Permission Assignments =====

  async addPermissionToRole(roleId: string, permissionId: string): Promise<void> {
    await this.api.post(`/api/v1/roles/${roleId}/permissions/${permissionId}`)
  }

  async removePermissionFromRole(roleId: string, permissionId: string): Promise<void> {
    await this.api.delete(`/api/v1/roles/${roleId}/permissions/${permissionId}`)
  }

  // ===== User-Role Assignments =====

  async assignRoleToUser(userId: string, roleId: string): Promise<void> {
    await this.api.post(`/api/v1/users/${userId}/roles/${roleId}`)
  }

  async removeRoleFromUser(userId: string, roleId: string): Promise<void> {
    await this.api.delete(`/api/v1/users/${userId}/roles/${roleId}`)
  }

  // ===== User Groups =====

  async listGroups(): Promise<UserGroup[]> {
    const { data } = await this.api.get<UserGroup[]>('/api/v1/groups')
    return data
  }

  async getGroup(groupId: string): Promise<UserGroup> {
    const { data } = await this.api.get<UserGroup>(`/api/v1/groups/${groupId}`)
    return data
  }

  async createGroup(groupData: UserGroupCreate): Promise<UserGroup> {
    const { data } = await this.api.post<UserGroup>('/api/v1/groups', groupData)
    return data
  }

  async updateGroup(groupId: string, groupData: UserGroupUpdate): Promise<UserGroup> {
    const { data } = await this.api.patch<UserGroup>(`/api/v1/groups/${groupId}`, groupData)
    return data
  }

  async deleteGroup(groupId: string): Promise<void> {
    await this.api.delete(`/api/v1/groups/${groupId}`)
  }

  // ===== Group Membership =====

  async addUserToGroup(groupId: string, userId: string): Promise<void> {
    await this.api.post(`/api/v1/groups/${groupId}/members/${userId}`)
  }

  async removeUserFromGroup(groupId: string, userId: string): Promise<void> {
    await this.api.delete(`/api/v1/groups/${groupId}/members/${userId}`)
  }
}
