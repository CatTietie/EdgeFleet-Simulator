import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './store/auth'
import Layout from './components/Layout/Layout'
import LoginPage from './components/Layout/LoginPage'
import DashboardPage from './components/Dashboard/DashboardPage'
import RulesPage from './components/Rules/RulesPage'
import TopologyPage from './components/Topology/TopologyPage'

function App() {
  const token = useAuthStore((s) => s.token)

  if (!token) {
    return (
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="*" element={<Navigate to="/login" />} />
        </Routes>
      </BrowserRouter>
    )
  }

  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/rules" element={<RulesPage />} />
          <Route path="/topology" element={<TopologyPage />} />
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}

export default App
