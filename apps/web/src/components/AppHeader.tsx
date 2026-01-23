import { useNavigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '@cartulary/shared'
import { Button } from './ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from './ui/dropdown-menu'
  import { FileText, Tags, Share2, Settings as SettingsIcon, User, LogOut, Info, MessageSquare } from 'lucide-react'

export default function AppHeader() {
  const navigate = useNavigate()
  const location = useLocation()
  const user = useAuthStore((state) => state.user)
  const logout = useAuthStore((state) => state.logout)

  const isActive = (path: string) => location.pathname === path

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  return (
    <header className="border-b">
      <div className="flex h-16 items-center px-4 gap-4">
        <div className="font-bold text-xl">Cartulary</div>

        <nav className="flex items-center gap-2 flex-1">
          <Button
            variant={isActive('/') ? 'secondary' : 'ghost'}
            onClick={() => navigate('/')}
          >
            <FileText className="mr-2 h-4 w-4" />
            Documents
          </Button>
          <Button
            variant={isActive('/chat') ? 'secondary' : 'ghost'}
            onClick={() => navigate('/chat')}
          >
            <MessageSquare className="mr-2 h-4 w-4" />
            Chat
          </Button>
          <Button
            variant={isActive('/tags') ? 'secondary' : 'ghost'}
            onClick={() => navigate('/tags')}
          >
            <Tags className="mr-2 h-4 w-4" />
            Tags
          </Button>
          <Button
            variant={isActive('/shared') ? 'secondary' : 'ghost'}
            onClick={() => navigate('/shared')}
          >
            <Share2 className="mr-2 h-4 w-4" />
            Shared
          </Button>
          {(user?.is_superuser || user?.roles?.some(r => r.name === 'admin')) && (
            <Button
              variant={isActive('/admin') ? 'secondary' : 'ghost'}
              onClick={() => navigate('/admin')}
            >
              <SettingsIcon className="mr-2 h-4 w-4" />
              Admin
            </Button>
          )}
        </nav>

        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">
            {user?.full_name || user?.email}
          </span>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon">
                <User className="h-5 w-5" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => navigate('/settings')}>
                <SettingsIcon className="mr-2 h-4 w-4" />
                Settings
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => navigate('/about')}>
                <Info className="mr-2 h-4 w-4" />
                About
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={handleLogout}>
                <LogOut className="mr-2 h-4 w-4" />
                Logout
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  )
}
