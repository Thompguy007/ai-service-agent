import { useEffect, useState } from 'react'
import Chatbot from '../components/Chatbot'
type Appointment = {
  id: number
  customer_name: string
  vehicle: string
  date: string
  time: string
  service_type: string
  status: string
}

function CustomerDashboard() {
  const [appointments, setAppointments] = useState<Appointment[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  function loadAppointments() {
    const token = sessionStorage.getItem('access_token')

    void fetch('http://127.0.0.1:8000/appointments', {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    })

      .then(async (response) => {
        if (!response.ok) {
          throw new Error('Could not load appointments')
        }

        const data = await response.json()
        setAppointments(data.appointments)
        setError('')
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'Something went wrong')
      })
      .finally(() => {
        setLoading(false)
      })
  }

  useEffect(() => {
    loadAppointments()
  }, [])

  return (
    <main className="customer-dashboard">
      <h1>👤 Customer Dashboard</h1>
      <h2>My Appointments</h2>

      {loading && <p>Loading appointments...</p>}

      {error && <p style={{ color: 'red' }}>{error}</p>}

      {!loading && !error && appointments.length === 0 && (
        <p>You have no appointments.</p>
      )}

      {!loading && !error && appointments.map((appointment) => (
        <div
          key={appointment.id}
          className="appointment-card"
        >
          <h3>{appointment.service_type}</h3>
          <p><strong>Vehicle:</strong> {appointment.vehicle}</p>
          <p><strong>Date:</strong> {appointment.date}</p>
          <p><strong>Time:</strong> {appointment.time}</p>
          <p>
            <strong>Status: </strong>
            <span
              className={`appointment-status ${
                appointment.status === 'booked'
                  ? 'status-booked'
                  : appointment.status === 'cancelled'
                    ? 'status-cancelled'
                    : 'status-other'
              }`}
            >
              {appointment.status}
            </span>
          </p>
        </div>
      ))}
      <section className="dashboard-ai-section">
  <div className="dashboard-ai-header">
    <span className="dashboard-ai-label">AI-POWERED ASSISTANCE</span>
    <h2>Your personal service assistant</h2>
    <p>
      Book appointments, reschedule visits, or ask questions
      about your vehicle.
    </p>
  </div>

  <Chatbot onAppointmentsChanged={loadAppointments} />
</section>
    </main>
  )
}

export default CustomerDashboard
