/**
 * Import source related types
 */

export enum ImportSourceType {
  DIRECTORY = 'directory',
  IMAP = 'imap'
}

export enum ImportSourceStatus {
  ACTIVE = 'active',
  PAUSED = 'paused',
  ERROR = 'error'
}

export interface ImportSource {
  id: string
  name: string
  source_type: ImportSourceType
  status: ImportSourceStatus
  owner_id: string

  // Directory-specific fields
  watch_path: string | null
  move_after_import: boolean
  move_to_path: string | null
  delete_after_import: boolean

  // IMAP-specific fields (password excluded for security)
  imap_server: string | null
  imap_port: number | null
  imap_username: string | null
  imap_use_ssl: boolean
  imap_mailbox: string | null
  imap_processed_folder: string | null

  last_run: string | null
  last_error: string | null
  created_at: string
  updated_at: string
}

export interface ImportSourceCreate {
  name: string
  source_type: ImportSourceType
  status?: ImportSourceStatus

  // Directory-specific fields
  watch_path?: string | null
  move_after_import?: boolean
  move_to_path?: string | null
  delete_after_import?: boolean

  // IMAP-specific fields
  imap_server?: string | null
  imap_port?: number | null
  imap_username?: string | null
  imap_password?: string | null
  imap_use_ssl?: boolean
  imap_mailbox?: string
  imap_processed_folder?: string | null
}

export interface ImportSourceUpdate {
  name?: string
  status?: ImportSourceStatus

  // Directory-specific fields
  watch_path?: string | null
  move_after_import?: boolean
  move_to_path?: string | null
  delete_after_import?: boolean

  // IMAP-specific fields
  imap_server?: string | null
  imap_port?: number | null
  imap_username?: string | null
  imap_password?: string | null
  imap_use_ssl?: boolean
  imap_mailbox?: string | null
  imap_processed_folder?: string | null
}
