import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@cartulary/shared'
import { authService } from '../services'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { Shield } from 'lucide-react'

export default function Login() {
  const navigate = useNavigate()
  const login = useAuthStore((state) => state.login)
  const error = useAuthStore((state) => state.error)
  const loading = useAuthStore((state) => state.loading)

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [oidcEnabled, setOidcEnabled] = useState(false)
  const [oidcLoading, setOidcLoading] = useState(false)

  useEffect(() => {
    // Check if OIDC is enabled
    const checkOIDC = async () => {
      try {
        const config = await authService.getOIDCConfig()
        setOidcEnabled(config.enabled)
      } catch (err) {
        // OIDC not available
        setOidcEnabled(false)
      }
    }
    checkOIDC()
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const success = await login({ email, password })
    if (success) {
      navigate('/')
    }
  }

  const handleOIDCLogin = async () => {
    setOidcLoading(true)
    try {
      await authService.initiateOIDCLogin()
    } catch (err) {
      console.error('OIDC login failed:', err)
      setOidcLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Cartulary Login</CardTitle>
          <CardDescription>Sign in to access your documents</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="rounded-md bg-destructive/15 p-3 text-sm text-destructive">
                {error}
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
              />
            </div>

            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? 'Logging in...' : 'Login'}
            </Button>

            {oidcEnabled && (
              <>
                <div className="relative">
                  <div className="absolute inset-0 flex items-center">
                    <Separator />
                  </div>
                  <div className="relative flex justify-center text-xs uppercase">
                    <span className="bg-background px-2 text-muted-foreground">
                      Or continue with
                    </span>
                  </div>
                </div>

                <Button
                  type="button"
                  variant="outline"
                  className="w-full"
                  onClick={handleOIDCLogin}
                  disabled={oidcLoading}
                >
                  <Shield className="mr-2 h-4 w-4" />
                  {oidcLoading ? 'Redirecting...' : 'Single Sign-On (SSO)'}
                </Button>
              </>
            )}

            <Button
              type="button"
              variant="ghost"
              className="w-full"
              onClick={() => navigate('/register')}
            >
              Create an account
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
