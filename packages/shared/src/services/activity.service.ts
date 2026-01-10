import type { AxiosInstance } from 'axios'
import type { ActivityLog } from '../types/activity'

/**
 * Activity service with dependency injection
 */
export class ActivityService {
  constructor(private api: AxiosInstance) {}

  /**
   * Get activity logs for all users (admin only)
   */
  async list(params?: {
    skip?: number
    limit?: number
    resource_type?: string
    resource_id?: string
    action?: string
  }): Promise<ActivityLog[]> {
    const { data } = await this.api.get<ActivityLog[]>('/api/v1/activity-logs/', { params })
    return data
  }

  /**
   * Get activity logs for the current user
   */
  async getMyActivities(params?: {
    skip?: number
    limit?: number
  }): Promise<ActivityLog[]> {
    const { data } = await this.api.get<ActivityLog[]>('/api/v1/activity-logs/me', { params })
    return data
  }
}
