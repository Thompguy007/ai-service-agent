export async function managementRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers)
  headers.set('Authorization', `Bearer ${sessionStorage.getItem('access_token')}`)
  if (options.body) headers.set('Content-Type', 'application/json')

  let response: Response
  try {
    response = await fetch(`http://127.0.0.1:8000${path}`, { ...options, headers })
  } catch (error) {
    if (options.signal?.aborted) throw error
    throw new Error('Could not reach the service. Please try again.', { cause: error })
  }
  if (response.status === 401) throw new Error('Your session expired. Sign in again.')
  if (response.status === 403) throw new Error('You do not have permission for this action.')
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new Error(typeof body?.detail === 'string' ? body.detail : 'Check the form and try again.')
  }
  return response.status === 204 ? undefined as T : response.json()
}

export function managementError(error: unknown) {
  return error instanceof Error ? error.message : 'Something went wrong. Please try again.'
}
