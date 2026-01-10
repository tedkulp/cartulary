/**
 * Format a date string to the user's local timezone
 * @param dateString ISO date string from the backend
 * @param options Intl.DateTimeFormatOptions
 * @returns Formatted date string in user's timezone
 */
export function formatDateTime(dateString: string, options?: Intl.DateTimeFormatOptions): string {
  if (!dateString) return 'Unknown'

  const date = new Date(dateString)

  if (isNaN(date.getTime())) {
    console.error('Invalid date:', dateString)
    return 'Invalid date'
  }

  const defaultOptions: Intl.DateTimeFormatOptions = {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    ...options
  }

  return date.toLocaleString(undefined, defaultOptions)
}

/**
 * Format a date string to just the date (no time) in user's timezone
 */
export function formatDate(dateString: string): string {
  return formatDateTime(dateString, {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  })
}

/**
 * Format a date string to just the time in user's timezone
 */
export function formatTime(dateString: string): string {
  return formatDateTime(dateString, {
    hour: '2-digit',
    minute: '2-digit'
  })
}

/**
 * Format a date string as relative time (e.g., "2 hours ago", "just now")
 */
export function formatRelativeTime(dateString: string): string {
  if (!dateString) return 'Unknown'

  const date = new Date(dateString)

  if (isNaN(date.getTime())) {
    console.error('Invalid date:', dateString)
    return 'Invalid date'
  }

  const now = new Date()
  const diff = now.getTime() - date.getTime()

  const seconds = Math.floor(diff / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)
  const days = Math.floor(hours / 24)
  const weeks = Math.floor(days / 7)
  const months = Math.floor(days / 30)
  const years = Math.floor(days / 365)

  if (seconds < 60) return 'Just now'
  if (minutes < 60) return `${minutes}m ago`
  if (hours < 24) return `${hours}h ago`
  if (days < 7) return `${days}d ago`
  if (weeks < 4) return `${weeks}w ago`
  if (months < 12) return `${months}mo ago`
  return `${years}y ago`
}
