/**
 * Highlights search terms in text by wrapping them with <mark> tags
 * @param text The text to highlight
 * @param searchTerm The term to search for and highlight
 * @returns HTML string with highlighted terms
 */
export function highlightText(text: string, searchTerm: string): string {
  if (!searchTerm || !text) {
    return text
  }

  // Escape special regex characters in search term
  const escapedTerm = searchTerm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

  // Create regex with global and case-insensitive flags
  const regex = new RegExp(`(${escapedTerm})`, 'gi')

  // Replace matches with highlighted version
  return text.replace(regex, '<mark class="bg-yellow-200 dark:bg-yellow-700">$1</mark>')
}

/**
 * Extracts a snippet of text around the search term
 * @param text The full text
 * @param searchTerm The search term
 * @param contextLength Number of characters to show before and after the match
 * @returns Snippet with highlighted search term
 */
export function getHighlightedSnippet(
  text: string,
  searchTerm: string,
  contextLength: number = 100
): string {
  if (!searchTerm || !text) {
    return text.substring(0, contextLength * 2) + (text.length > contextLength * 2 ? '...' : '')
  }

  const lowerText = text.toLowerCase()
  const lowerTerm = searchTerm.toLowerCase()
  const index = lowerText.indexOf(lowerTerm)

  if (index === -1) {
    // Term not found, return beginning of text
    return text.substring(0, contextLength * 2) + (text.length > contextLength * 2 ? '...' : '')
  }

  // Calculate start and end positions
  const start = Math.max(0, index - contextLength)
  const end = Math.min(text.length, index + searchTerm.length + contextLength)

  // Extract snippet
  let snippet = text.substring(start, end)

  // Add ellipsis if needed
  if (start > 0) snippet = '...' + snippet
  if (end < text.length) snippet = snippet + '...'

  // Highlight the search term in the snippet
  return highlightText(snippet, searchTerm)
}
