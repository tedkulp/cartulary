import { useState, useEffect, useCallback } from 'react'

const THEME_STORAGE_KEY = 'cartulary-theme'

export type Theme = 'light' | 'dark'

interface UseThemeOptions {
  storage?: Storage
}

/**
 * React hook for theme management
 * Platform-agnostic: works with web (localStorage) and mobile (AsyncStorage)
 *
 * @param options - Configuration options including storage provider
 * @returns Theme state and control functions
 */
export function useTheme(options?: UseThemeOptions) {
  const [theme, setThemeState] = useState<Theme>('light')
  const [isDark, setIsDark] = useState(false)

  const setTheme = useCallback(
    (newTheme: Theme) => {
      setThemeState(newTheme)
      setIsDark(newTheme === 'dark')

      // Platform-specific: only manipulate DOM on web
      if (typeof document !== 'undefined') {
        if (newTheme === 'dark') {
          document.documentElement.classList.add('dark-mode')
        } else {
          document.documentElement.classList.remove('dark-mode')
        }
      }

      // Save to storage
      if (options?.storage) {
        options.storage.setItem?.(THEME_STORAGE_KEY, newTheme)
      }
    },
    [options?.storage]
  )

  const toggleTheme = useCallback(() => {
    const newTheme = isDark ? 'light' : 'dark'
    setTheme(newTheme)
  }, [isDark, setTheme])

  const initTheme = useCallback(() => {
    // Check storage first
    const savedTheme = options?.storage?.getItem?.(THEME_STORAGE_KEY) as Theme | null

    if (savedTheme) {
      setTheme(savedTheme)
    } else if (typeof window !== 'undefined') {
      // Check system preference (web only)
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
      setTheme(prefersDark ? 'dark' : 'light')
    } else {
      // Default to light theme
      setTheme('light')
    }
  }, [options?.storage, setTheme])

  useEffect(() => {
    initTheme()
  }, [initTheme])

  return {
    isDark,
    theme,
    setTheme,
    toggleTheme,
    initTheme
  }
}
