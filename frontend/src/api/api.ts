/**
 * api.ts – Typed API client.
 * Always sends the Bearer token from Keycloak.
 * Never stores patient data in localStorage.
 */
import keycloak, { DEV_MOCK_TOKEN, DEV_SKIP_AUTH } from '../auth/keycloak'

const BACKEND = import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000'

async function authFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const token = DEV_SKIP_AUTH ? DEV_MOCK_TOKEN : keycloak.token
  if (!token) throw new Error('Not authenticated')
  return fetch(`${BACKEND}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
      ...(options.headers ?? {}),
    },
  })
}

export async function getPatients() {
  const r = await authFetch('/api/patients')
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getPatient(id: string) {
  const r = await authFetch(`/api/patients/${id}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function listDocuments(patientId: string) {
  const r = await authFetch(`/api/patients/${patientId}/documents`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getDocument(patientId: string, docId: string) {
  const r = await authFetch(`/api/patients/${patientId}/documents/${docId}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function startPipeline(patientId: string) {
  const r = await authFetch(`/api/patients/${patientId}/pipeline`, { method: 'POST' })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function pollJob(jobId: string) {
  const r = await authFetch(`/api/jobs/${jobId}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getDraft(patientId: string) {
  const r = await authFetch(`/api/patients/${patientId}/draft`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function patchDraft(patientId: string, body: { summary_text?: string; items_json?: object }) {
  const r = await authFetch(`/api/patients/${patientId}/draft`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function approveDraft(patientId: string) {
  const r = await authFetch(`/api/patients/${patientId}/approve`, {
    method: 'POST',
    body: JSON.stringify({ reviewed_and_confirmed: true }),
  })
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }))
    throw err
  }
  return r.json()
}

export async function getHistory(patientId: string) {
  const r = await authFetch(`/api/patients/${patientId}/history`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getVersion(patientId: string, versionId: string) {
  const r = await authFetch(`/api/patients/${patientId}/history/${versionId}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}
