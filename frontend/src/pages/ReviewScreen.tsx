import React, { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { getDraft, patchDraft, approveDraft, listDocuments, getDocument } from '../api/api'

// ── Lightweight Markdown renderer (no external deps) ─────────────────────────
// Handles: headings (#/##/###), bold (**text**), blockquote (>), horizontal
// rule (---), bullet list (- item), and plain paragraphs.
function MarkdownView({ text, style }: { text: string; style?: React.CSSProperties }) {
  const lines = text.split('\n')
  const elements: React.ReactNode[] = []
  let i = 0

  const inlineBold = (raw: string): React.ReactNode => {
    const parts = raw.split(/\*\*(.*?)\*\*/g)
    return parts.map((p, j) => j % 2 === 1 ? <strong key={j}>{p}</strong> : p)
  }

  while (i < lines.length) {
    const line = lines[i]

    if (/^### /.test(line)) {
      elements.push(<h3 key={i} style={mdS.h3}>{inlineBold(line.slice(4))}</h3>)
    } else if (/^## /.test(line)) {
      elements.push(<h2 key={i} style={mdS.h2}>{inlineBold(line.slice(3))}</h2>)
    } else if (/^# /.test(line)) {
      elements.push(<h1 key={i} style={mdS.h1}>{inlineBold(line.slice(2))}</h1>)
    } else if (/^> /.test(line)) {
      elements.push(
        <blockquote key={i} style={mdS.blockquote}>
          {inlineBold(line.slice(2))}
        </blockquote>
      )
    } else if (/^---+$/.test(line.trim())) {
      elements.push(<hr key={i} style={mdS.hr} />)
    } else if (/^[-*] /.test(line)) {
      // Collect consecutive list items
      const listItems: React.ReactNode[] = []
      while (i < lines.length && /^[-*] /.test(lines[i])) {
        listItems.push(<li key={i} style={mdS.li}>{inlineBold(lines[i].slice(2))}</li>)
        i++
      }
      elements.push(<ul key={`ul-${i}`} style={mdS.ul}>{listItems}</ul>)
      continue
    } else if (line.trim() === '') {
      elements.push(<div key={i} style={{ height: '0.5rem' }} />)
    } else {
      elements.push(<p key={i} style={mdS.p}>{inlineBold(line)}</p>)
    }
    i++
  }

  return <div style={{ ...mdS.root, ...style }}>{elements}</div>
}

const mdS: Record<string, React.CSSProperties> = {
  root: { fontFamily: 'Georgia, "Times New Roman", serif', lineHeight: 1.7, color: '#1a1a1a' },
  h1: { fontSize: '1.25rem', fontWeight: 700, margin: '1rem 0 0.25rem', color: '#1a3c5e', borderBottom: '1px solid #ccc', paddingBottom: '0.2rem' },
  h2: { fontSize: '1.05rem', fontWeight: 700, margin: '1rem 0 0.2rem', color: '#1a3c5e' },
  h3: { fontSize: '0.95rem', fontWeight: 700, margin: '0.75rem 0 0.15rem', color: '#2c5282' },
  p: { margin: '0.2rem 0', fontSize: '0.9rem' },
  blockquote: { borderLeft: '4px solid #ffc107', margin: '0.5rem 0', padding: '0.4rem 0.75rem', background: '#fffde7', color: '#7d5800', fontSize: '0.875rem', borderRadius: '0 4px 4px 0' },
  hr: { border: 'none', borderTop: '1px solid #ccc', margin: '0.75rem 0' },
  ul: { margin: '0.25rem 0 0.25rem 1.25rem', padding: 0 },
  li: { fontSize: '0.9rem', marginBottom: '0.15rem' },
}

// ── Status light ─────────────────────────────────────────────────────────────
function StatusLight({ status }: { status: 'green' | 'yellow' | 'red' | string }) {
  const colors: Record<string, string> = { green: '#27ae60', yellow: '#f39c12', red: '#e74c3c' }
  const label: Record<string, string> = { green: 'Verifiziert', yellow: 'Unsicher', red: 'Nicht gefunden' }
  return (
    <span title={label[status] ?? status} style={{
      display: 'inline-block', width: 12, height: 12, borderRadius: '50%',
      background: colors[status] ?? '#aaa', marginRight: 6, flexShrink: 0,
    }} />
  )
}

// ── Section renderer ─────────────────────────────────────────────────────────
function IpsSection({ title, items, onHighlight }: {
  title: string
  items: any[]
  onHighlight: (docId: string, quote: string) => void
}) {
  if (!items?.length) return null
  return (
    <section style={s.section}>
      <h3 style={s.sectionTitle}>{title}</h3>
      {items.map((item: any, i: number) => {
        const light = item.quote_verified === false ? 'red' : item.code_validated === false ? 'yellow' : 'green'
        const text = item.text ?? item.substance ?? item.active_ingredient ?? item.vaccine ?? '–'
        return (
          <div key={i} style={s.item}>
            <StatusLight status={light} />
            <span style={{ flex: 1 }}>{text}{item.dose ? ` · ${item.dose}` : ''}{item.status ? ` [${item.status}]` : ''}</span>
            {item.quote && item.source_ids?.[0] && (
              <button style={s.quoteBtn} onClick={() => onHighlight(item.source_ids[0], item.quote)}>
                Quelle
              </button>
            )}
          </div>
        )
      })}
    </section>
  )
}

export default function ReviewScreen() {
  const { id } = useParams<{ id: string }>()
  const nav = useNavigate()
  const [draft, setDraft] = useState<any>(null)
  const [docs, setDocs] = useState<any[]>([])
  const [activeDocId, setActiveDocId] = useState<string | null>(null)
  const [activeDocText, setActiveDocText] = useState('')
  const [highlightQuote, setHighlightQuote] = useState('')
  const [summaryText, setSummaryText] = useState('')
  const [error, setError] = useState('')
  const [approving, setApproving] = useState(false)
  const [confirmed, setConfirmed] = useState(false)
  const [approveError, setApproveError] = useState<any>(null)
  const [showExcluded, setShowExcluded] = useState(false)
  const [editMode, setEditMode] = useState(false)

  useEffect(() => {
    if (!id) return
    getDraft(id).then(d => {
      setDraft(d)
      const ext = d?.composition?.extension ?? []
      const summaryExt = ext.find((e: any) => e.url?.includes('summary-text'))
      setSummaryText(summaryExt?.valueString ?? '')
    }).catch(e => setError(String(e)))
    listDocuments(id).then(d => setDocs(d.documents ?? [])).catch(() => {})
  }, [id])

  const handleHighlight = async (docId: string, quote: string) => {
    setHighlightQuote(quote)
    if (docId !== activeDocId) {
      setActiveDocId(docId)
      try {
        const doc = await getDocument(id!, docId)
        setActiveDocText(doc.text ?? '')
      } catch { setActiveDocText('Dokument konnte nicht geladen werden.') }
    }
  }

  const handleSave = async () => {
    if (!id) return
    try { await patchDraft(id, { summary_text: summaryText }) } catch (e) { setError(String(e)) }
  }

  const handleApprove = async () => {
    if (!id || !confirmed) return
    setApproving(true)
    setApproveError(null)
    try {
      await approveDraft(id)
      nav(`/patients/${id}/history`)
    } catch (e: any) {
      setApproveError(e?.detail ?? String(e))
    } finally { setApproving(false) }
  }

  const inter = draft?.intermediate ?? draft?.result?.intermediate
  const included = inter?.included ?? {}
  const excluded = inter?.excluded ?? []

  const hasRedItems = (() => {
    if (!draft?.bundle) return false
    const entries: any[] = draft.bundle?.entry ?? draft?.result?.bundle?.entry ?? []
    return entries.some((e: any) =>
      e.resource?.extension?.some((x: any) => x.url?.includes('status-light') && x.valueString === 'red')
    )
  })()

  const highlightedText = highlightQuote
    ? activeDocText.replace(
        new RegExp(highlightQuote.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi'),
        match => `<mark style="background:#fff176">${match}</mark>`
      )
    : activeDocText

  return (
    <div style={s.root}>
      {/* Draft notice */}
      <div style={s.notice}>
        ⚠️ <strong>KI-generierter Entwurf, ärztliche Prüfung erforderlich</strong>
      </div>
      {error && <div style={s.error}>{error}</div>}

      <div style={s.twoPan}>
        {/* Left: source documents */}
        <div style={s.left}>
          <h2 style={s.panTitle}>Quelldokumente</h2>
          <ul style={s.docList}>
            {docs.map(d => (
              <li key={d.id} style={{ ...s.docItem, fontWeight: d.id === activeDocId ? 700 : 400 }}
                  onClick={() => handleHighlight(d.id, highlightQuote)}>
                <span style={s.docType}>{d.type}</span> {d.description}
              </li>
            ))}
          </ul>
          {activeDocId && (
            <div style={s.docText}
                 dangerouslySetInnerHTML={{ __html: highlightedText.replace(/\n/g, '<br/>') }} />
          )}
        </div>

        {/* Right: IPS sections */}
        <div style={s.right}>
          <h2 style={s.panTitle}>Zusammenfassung & IPS</h2>
          <IpsSection title="Aktive Probleme" items={included.problems_active ?? []} onHighlight={handleHighlight} />
          <IpsSection title="Allergien & Unverträglichkeiten" items={included.allergies_intolerances ?? []} onHighlight={handleHighlight} />
          <IpsSection title="Medikation bei Entlassung" items={included.medication_at_discharge ?? []} onHighlight={handleHighlight} />
          <IpsSection title="Gestoppte Medikamente" items={included.medication_stopped ?? []} onHighlight={handleHighlight} />
          <IpsSection title="Frühere Erkrankungen" items={included.past_history ?? []} onHighlight={handleHighlight} />
          <IpsSection title="Eingriffe / Maßnahmen" items={included.procedures ?? []} onHighlight={handleHighlight} />
          <IpsSection title="Geräte & Implantate" items={included.medical_devices ?? []} onHighlight={handleHighlight} />
          <IpsSection title="Wichtige Befunde" items={included.key_results ?? []} onHighlight={handleHighlight} />

          {/* Excluded items (collapsible) */}
          {excluded.length > 0 && (
            <section style={s.section}>
              <button style={s.toggleBtn} onClick={() => setShowExcluded(x => !x)}>
                {showExcluded ? '▼' : '▶'} Ausgeschlossene Einträge ({excluded.length})
              </button>
              {showExcluded && excluded.map((item: any, i: number) => (
                <div key={i} style={{ ...s.item, color: '#777', fontStyle: 'italic' }}>
                  ✗ {item.text} <span style={s.reason}>[{item.reason}]</span>
                </div>
              ))}
            </section>
          )}

          {/* Summary: rendered view with edit toggle */}
          <section style={s.section}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
              <h3 style={{ ...s.sectionTitle, margin: 0 }}>Entlassungsbrief-Entwurf</h3>
              <button style={s.toggleModeBtn} onClick={() => setEditMode(m => !m)}>
                {editMode ? '👁 Vorschau' : '✏️ Bearbeiten'}
              </button>
            </div>

            {editMode ? (
              <>
                <textarea
                  style={s.textarea}
                  value={summaryText}
                  onChange={e => setSummaryText(e.target.value)}
                  rows={18}
                />
                <button style={s.saveBtn} onClick={handleSave}>Entwurf speichern</button>
              </>
            ) : (
              <div style={s.summaryView}>
                {summaryText
                  ? <MarkdownView text={summaryText} />
                  : <span style={{ color: '#999', fontSize: '0.875rem' }}>Kein Entlassungsbrief verfügbar.</span>
                }
              </div>
            )}
          </section>

          {/* Approval */}
          <section style={{ ...s.section, borderTop: '2px solid #1a3c5e', marginTop: '1.5rem' }}>
            <h3 style={s.sectionTitle}>Freigabe</h3>
            {hasRedItems && (
              <div style={s.error}>Es gibt noch rot markierte Einträge. Bitte prüfen Sie diese vor der Freigabe.</div>
            )}
            {approveError && (
              <div style={s.error}>
                {typeof approveError === 'string' ? approveError : JSON.stringify(approveError, null, 2)}
              </div>
            )}
            <label style={s.confirmLabel}>
              <input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />
              {' '}Ich habe den Inhalt geprüft und übernehme ihn.
            </label>
            <br />
            <button
              style={{ ...s.approveBtn, opacity: (!confirmed || hasRedItems || approving) ? 0.5 : 1 }}
              disabled={!confirmed || hasRedItems || approving}
              onClick={handleApprove}
            >
              {approving ? 'Wird freigegeben …' : 'Freigeben'}
            </button>
          </section>
        </div>
      </div>
    </div>
  )
}

const s: Record<string, React.CSSProperties> = {
  root: { fontFamily: 'sans-serif' },
  notice: { background: '#fff3cd', border: '1px solid #ffc107', padding: '0.6rem 1rem', borderRadius: 4, marginBottom: '1rem', color: '#856404' },
  error: { color: '#c0392b', background: '#fdecea', padding: '0.5rem', borderRadius: 4, marginBottom: '0.5rem' },
  twoPan: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' },
  panTitle: { color: '#1a3c5e', borderBottom: '2px solid #1a3c5e', paddingBottom: '0.3rem' },
  left: {},
  right: {},
  docList: { listStyle: 'none', padding: 0, margin: '0 0 1rem 0', maxHeight: 200, overflowY: 'auto', border: '1px solid #dde', borderRadius: 4 },
  docItem: { padding: '0.4rem 0.6rem', cursor: 'pointer', borderBottom: '1px solid #eee', fontSize: '0.85rem' },
  docType: { fontSize: '0.7rem', background: '#e8f0fe', color: '#1a3c5e', padding: '1px 4px', borderRadius: 3, marginRight: 4 },
  docText: { maxHeight: 400, overflowY: 'auto', background: '#f9f9f9', border: '1px solid #ddd', borderRadius: 4, padding: '0.75rem', fontSize: '0.85rem', whiteSpace: 'pre-wrap', lineHeight: 1.6 },
  section: { marginBottom: '1rem' },
  sectionTitle: { color: '#1a3c5e', fontSize: '0.95rem', margin: '0.5rem 0 0.3rem' },
  item: { display: 'flex', alignItems: 'center', padding: '0.25rem 0', fontSize: '0.875rem', gap: 4 },
  quoteBtn: { background: 'none', border: '1px solid #ccc', color: '#555', padding: '1px 6px', borderRadius: 3, cursor: 'pointer', fontSize: '0.75rem' },
  toggleBtn: { background: 'none', border: 'none', cursor: 'pointer', color: '#1a3c5e', fontWeight: 600, fontSize: '0.9rem', padding: 0 },
  reason: { fontSize: '0.75rem', color: '#999', marginLeft: 4 },
  textarea: { width: '100%', border: '1px solid #ccc', borderRadius: 4, padding: '0.5rem', fontFamily: 'monospace', fontSize: '0.85rem', boxSizing: 'border-box' as const },
  saveBtn: { background: '#1a3c5e', color: '#fff', border: 'none', padding: '0.4rem 0.8rem', borderRadius: 4, cursor: 'pointer', marginTop: 6 },
  toggleModeBtn: { background: '#f0f4f8', color: '#1a3c5e', border: '1px solid #c0cfe0', borderRadius: 4, padding: '0.25rem 0.65rem', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 600 },
  summaryView: { background: '#fff', border: '1px solid #dde', borderRadius: 4, padding: '1rem 1.25rem', maxHeight: 520, overflowY: 'auto' as const },
  confirmLabel: { fontSize: '0.9rem', cursor: 'pointer' },
  approveBtn: { background: '#27ae60', color: '#fff', border: 'none', padding: '0.5rem 1.2rem', borderRadius: 4, cursor: 'pointer', marginTop: '0.5rem', fontSize: '0.95rem' },
}
