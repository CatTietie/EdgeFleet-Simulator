import { ReactNode } from 'react'
import { useAuthStore } from '../../store/auth'
import { useWebSocket } from '../../hooks/useWebSocket'

interface Props {
  children: ReactNode
}

export default function Layout({ children }: Props) {
  const { logout, orgId, role } = useAuthStore()
  useWebSocket()

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <header style={{
        background: '#1a1a2e',
        color: '#fff',
        padding: '12px 24px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
          <h1 style={{ margin: 0, fontSize: 20 }}>EdgeFleet Dashboard</h1>
          <nav style={{ display: 'flex', gap: 16 }}>
            <a href="/" style={{ color: '#88f' }}>Dashboard</a>
            <a href="/rules" style={{ color: '#88f' }}>Rules</a>
            <a href="/topology" style={{ color: '#88f' }}>Topology</a>
          </nav>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 12, opacity: 0.7 }}>Org: {orgId} | Role: {role}</span>
          <button onClick={logout} style={{ cursor: 'pointer' }}>Logout</button>
        </div>
      </header>
      <main style={{ flex: 1, padding: 24, background: '#f0f2f5' }}>
        {children}
      </main>
    </div>
  )
}
