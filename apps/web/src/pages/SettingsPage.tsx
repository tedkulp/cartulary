import { useState } from 'react'
import { useAuthStore } from '@cartulary/shared'
import { authService } from '../services'
import { toast } from 'sonner'
import { Shield } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

export default function SettingsPage() {
  const user = useAuthStore((state) => state.user)
  const fetchCurrentUser = useAuthStore((state) => state.fetchCurrentUser)

  const isOidcUser = !!user?.oidc_sub

  const [fullName, setFullName] = useState(user?.full_name ?? '')
  const [email, setEmail] = useState(user?.email ?? '')
  const [, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [saving, setSaving] = useState(false)

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      await authService.updateProfile({
        full_name: fullName || null,
        email: email || undefined,
      })
      await fetchCurrentUser()
      toast.success('Profile updated')
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to update profile')
    } finally {
      setSaving(false)
    }
  }

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault()
    if (newPassword !== confirmPassword) {
      toast.error('New passwords do not match')
      return
    }
    if (!newPassword) {
      toast.error('New password cannot be empty')
      return
    }
    setSaving(true)
    try {
      await authService.updateProfile({ password: newPassword })
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
      toast.success('Password changed')
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to change password')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="container mx-auto py-6 max-w-2xl space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Settings</h1>
        <p className="text-muted-foreground">Manage your account</p>
      </div>

      {isOidcUser && (
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3 text-muted-foreground">
              <Shield className="h-5 w-5 shrink-0" />
              <p className="text-sm">
                Your account is managed by your identity provider. Profile details cannot be changed here.
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Profile</CardTitle>
          <CardDescription>Update your name and email address</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSaveProfile} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="full_name">Full name</Label>
              <Input
                id="full_name"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                disabled={isOidcUser}
                placeholder="Your name"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={isOidcUser}
                autoComplete="email"
              />
            </div>
            {!isOidcUser && (
              <Button type="submit" disabled={saving}>
                {saving ? 'Saving…' : 'Save profile'}
              </Button>
            )}
          </form>
        </CardContent>
      </Card>

      {!isOidcUser && (
        <Card>
          <CardHeader>
            <CardTitle>Change password</CardTitle>
            <CardDescription>Choose a new password for your account</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleChangePassword} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="new_password">New password</Label>
                <Input
                  id="new_password"
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  autoComplete="new-password"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="confirm_password">Confirm new password</Label>
                <Input
                  id="confirm_password"
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  autoComplete="new-password"
                />
              </div>
              <Button type="submit" disabled={saving || !newPassword}>
                {saving ? 'Saving…' : 'Change password'}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
