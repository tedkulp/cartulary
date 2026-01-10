import { Outlet } from 'react-router-dom'
import AppHeader from './AppHeader'

export default function Layout() {
  return (
    <div className="flex flex-col min-h-screen">
      <AppHeader />
      <main className="flex-1 container mx-auto p-6">
        <Outlet />
      </main>
    </div>
  )
}
