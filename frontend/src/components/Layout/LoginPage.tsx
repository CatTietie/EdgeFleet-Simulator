import { useState } from 'react'
import { useAuthStore } from '../../store/auth'

export default function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const login = useAuthStore((s) => s.login)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    try {
      await login(username, password)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Login failed')
    }
  }

  return (
    <div style={{
      display: 'flex', justifyContent: 'center', alignItems: 'center',
      minHeight: '100vh', background: '#1a1a2e',
    }}>
      <form onSubmit={handleSubmit} style={{
        background: '#fff', padding: 32, borderRadius: 8,
        minWidth: 320, display: 'flex', flexDirection: 'column', gap: 16,
      }}>
        <h2 style={{ margin: 0, textAlign: 'center' }}>EdgeFleet Login</h2>
        {error && <div style={{ color: 'red', fontSize: 14 }}>{error}</div>}
        <input
          type="text"
          placeholder="Username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          style={{ padding: 8, borderRadius: 4, border: '1px solid #ccc' }}
        />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          style={{ padding: 8, borderRadius: 4, border: '1px solid #ccc' }}
        />
        <button type="submit" style={{
          padding: 10, background: '#4a4ae8', color: '#fff',
          border: 'none', borderRadius: 4, cursor: 'pointer',
        }}>
          Sign In
        </button>
      </form>
    </div>
  )
}
