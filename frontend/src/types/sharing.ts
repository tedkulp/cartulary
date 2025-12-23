/**
 * Document sharing types
 */

import type { Document } from './document'

export type PermissionLevel = 'read' | 'write' | 'admin'

export interface DocumentShare {
  id: string
  document_id: string
  shared_with_user_id: string
  shared_by_user_id: string | null
  permission_level: PermissionLevel
  expires_at: string | null
  created_at: string
}

export interface DocumentShareCreate {
  shared_with_user_id: string
  permission_level: PermissionLevel
  expires_at?: string | null
}

export interface DocumentShareUpdate {
  permission_level?: PermissionLevel
  expires_at?: string | null
}

export interface SharedDocument {
  document: Document
  share: DocumentShare
}
