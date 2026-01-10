/**
 * WebSocket service for real-time updates
 */
import type { EventType, WebSocketEvent } from '../types/websocket'

type EventHandler = (event: WebSocketEvent) => void

/**
 * WebSocket service for real-time updates
 * Platform-agnostic (works in browser and React Native)
 */
export class WebSocketService {
  private ws: WebSocket | null = null
  private eventHandlers = new Map<EventType, Set<EventHandler>>()
  private reconnectAttempts = 0
  private maxReconnectAttempts = 10
  private reconnectDelay = 1000
  private isConnecting = false
  private wsUrl: string
  private getToken: () => string | null

  /**
   * @param baseUrl - WebSocket base URL (e.g., 'ws://localhost:8000')
   * @param getToken - Function to retrieve the current auth token
   */
  constructor(baseUrl: string, getToken: () => string | null) {
    this.wsUrl = baseUrl
    this.getToken = getToken
  }

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        resolve()
        return
      }

      if (this.isConnecting) {
        resolve()
        return
      }

      this.isConnecting = true
      const token = this.getToken()

      if (!token) {
        this.isConnecting = false
        reject(new Error('No authentication token'))
        return
      }

      const fullUrl = `${this.wsUrl}/api/v1/ws?token=${token}`
      this.ws = new WebSocket(fullUrl)

      this.ws.onopen = () => {
        console.log('[WebSocket] Connected')
        this.isConnecting = false
        this.reconnectAttempts = 0
        resolve()
      }

      this.ws.onmessage = (event) => {
        this.handleMessage(event)
      }

      this.ws.onclose = () => {
        console.log('[WebSocket] Disconnected')
        this.isConnecting = false
        this.reconnect()
      }

      this.ws.onerror = (error) => {
        console.error('[WebSocket] Error:', error)
        this.isConnecting = false
        reject(error)
      }
    })
  }

  disconnect(): void {
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }

  on(eventType: EventType, handler: EventHandler): void {
    if (!this.eventHandlers.has(eventType)) {
      this.eventHandlers.set(eventType, new Set())
    }
    this.eventHandlers.get(eventType)!.add(handler)
  }

  off(eventType: EventType, handler: EventHandler): void {
    this.eventHandlers.get(eventType)?.delete(handler)
  }

  private handleMessage(event: MessageEvent): void {
    try {
      const message = JSON.parse(event.data)
      console.log('[WebSocket] Received message:', message)

      // Handle ping/pong
      if (message.type === 'ping') {
        this.ws?.send(JSON.stringify({ type: 'pong' }))
        return
      }

      // Dispatch to handlers
      const handlers = this.eventHandlers.get(message.type)
      if (handlers) {
        console.log(`[WebSocket] Dispatching to ${handlers.size} handlers for event type: ${message.type}`)
        handlers.forEach((handler) => handler(message))
      } else {
        console.warn(`[WebSocket] No handlers registered for event type: ${message.type}`)
      }
    } catch (error) {
      console.error('[WebSocket] Message parsing error:', error)
    }
  }

  private reconnect(): void {
    // Don't reconnect if no token available (user logged out)
    if (!this.getToken()) {
      console.log('[WebSocket] No token available, stopping reconnection')
      return
    }

    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('[WebSocket] Max reconnection attempts reached')
      return
    }

    this.reconnectAttempts++
    const delay = Math.min(this.reconnectDelay * Math.pow(2, this.reconnectAttempts), 32000)

    console.log(`[WebSocket] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`)
    setTimeout(() => this.connect().catch(() => {
      // Silently fail - reconnect will be triggered by onclose if needed
    }), delay)
  }
}
