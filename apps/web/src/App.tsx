import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from '@cartulary/shared'
import { Toaster } from './components/ui/sonner'
import { Loader2 } from 'lucide-react'
import { ErrorBoundary } from './components/ErrorBoundary'
import Layout from './components/Layout'
import Login from './pages/Login'
import Register from './pages/Register'
import OIDCCallback from './pages/OIDCCallback'
import DocumentsList from './pages/DocumentsList'
import DocumentDetail from './pages/DocumentDetail'
import AdminPage from './pages/AdminPage'
import SettingsPage from './pages/SettingsPage'
import TagsPage from './pages/TagsPage'
import SharedDocuments from './pages/SharedDocuments'
import AboutPage from './pages/AboutPage'

// Protected route wrapper
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated())
  const initializing = useAuthStore((state) => state.initializing)

  // Show loading spinner while initializing auth
  if (initializing) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/auth/callback" element={<OIDCCallback />} />

          {/* Protected routes with layout */}
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route index element={<DocumentsList />} />
            <Route path="documents/:id" element={<DocumentDetail />} />
            <Route path="admin" element={<AdminPage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="tags" element={<TagsPage />} />
            <Route path="shared" element={<SharedDocuments />} />
            <Route path="about" element={<AboutPage />} />
          </Route>

          {/* Catch-all redirect */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        <Toaster />
      </BrowserRouter>
    </ErrorBoundary>
  )
}

export default App
