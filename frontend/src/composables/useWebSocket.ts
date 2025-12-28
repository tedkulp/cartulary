import { onBeforeUnmount, onMounted } from 'vue'
import { websocketService, type EventType, type WebSocketEvent } from '@/services/websocketService'
import { useAuthStore } from '@/stores/auth'

export function useWebSocket() {
  function subscribe(eventType: EventType, handler: (event: WebSocketEvent) => void) {
    websocketService.on(eventType, handler)

    // Return unsubscribe function
    return () => {
      websocketService.off(eventType, handler)
    }
  }

  onMounted(() => {
    const authStore = useAuthStore()

    // Only connect if user is authenticated
    if (authStore.isAuthenticated) {
      websocketService.connect().catch((error) => {
        console.error('Failed to connect WebSocket:', error)
      })
    } else {
      console.log('[WebSocket] Skipping connection - user not authenticated')
    }
  })

  onBeforeUnmount(() => {
    // Don't disconnect here - let other components use the same connection
    // Connection will be reused across components
  })

  return {
    subscribe
  }
}
