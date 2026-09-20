import { create } from 'zustand'
import {
  ALL_CAPABILITIES,
  type Capabilities,
  type CapabilityService,
} from '../services/capability.service'

interface CapabilityState {
  // State
  capabilities: Capabilities
  loaded: boolean
  loading: boolean

  // Internal helper
  _capabilityService: CapabilityService | null

  // Actions
  setCapabilityService: (service: CapabilityService) => void
  fetch: () => Promise<void>
}

/**
 * Capability store using Zustand
 *
 * Holds what the backend says this deployment can do, so a feature whose
 * endpoints would answer 503 is hidden rather than offered (docs/adr/0003).
 * Fetched once after login; every consumer reads the same answer.
 *
 * Capabilities start out all true and stay that way if the fetch fails: an
 * older backend has no capabilities route and its features still work, so a
 * failure must never hide a feature that is actually there.
 */
export const useCapabilityStore = create<CapabilityState>((set, get) => ({
  capabilities: ALL_CAPABILITIES,
  loaded: false,
  loading: false,
  _capabilityService: null,

  setCapabilityService: (service: CapabilityService) => {
    set({ _capabilityService: service })
  },

  fetch: async () => {
    const service = get()._capabilityService
    if (!service || get().loading) return

    set({ loading: true })
    try {
      set({ capabilities: await service.get(), loaded: true })
    } catch (err) {
      console.error('Failed to fetch capabilities; assuming all are on:', err)
      set({ capabilities: ALL_CAPABILITIES, loaded: true })
    } finally {
      set({ loading: false })
    }
  },
}))
