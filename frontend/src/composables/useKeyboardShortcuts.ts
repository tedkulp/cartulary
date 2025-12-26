import { onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'

export interface KeyboardShortcut {
  key: string
  ctrl?: boolean
  shift?: boolean
  alt?: boolean
  meta?: boolean
  description: string
  action: () => void
}

export function useKeyboardShortcuts(shortcuts: KeyboardShortcut[]) {
  const handleKeydown = (event: KeyboardEvent) => {
    for (const shortcut of shortcuts) {
      const ctrlMatch = shortcut.ctrl === undefined || shortcut.ctrl === (event.ctrlKey || event.metaKey)
      const shiftMatch = shortcut.shift === undefined || shortcut.shift === event.shiftKey
      const altMatch = shortcut.alt === undefined || shortcut.alt === event.altKey
      const metaMatch = shortcut.meta === undefined || shortcut.meta === event.metaKey
      const keyMatch = shortcut.key.toLowerCase() === event.key.toLowerCase()

      if (ctrlMatch && shiftMatch && altMatch && metaMatch && keyMatch) {
        event.preventDefault()
        shortcut.action()
        break
      }
    }
  }

  onMounted(() => {
    window.addEventListener('keydown', handleKeydown)
  })

  onUnmounted(() => {
    window.removeEventListener('keydown', handleKeydown)
  })

  return { shortcuts }
}

// Global navigation shortcuts
export function useGlobalShortcuts() {
  const router = useRouter()

  const shortcuts: KeyboardShortcut[] = [
    {
      key: 'd',
      ctrl: true,
      description: 'Go to Documents',
      action: () => router.push('/documents')
    },
    {
      key: 't',
      ctrl: true,
      description: 'Go to Tags',
      action: () => router.push('/tags')
    },
    {
      key: 's',
      ctrl: true,
      description: 'Go to Settings',
      action: () => router.push('/settings')
    },
    {
      key: 'h',
      ctrl: true,
      description: 'Go to Home',
      action: () => router.push('/')
    },
    {
      key: '/',
      ctrl: true,
      description: 'Focus search',
      action: () => {
        const searchInput = document.querySelector('input[type="text"]') as HTMLInputElement
        if (searchInput) {
          searchInput.focus()
        }
      }
    }
  ]

  return useKeyboardShortcuts(shortcuts)
}
