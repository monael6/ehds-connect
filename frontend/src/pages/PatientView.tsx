import React, { useEffect, useState, useRef } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { listDocuments, startPipeline, pollJob } from '../api/api'

interface DocSummary { id: string; source_doc_id: string; type: string; date: string; description: string }

export default function PatientView() {
  const { id } = useParams<{ id: string }>()
  const nav = useNavigate()
  const [docs, setDocs] = useState<DocSummary[]>([])
  const [error, setError] = useState('')
  const [jobStatus, setJobStatus] = useState<string | null>(null)
  const [jobProgress, setJobProgress] = useState(0)
  const [jobStep, setJobStep] = useState('')
  const pollRef = useRef<number | null>(null)

  useEffect(() => {
    if (!id) return
    listDocuments(id).then(d => setDocs(d.documents ?? [])).catch(e => setError(String(e)))
  }, [id])

  const handleStartPipeline = async () => {
    if (!id) return
    try {
      setError('')
      const { job_id } = await startPipeline(id)
      setJobStatus('running')
      pollRef.current = window.setInterval(async () => {
        const job = await pollJob(job_id)
        setJobProgress(job.progress)
        setJobStep(job.step)
        if (job.status === 'completed') {
          clearInterval(pollRef.current!)
          setJobStatus('completed')
          nav(`/patients/${id}/review`)
        } else if (job.status === 'failed') {
          clearInterval(pollRef.current!)
          setJobStatus('failed')
          setError(`Pipeline fehlgeschlagen: ${job.error}`)
        }
      }, 2000)
    } catch (e) { setError(String(e)) }
  }

  return (
    <div>
      <button style={s.back} onClick={() => nav('/patients')}>← Patientenliste</button>
      <h1 style={s.h1}>Dokumente</h1>
      {error && <div style={s.error}>{error}</div>}

      <button
        style={{ ...s.btn, opacity: jobStatus === 'running' ? 0.6 : 1 }}
        disabled={jobStatus === 'running'}
        onClick={handleStartPipeline}
      >
        {jobStatus === 'running' ? `${jobStep} … ${jobProgress}%` : 'Zusammenfassung erstellen'}
      </button>

      {docs.length === 0 && <p>Keine Dokumente gefunden.</p>}
      <ul style={s.list}>
        {docs.map(d => (
          <li key={d.id} style={s.item}>
            <span style={s.type}>{d.type}</span>
            <span style={s.desc}>{d.description}</span>
            <span style={s.date}>{d.date?.slice(0, 10)}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

const s: Record<string, React.CSSProperties> = {
  back: { background: 'none', border: 'none', color: '#1a3c5e', cursor: 'pointer', marginBottom: '0.5rem', fontSize: '0.9rem' },
  h1: { color: '#1a3c5e', marginBottom: '1rem' },
  error: { color: '#c0392b', margin: '0.5rem 0' },
  btn: { background: '#1a3c5e', color: '#fff', border: 'none', padding: '0.6rem 1.2rem', borderRadius: 4, cursor: 'pointer', marginBottom: '1.5rem', fontSize: '0.95rem' },
  list: { listStyle: 'none', padding: 0, margin: 0 },
  item: { display: 'grid', gridTemplateColumns: '160px 1fr 100px', gap: '1rem', padding: '0.6rem 0', borderBottom: '1px solid #e5e9f0', alignItems: 'center' },
  type: { fontSize: '0.75rem', background: '#e8f0fe', color: '#1a3c5e', padding: '2px 6px', borderRadius: 3 },
  desc: { fontSize: '0.9rem' },
  date: { fontSize: '0.8rem', color: '#777', textAlign: 'right' as const },
}
