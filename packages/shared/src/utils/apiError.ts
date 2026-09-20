/**
 * Pull the message the backend wrote out of a failed request.
 *
 * FastAPI puts it in `detail`, and for a disabled capability (503) that message
 * names the setting an operator has to change — so showing a fixed "please try
 * again" in its place hides the one thing that would help. See docs/adr/0003.
 *
 * @param error The thrown value, usually an AxiosError.
 * @param fallback What to show when the response carried no usable message.
 */
export function apiErrorMessage(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail

  if (typeof detail === 'string' && detail.trim()) {
    return detail
  }

  // 422 sends an array of per-field validation errors rather than a string.
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => (typeof item?.msg === 'string' ? item.msg : null))
      .filter((msg): msg is string => Boolean(msg))
    if (messages.length > 0) {
      return messages.join('; ')
    }
  }

  return fallback
}
