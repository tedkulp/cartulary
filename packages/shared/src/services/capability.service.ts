import type { AxiosInstance } from 'axios'

/**
 * Which optional capabilities a deployment has turned on.
 *
 * A capability reported false means the endpoints behind it answer 503, so the feature
 * should be hidden or disabled rather than offered. See docs/adr/0003.
 */
export interface Capabilities {
  ocr: boolean
  embeddings: boolean
  chat: boolean
  metadata: boolean
}

/**
 * Everything on. Used when the backend cannot be asked — an older backend has no
 * capabilities route, and its features still work, so nothing is hidden on a failure.
 */
export const ALL_CAPABILITIES: Capabilities = {
  ocr: true,
  embeddings: true,
  chat: true,
  metadata: true,
}

/**
 * Capability service: what this deployment can do.
 */
export class CapabilityService {
  constructor(private api: AxiosInstance) {}

  async get(): Promise<Capabilities> {
    const { data } = await this.api.get<Capabilities>('/api/v1/capabilities')
    return data
  }
}
