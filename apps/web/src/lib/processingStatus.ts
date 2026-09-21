import { processingStatusGroup } from '@cartulary/shared'
import type { ProcessingStatus } from '@cartulary/shared'

/**
 * Tailwind classes for a Document's processing status badge, one entry per group
 * from `@cartulary/shared`. The grouping is shared with mobile; these classes are
 * not, which is why they live here.
 */
const GROUP_CLASSES = {
  queued: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300',
  in_flight: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300',
  stage_complete: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300',
  complete: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300',
  failed: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300',
} as const

export function processingStatusClasses(status: ProcessingStatus): string {
  return GROUP_CLASSES[processingStatusGroup(status)]
}
