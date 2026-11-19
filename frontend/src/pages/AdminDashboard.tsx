import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { managementError, managementRequest } from '../managementApi'

type Customer = {
  id: number
  name: string
  phone: string
  vehicle: string
  email: string | null
  role: 'customer' | 'staff' | 'admin'
}
type Directory = { customers: Customer[] }
type Editor = { mode: 'new' } | { mode: 'edit' | 'delete'; customer: Customer }

export default function AdminDashboard() {
  const [customers, setCustomers] = useState<Customer[]>([])
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
    void managementRequest<Directory>('/customers', { signal }).then((directory) => {
      if (signal.aborted) return
      setCustomers(directory.customers.filter((customer) => customer.role === 'customer'))
      setLoadError('')
    }).catch((error: unknown) => {
      if (!signal.aborted) setLoadError(managementError(error))
    }).finally(() => {
      if (!signal.aborted) setLoading(false)
    })
    return () => controller.abort()
  }, [reload])

  const query = search.trim().toLowerCase()
  const visible = customers.filter((customer) =>
    [customer.name, customer.email ?? '', customer.phone, customer.vehicle]
      .some((value) => value.toLowerCase().includes(query)),
  )
  const selected = editor && editor.mode !== 'new' ? editor.customer : null

  function openEditor(next: Editor | null) {
    setEditor(next)
    setActionError('')
    setNotice('')
  }

  function refresh() {
    setLoading(true)
    setReload((value) => value + 1)
  }

  async function submitCustomer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!editor || saving) return
    const data = new FormData(event.currentTarget)
    setSaving(true)
    setActionError('')
    try {
      if (editor.mode === 'delete') {
        await managementRequest(`/admin/customers/${editor.customer.id}`, { method: 'DELETE' })
        setNotice('Customer deleted.')
      } else {
        const profile = { name: data.get('name'), phone: data.get('phone'), vehicle: data.get('vehicle') }
        if (editor.mode === 'new') {
          const email = data.get('email')
          const password = data.get('password')
          if (Boolean(email) !== Boolean(password)) {
            setActionError('Provide both email and password to enable login.')
            return
          }
          await managementRequest('/customers', {
            method: 'POST',
            body: JSON.stringify({ ...profile, email: email || null, password: password || null }),
          })
          setSearch('')
          setNotice('Customer created.')
        } else {
          await managementRequest(`/customers/${editor.customer.id}`, {
            method: 'PATCH', body: JSON.stringify(profile),
          })
          setNotice('Customer updated.')
        }
      }
      setEditor(null)
      refresh()
    } catch (error) {
      setActionError(managementError(error))
    } finally {
      setSaving(false)
    }
  }

  return (
    <main className="management-page">
      <header className="management-heading">
        <div><h1>Admin Dashboard</h1><p>Manage customer profiles and create customer logins.</p></div>
        <button className="management-primary" disabled={saving} onClick={() => openEditor({ mode: 'new' })}>New customer</button>
      </header>

      {notice && <p role="status" className="management-notice">{notice}</p>}
      {editor && (
        <section className="management-panel" aria-labelledby="customer-editor">
          <h2 id="customer-editor" ref={editorHeading} tabIndex={-1}>{editor.mode === 'new' ? 'New customer' : editor.mode === 'edit' ? 'Edit customer' : 'Delete customer'}</h2>
          <form key={selected ? `${editor.mode}-${selected.id}` : 'new'} onSubmit={submitCustomer}>
            {editor.mode === 'delete' ? (
              <p>Delete {editor.customer.name}? Customers with appointments or chat history are kept.</p>
            ) : (
              <>
                <div className="management-fields">
                  <label>Name<input name="name" required maxLength={120} defaultValue={selected?.name} /></label>
                  <label>Phone<input name="phone" type="tel" required maxLength={40} defaultValue={selected?.phone} /></label>
                  <label>Vehicle<input name="vehicle" required maxLength={120} defaultValue={selected?.vehicle} /></label>
                </div>
                {editor.mode === 'new' && <fieldset className="management-fields">
                  <legend>Optional customer login</legend>
                  <label>Email<input name="email" type="email" autoComplete="off" maxLength={254} /></label>
                  <label>Password (8–128 characters)<input name="password" type="password" autoComplete="new-password" minLength={8} maxLength={128} /></label>
                </fieldset>}
              </>
            )}
            {actionError && <p role="alert" className="management-error">{actionError}</p>}
            <div className="management-actions">
              <button className={editor.mode === 'delete' ? 'management-danger' : 'management-primary'} disabled={saving}>
                {saving ? 'Saving…' : editor.mode === 'delete' ? 'Confirm deletion' : 'Save customer'}
              </button>
              <button type="button" disabled={saving} onClick={() => openEditor(null)}>Close</button>
            </div>
          </form>
        </section>
      )}

      <section className="management-panel" aria-labelledby="customer-title" aria-busy={loading}>
        <h2 id="customer-title">Customers</h2>
        <div className="management-filters">
          <label>Search<input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Name, email, phone or vehicle" /></label>
          <button onClick={refresh} disabled={loading || saving}>Refresh</button>
        </div>
        {loading && <p role="status">Loading customers…</p>}
        {!loading && loadError && <p role="alert" className="management-error">{loadError}</p>}
        {!loading && !loadError && visible.length === 0 && <p>No customers match this search.</p>}
        {!loading && !loadError && visible.length > 0 && <div className="management-table" role="region" aria-label="Customers table" tabIndex={0}>
          <table>
            <thead><tr><th scope="col">Customer</th><th scope="col">Phone</th><th scope="col">Vehicle</th><th scope="col">Actions</th></tr></thead>
            <tbody>{visible.map((customer) => (
              <tr key={customer.id}>
                <td><strong>{customer.name}</strong><small>{customer.email ?? 'No login email'}</small></td>
                <td>{customer.phone}</td><td>{customer.vehicle}</td>
                <td><div className="management-actions">
                  <button disabled={saving} onClick={() => openEditor({ mode: 'edit', customer })}>Edit</button>
                  <button disabled={saving} onClick={() => openEditor({ mode: 'delete', customer })}>Delete</button>
                </div></td>
              </tr>
            ))}</tbody>
          </table>
        </div>}
      </section>
    </main>
  )
}
