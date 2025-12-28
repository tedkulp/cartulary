export type EventType =
  | 'document.created'
  | 'document.updated'
  | 'document.deleted'
  | 'document.status_changed'

export interface WebSocketEvent {
  type: EventType
  data: {
    document_id?: string
    user_id?: string
    old_status?: string
    new_status?: string
    [key: string]: any
  }
  timestamp: string
}
