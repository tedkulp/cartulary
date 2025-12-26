export interface ActivityLog {
  id: string
  action: string
  resource_type: string
  resource_id?: string
  description: string
  extra_data?: Record<string, any>
  user_id?: string
  user_email?: string
  ip_address?: string
  user_agent?: string
  created_at: string
}
