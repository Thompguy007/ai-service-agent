import { useEffect, useState } from 'react'
import { Routes, Route, Link, useLocation } from 'react-router-dom'

import Home from './pages/Home'
import Login from './pages/Login'
import CustomerDashboard from './pages/CustomerDashboard'
import StaffDashboard from './pages/StaffDashboard'
import AdminDashboard from './pages/AdminDashboard'
import ProtectedRoute from './components/ProtectedRoute'

type Role = 'customer' | 'staff' | 'admin'

function App() {
  const location = useLocation()
  const [role, setRole] = useState<Role | null>(null)

  useEffect(() => {
    const controller = new AbortController()

    async function loadUser() {
      const token = sessionStorage.getItem('access_token')

      if (!token) {
        setRole(null)
        return
      }

      try {
        const response = await fetch('http://127.0.0.1:8000/me', {
          headers: {
            Authorization: `Bearer ${token}`,
          },
          signal: controller.signal,
        })

        if (!response.ok) {
          throw new Error('Could not verify user')
        }

        const user: { role: Role } = await response.json()

        if (!controller.signal.aborted) {
          setRole(user.role)
        }
      } catch {
        if (!controller.signal.aborted) {
          setRole(null)
        }
      }
    }

    void loadUser()

    return () => controller.abort()
    }, [location.pathname])

  return (
    <div>
      <nav className="app-navbar">
        <Link to="/" className="app-brand">
          <span className="brand-icon">✦</span>
          ServiceAI
        </Link>

        <Link to="/">Home</Link>

        {role === null && (
          <Link to="/login">Login</Link>
        )}

        {role === 'customer' && (
          <Link to="/customer">My Dashboard</Link>
        )}

        {role === 'staff' && (
          <Link to="/staff">Staff Dashboard</Link>
        )}

        {role === 'admin' && (
          <Link to="/admin">Admin Dashboard</Link>
        )}

        {role !== null && (
  <button
    onClick={() => {
      sessionStorage.removeItem('access_token')
      sessionStorage.removeItem('active_conversation_id')
      setRole(null)
      window.location.href = '/login'
    }}
  >
    Logout
  </button>
)}
</nav>

      <Routes>
        {/* Public pages */}
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<Login />} />

        {/* Customer only */}
        <Route element={<ProtectedRoute allowedRole="customer" />}>
          <Route
            path="/customer"
            element={<CustomerDashboard />}
          />
        </Route>

        {/* Staff only */}
        <Route element={<ProtectedRoute allowedRole="staff" />}>
          <Route
            path="/staff"
            element={<StaffDashboard />}
          />
        </Route>

        {/* Admin only */}
        <Route element={<ProtectedRoute allowedRole="admin" />}>
          <Route
            path="/admin"
            element={<AdminDashboard />}
          />
        </Route>
      </Routes>
    </div>
  )
}

export default App
