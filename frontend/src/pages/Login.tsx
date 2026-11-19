import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

type User = {
  id: number
  name: string
  email: string | null
  role: 'customer' | 'staff' | 'admin'
}

function Login() {
  const navigate = useNavigate()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleLogin(event: React.SubmitEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setLoading(true)

    try {
      // 1. Authenticate with FastAPI
      const loginResponse = await fetch('http://127.0.0.1:8000/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password }),
      })

      if (!loginResponse.ok) {
        throw new Error('Invalid email or password')
      }

      const loginData: { access_token: string } =
        await loginResponse.json()

      const token = loginData.access_token

      // 2. Fetch the authenticated user's identity and role
      const meResponse = await fetch('http://127.0.0.1:8000/me', {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })

      if (!meResponse.ok) {
        throw new Error('Could not retrieve user profile')
      }

      const user: User = await meResponse.json()

      // 3. Clear previous conversation and store the new token
      sessionStorage.removeItem('active_conversation_id')
      sessionStorage.setItem('access_token', token)

      // 4. Navigate based on the user's role
      switch (user.role) {
        case 'admin':
          navigate('/admin', { replace: true })
          break

        case 'staff':
          navigate('/staff', { replace: true })
          break

        case 'customer':
          navigate('/customer', { replace: true })
          break

        default:
          sessionStorage.removeItem('access_token')
          throw new Error('Unknown user role')
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Login failed'
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <main style={{ maxWidth: '400px', margin: '60px auto' }}>
      <h1>AI Service Agent</h1>
      <h2>Login</h2>

      <form onSubmit={handleLogin}>
        <div style={{ marginBottom: '16px' }}>
          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
            autoComplete="username"
            style={{ display: 'block', width: '100%', padding: '10px' }}
          />
        </div>

        <div style={{ marginBottom: '16px' }}>
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
            autoComplete="current-password"
            style={{ display: 'block', width: '100%', padding: '10px' }}
          />
        </div>

        <button type="submit" disabled={loading}>
          {loading ? 'Logging in...' : 'Login'}
        </button>

        {error && (
          <p role="alert" style={{ color: 'red' }}>
            {error}
          </p>
        )}
      </form>
    </main>
  )
}

export default Login