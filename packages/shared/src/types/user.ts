/**
 * User-related types for RBAC and user management
 */

export interface User {
  id: string
  email: string
  full_name: string | null
  is_active: boolean
  is_superuser: boolean
  created_at: string
  roles?: Role[]
}

export interface UserCreate {
  email: string
  password: string
  full_name?: string | null
  is_active?: boolean
  is_superuser?: boolean
}

export interface UserUpdate {
  email?: string
  full_name?: string | null
  is_active?: boolean
  is_superuser?: boolean
  password?: string
}

export interface Role {
  id: string
  name: string
  description: string | null
  created_at: string
}

export interface RoleCreate {
  name: string
  description?: string | null
}

export interface RoleUpdate {
  name?: string
  description?: string | null
}

export interface Permission {
  id: string
  name: string
  description: string | null
}

export interface UserGroup {
  id: string
  name: string
  description: string | null
  created_at: string
}

export interface UserGroupCreate {
  name: string
  description?: string | null
}

export interface UserGroupUpdate {
  name?: string
  description?: string | null
}
