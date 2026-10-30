import React, { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { getHistory, getVersion } from '../api/api'

interface VersionMeta { id: string; status: string; date: string; title: string }

export default function History() {
  const { id } = useParams<{ id: string }>()
  const nav = useNavigate()
  const [versions, setVersions] = useState<VersionMeta[]>([])
  const [selected, setSelected] = useState<[string, string] | null>(null)
  const [vA, setVA] = useState<any>(null)
  const [vB, setVB] = useState<any>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!id) return
    getHistory(id).then(d => setVersions(d.versions ?? [])).catch(e => setError(String(e)))
  }, [id])

  const compare = async (idA: string, idB: string) => {
    try {
      const [a, b] = await Promise.all([getVersion(id!, idA), getVersion(id!, idB)])
      setVA(a); setVB(b); setSelected([idA, idB])
    } catch (e) { setError(String(e)) }
  }

  const getSummaryExt = (comp: any) =>
    comp?.extension?.find((e: any) => e.url?.includes('summary-text'))?.valueString ?? JSON.stringify(comp, null, 2)

  return (
    <div>
      <button style={s.back} onClick={() => nav(`/patients/${id}`)}>← Patientenansicht</button>
      <h1 style={s.h1}>Verlauf</h1>
      {error && <div style={s.error}>{error}</div>}
      <p style={{ color: '#555', fontSize: '0.9rem' }}>Wählen Sie zwei Versionen zum Vergleich:</p>
      <table style={s.table}>
        <thead><tr><th>Status</th><th>Datum</th><th>Titel</th><th></th></tr></thead>
        <tbody>
          {versions.map((v, i) => (
            <tr key={v.id}>
              <td><span style={{ ...s.badge, background: v.status === 'final' ? '#27ae60' : '#f39c12' }}>{v.status}</span></td>
              <td>{v.date?.slice(0, 16)}</td>
              <td>{v.title}</td>
              <td>
                {i < versions.length - 1 &&
                  <button style={s.cmpBtn} onClick={() => compare(versions[i + 1].id, v.id)}>Vergleich mit vorher</button>
                }
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {selected && vA && vB && (
        <div style={s.diffWrap}>
          <h2 style={s.h2}>Vergleich</h2>
          <div style={s.diffGrid}>
            <div>
              <h3 style={s.h3}>Version A ({vA.status})</h3>
              <pre style={s.pre}>{getSummaryExt(vA)}</pre>
            </div>
            <div>
              <h3 style={s.h3}>Version B ({vB.status})</h3>
              <pre style={s.pre}>{getSummaryExt(vB)}</pre>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

const s: Record<string, React.CSSProperties> = {
  back: { background: 'none', border: 'none', color: '#1a3c5e', cursor: 'pointer', marginBottom: '0.5rem' },
  h1: { color: '#1a3c5e', marginBottom: '1rem' },
  h2: { color: '#1a3c5e' },
  h3: { color: '#333' },
  error: { color: '#c0392b', marginBottom: '1rem' },
  table: { width: '100%', borderCollapse: 'collapse', marginBottom: '1.5rem' },
  badge: { color: '#fff', padding: '2px 8px', borderRadius: 3, fontSize: '0.8rem' },
  cmpBtn: { background: '#1a3c5e', color: '#fff', border: 'none', padding: '2px 8px', borderRadius: 3, cursor: 'pointer', fontSize: '0.8rem' },
  diffWrap: { marginTop: '1.5rem' },
  diffGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' },
  pre: { background: '#f5f5f5', border: '1px solid #ddd', borderRadius: 4, padding: '1rem', overflow: 'auto', fontSize: '0.8rem', maxHeight: 500 },
}
