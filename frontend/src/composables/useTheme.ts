import { ref, onMounted, watch } from 'vue'

const THEME_STORAGE_KEY = 'trapper-theme'

export type Theme = 'light' | 'dark'

const isDark = ref<boolean>(false)

export function useTheme() {
  const setTheme = (theme: Theme) => {
    isDark.value = theme === 'dark'

    if (theme === 'dark') {
      document.documentElement.classList.add('dark-mode')
    } else {
      document.documentElement.classList.remove('dark-mode')
    }

    localStorage.setItem(THEME_STORAGE_KEY, theme)
  }

  const toggleTheme = () => {
    const newTheme = isDark.value ? 'light' : 'dark'
    setTheme(newTheme)
  }

  const initTheme = () => {
    // Check localStorage first
    const savedTheme = localStorage.getItem(THEME_STORAGE_KEY) as Theme | null

    if (savedTheme) {
      setTheme(savedTheme)
    } else {
      // Check system preference
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
      setTheme(prefersDark ? 'dark' : 'light')
    }
  }

  onMounted(() => {
    initTheme()
  })

  return {
    isDark,
    theme: ref<Theme>(isDark.value ? 'dark' : 'light'),
    setTheme,
    toggleTheme,
    initTheme
  }
}
