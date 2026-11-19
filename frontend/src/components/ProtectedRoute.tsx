import { useEffect, useState } from 'react'
import { Navigate, Outlet } from 'react-router-dom'

type Role = 'customer' | 'staff' | 'admin'

type User = {
  id: number
  name: string
  email: string | null
  role: Role
}

type ProtectedRouteProps = {
  allowedRoles: Role[]
}

function ProtectedRoute({ allowedRoles }: ProtectedRouteProps) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true

    async function verifyUser() {
      const token = sessionStorage.getItem('access_token')

      if (!token) {
        sessionStorage.removeItem('active_conversation_id')
        setLoading(false)
        return
      }

      try {
        const response = await fetch('http://127.0.0.1:8000/me', {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        })

        if (!response.ok) {
          throw new Error('Authentication failed')
        }

        const data: User = await response.json()

        if (active) {
          setUser(data)
        }
      } catch {
      if (active) {
        sessionStorage.removeItem('access_token')
        sessionStorage.removeItem('active_conversation_id')
        }
      } finally {
        if (active) {
          setLoading(false)
  }
}
    }

    verifyUser()

    return () => {
      active = false
    }
  }, [])

  if (loading) {
    return <p>Checking authentication...</p>
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  if (!allowedRoles.includes(user.role)) {
    return <Navigate to={`/${user.role}`} replace />
  }

  return <Outlet />
}

export default ProtectedRoute
