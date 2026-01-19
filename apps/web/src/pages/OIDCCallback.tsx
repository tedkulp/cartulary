import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { authService } from '../services'
import { useAuthStore } from '@cartulary/shared'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'

export default function OIDCCallback() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [error, setError] = useState<string | null>(null)
  const fetchCurrentUser = useAuthStore((state) => state.fetchCurrentUser)

  useEffect(() => {
    const code = searchParams.get('code')
    const state = searchParams.get('state')

    if (!code) {
      const errorMsg = 'No authorization code received'
      setError(errorMsg)
      toast.error(errorMsg)
      setTimeout(() => navigate('/login'), 2000)
      return
    }

    // Prevent double-processing in React StrictMode
    // Check synchronously BEFORE any async work to avoid race conditions
    const processedKey = `oidc_processed_${code}`
    if (sessionStorage.getItem(processedKey)) {
      return
    }
    sessionStorage.setItem(processedKey, 'true')

    const handleCallback = async () => {
      console.log('handleCallback')
      try {
        const tokens = await authService.handleOIDCCallback(code, state || '')

        // Store tokens
        useAuthStore.setState({
          accessToken: tokens.access_token,
          refreshTokenValue: tokens.refresh_token,
        })
        localStorage.setItem('access_token', tokens.access_token)
        if (tokens.refresh_token) {
          localStorage.setItem('refresh_token', tokens.refresh_token)
        }

        // Fetch user info
        await fetchCurrentUser()

        // Redirect to home
        navigate('/')
      } catch (err: any) {
        // Clear the processed flag on error so user can retry
        sessionStorage.removeItem(processedKey)
        const errorMsg = err.response?.data?.detail || 'OIDC authentication failed'
        setError(errorMsg)
        toast.error(errorMsg)
        setTimeout(() => navigate('/login'), 2000)
      }
    }

    handleCallback()
  }, [searchParams, navigate, fetchCurrentUser])

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4">
      {error ? (
        <div className="rounded-md bg-destructive/15 p-4 text-destructive">
          {error}
        </div>
      ) : (
        <>
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="text-muted-foreground">Completing authentication...</p>
        </>
      )}
    </div>
  )
}
