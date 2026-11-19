import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { managementError, managementRequest } from '../managementApi'

type Appointment = {
  id: number
  customer_name: string
  vehicle: string
  date: string
  time: string
  service_type: string
  status: string
}
type BookingCustomer = { id: number; name: string }
type Calendar = { appointments: Appointment[] }
type Directory = { customers: BookingCustomer[] }
type Filter = 'booked' | 'cancelled' | 'all'
type Editor = { mode: 'new' } | { mode: 'move' | 'cancel'; appointment: Appointment }

const hours = Array.from({ length: 9 }, (_, index) => `${String(index + 8).padStart(2, '0')}:00`)

export default function StaffDashboard() {
  const [appointments, setAppointments] = useState<Appointment[]>([])
  const [customers, setCustomers] = useState<BookingCustomer[]>([])
  const [filter, setFilter] = useState<Filter>('booked')
  const [search, setSearch] = useState('')
  const [editor, setEditor] = useState<Editor | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [reload, setReload] = useState(0)
  const [loadError, setLoadError] = useState('')
  const [actionError, setActionError] = useState('')
  const [notice, setNotice] = useState('')
  const editorHeading = useRef<HTMLHeadingElement>(null)

  useEffect(() => {
    if (editor) editorHeading.current?.focus()
  }, [editor])

  useEffect(() => {
    const controller = new AbortController()
    const { signal } = controller
    void Promise.all([
      managementRequest<Calendar>('/appointments', { signal }),
      managementRequest<Directory>('/staff/customers', { signal }),
    ]).then(([calendar, directory]) => {
      if (signal.aborted) return
      setAppointments(calendar.appointments)
      setCustomers(directory.customers)
      setLoadError('')
    }).catch((error: unknown) => {
      if (!signal.aborted) setLoadError(managementError(error))
    }).finally(() => {
      if (!signal.aborted) setLoading(false)
    })
    return () => controller.abort()
  }, [reload])

  const query = search.trim().toLowerCase()
  const visible = appointments.filter((appointment) =>
    (filter === 'all' || appointment.status === filter) &&
    [appointment.customer_name, appointment.service_type, appointment.vehicle, appointment.date]
      .some((value) => value.toLowerCase().includes(query)),
  )

  function openEditor(next: Editor | null) {
    setEditor(next)
    setActionError('')
    setNotice('')
  }

  async function submitAppointment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!editor || saving) return
    const data = new FormData(event.currentTarget)
    setSaving(true)
    setActionError('')
    try {
      if (editor.mode === 'new') {
        await managementRequest('/staff/appointments', {
          method: 'POST',
          body: JSON.stringify({
            customer_id: Number(data.get('customer')),
            appointment_date: data.get('date'),
            appointment_time: data.get('time'),
            service_type: data.get('service'),
          }),
        })
        setFilter('booked')
        setSearch('')
        setNotice('Appointment booked.')
      } else if (editor.mode === 'move') {
        await managementRequest(`/staff/appointments/${editor.appointment.id}`, {
          method: 'PATCH',
          body: JSON.stringify({ new_date: data.get('date'), new_time: data.get('time') }),
        })
        setNotice('Appointment rescheduled.')
      } else {
        await managementRequest(`/staff/appointments/${editor.appointment.id}/cancel`, {
          method: 'POST',
        })
        setNotice('Appointment cancelled.')
      }
      setEditor(null)
      refresh()
    } catch (error) {
      setActionError(managementError(error))
    } finally {
      setSaving(false)
    }
  }

  function refresh() {
    setLoading(true)
    setReload((value) => value + 1)
  }

  const selected = editor && editor.mode !== 'new' ? editor.appointment : null

  return (
    <main className="management-page">
      <header className="management-heading">
        <div><h1>Staff Dashboard</h1><p>Manage the workshop’s service appointments.</p></div>
        <button className="management-primary" disabled={loading || Boolean(loadError) || saving || customers.length === 0}
          onClick={() => openEditor({ mode: 'new' })}>New booking</button>
      </header>

      {notice && <p role="status" className="management-notice">{notice}</p>}
      {editor && (
        <section className="management-panel" aria-labelledby="booking-editor">
          <h2 id="booking-editor" ref={editorHeading} tabIndex={-1}>{editor.mode === 'new' ? 'New booking' : editor.mode === 'move' ? 'Reschedule booking' : 'Cancel booking'}</h2>
          {selected && <p>{selected.customer_name} · {selected.service_type} · {selected.date} at {selected.time}</p>}
          <form key={selected ? `${editor.mode}-${selected.id}` : 'new'} onSubmit={submitAppointment}>
            <div className="management-fields">
              {editor.mode === 'new' && <>
                <label><span id="booking-customer-label">Customer</span>
                  <select name="customer" aria-labelledby="booking-customer-label" required defaultValue="">
                    <option value="" disabled>Select a customer</option>
                    {customers.map((customer) => <option key={customer.id} value={customer.id}>{customer.name} (#{customer.id})</option>)}
                  </select>
                </label>
                <label>Service<input name="service" required maxLength={120} placeholder="e.g. Oil change" /></label>
              </>}
              {editor.mode !== 'cancel' && <>
                <label>Date<input type="date" name="date" required defaultValue={selected?.date} /></label>
                <label><span id="booking-time-label">Time</span>
                  <select name="time" aria-labelledby="booking-time-label" required defaultValue={selected?.time ?? ''}>
                    <option value="" disabled>Select a time</option>
                    {hours.map((hour) => <option key={hour}>{hour}</option>)}
                  </select>
                </label>
              </>}
            </div>
            {editor.mode === 'cancel' && <p>This frees the time slot and leaves the cancellation in the appointment history.</p>}
            {actionError && <p role="alert" className="management-error">{actionError}</p>}
            <div className="management-actions">
              <button className={editor.mode === 'cancel' ? 'management-danger' : 'management-primary'} disabled={saving}>
                {saving ? 'Saving…' : editor.mode === 'cancel' ? 'Confirm cancellation' : 'Save booking'}
              </button>
              <button type="button" disabled={saving} onClick={() => openEditor(null)}>Close</button>
            </div>
          </form>
        </section>
      )}

      <section className="management-panel" aria-labelledby="calendar-title" aria-busy={loading}>
        <h2 id="calendar-title">Service calendar</h2>
        <div className="management-filters">
          <label>Search<input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Customer, service, vehicle or date" /></label>
          <label><span id="booking-status-label">Status</span><select aria-labelledby="booking-status-label" value={filter} onChange={(event) => setFilter(event.target.value as Filter)}>
            <option value="booked">Booked</option><option value="cancelled">Cancelled</option><option value="all">All</option>
          </select></label>
          <button onClick={refresh} disabled={loading || saving}>Refresh</button>
        </div>
        {loading && <p role="status">Loading appointments…</p>}
        {!loading && loadError && <p role="alert" className="management-error">{loadError}</p>}
        {!loading && !loadError && visible.length === 0 && <p>No appointments match these filters.</p>}
        {!loading && !loadError && visible.length > 0 && <div className="management-table" role="region" aria-label="Appointments table" tabIndex={0}>
          <table>
            <thead><tr><th scope="col">Date &amp; time</th><th scope="col">Customer</th><th scope="col">Service</th><th scope="col">Status</th><th scope="col">Actions</th></tr></thead>
            <tbody>{visible.map((appointment) => (
              <tr key={appointment.id}>
                <td>{appointment.date} <strong>{appointment.time}</strong></td>
                <td>{appointment.customer_name}<small>{appointment.vehicle}</small></td>
                <td>{appointment.service_type}</td>
                <td><span className={`appointment-status status-${appointment.status}`}>{appointment.status}</span></td>
                <td>{appointment.status === 'booked' && <div className="management-actions">
                  <button disabled={saving} onClick={() => openEditor({ mode: 'move', appointment })}>Reschedule</button>
                  <button disabled={saving} onClick={() => openEditor({ mode: 'cancel', appointment })}>Cancel</button>
                </div>}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>}
      </section>
    </main>
  )
}
