import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getPatients } from '../api/api'

interface PatientSummary { id: string; family: string; given: string; birthDate: string; gender: string }

export default function PatientList() {
  const [patients, setPatients] = useState<PatientSummary[]>([])
  const [error, setError] = useState('')
  const nav = useNavigate()

  useEffect(() => {
    getPatients().then(d => setPatients(d.patients ?? [])).catch(e => setError(String(e)))
  }, [])

  return (
    <div>
      <h1 style={s.h1}>Meine Patienten</h1>
      {error && <div style={s.error}>{error}</div>}
      <div style={s.grid}>
        {patients.map(p => (
          <div key={p.id} style={s.card} onClick={() => nav(`/patients/${p.id}`)}>
            <div style={s.name}>{p.family}, {p.given}</div>
            <div style={s.detail}>*{p.birthDate} · {p.gender}</div>
          </div>
        ))}
        {patients.length === 0 && !error && <p>Keine Patienten zugewiesen.</p>}
      </div>
    </div>
  )
}

const s: Record<string, React.CSSProperties> = {
  h1: { marginBottom: '1rem', color: '#1a3c5e' },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(260px,1fr))', gap: '1rem' },
  card: { background: '#f5f8fc', border: '1px solid #d0dce9', borderRadius: 6, padding: '1rem', cursor: 'pointer' },
  name: { fontWeight: 600, fontSize: '1rem', color: '#1a3c5e' },
  detail: { color: '#555', fontSize: '0.875rem', marginTop: 4 },
  error: { color: '#c0392b', marginBottom: '1rem' },
}
