import { useEffect, useCallback } from 'react'
import type { WebSocketService } from '../services/websocket.service'
import type { EventType, WebSocketEvent } from '../types/websocket'

/**
 * React hook for WebSocket functionality
 * @param websocketService - The WebSocket service instance
 * @param isAuthenticated - Whether the user is authenticated
 */
export function useWebSocket(
  websocketService: WebSocketService,
  isAuthenticated: boolean
) {
  const subscribe = useCallback(
    (eventType: EventType, handler: (event: WebSocketEvent) => void) => {
      websocketService.on(eventType, handler)

      // Return unsubscribe function
      return () => {
        websocketService.off(eventType, handler)
      }
    },
    [websocketService]
  )

  useEffect(() => {
    // Only connect if user is authenticated
    if (isAuthenticated) {
      websocketService.connect().catch((error) => {
        console.error('Failed to connect WebSocket:', error)
      })
    } else {
      console.log('[WebSocket] Skipping connection - user not authenticated')
    }

    // Don't disconnect on unmount - let other components use the same connection
    // Connection will be reused across components
  }, [websocketService, isAuthenticated])

  return {
    subscribe
  }
}
