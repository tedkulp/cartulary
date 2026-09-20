import api from './api'
import {
  DocumentService,
  AuthService,
  SearchService,
  TagService,
  UserService,
  SharingService,
  ActivityService,
  ImportSourceService,
  WebSocketService,
  ChatService,
  CapabilityService,
  useAuthStore,
  useCapabilityStore,
} from '@cartulary/shared'

// Initialize all services with the axios instance
export const documentService = new DocumentService(api)
export const authService = new AuthService(api)
export const searchService = new SearchService(api)
export const tagService = new TagService(api)
export const userService = new UserService(api)
export const sharingService = new SharingService(api)
export const activityService = new ActivityService(api)
export const importSourceService = new ImportSourceService(api)
export const chatService = new ChatService(api)
export const capabilityService = new CapabilityService(api)

// Initialize WebSocket service
const getToken = () => useAuthStore.getState().accessToken
// Use relative ws URL - will connect to same host as the frontend
const wsUrl = window.location.protocol === 'https:' ? 'wss://' : 'ws://'
const wsHost = window.location.host
export const websocketService = new WebSocketService(
  `${wsUrl}${wsHost}`,
  getToken
)

// Initialize auth store with service and storage
useAuthStore.getState().setAuthService(authService, localStorage)

// Capabilities need a token, so they are fetched once the user is known
useCapabilityStore.getState().setCapabilityService(capabilityService)

// Initialize auth state from localStorage (fetch current user if tokens exist)
useAuthStore.getState().initialize()
