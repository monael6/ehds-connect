import React, { useEffect, useRef, useState } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import keycloak, { DEV_MOCK_USERNAME, DEV_SKIP_AUTH } from './auth/keycloak'
import PatientList from './pages/PatientList'
import PatientView from './pages/PatientView'
import ReviewScreen from './pages/ReviewScreen'
import History from './pages/History'

export default function App() {
  const [authenticated, setAuthenticated] = useState<boolean | null>(
    DEV_SKIP_AUTH ? true : null   // skip auth check entirely in dev bypass mode
  )
  const initStarted = useRef(false)

  useEffect(() => {
    if (DEV_SKIP_AUTH) return   // Keycloak not running locally — skip
    // Guard: keycloak-js throws if .init() is called more than once.
    if (initStarted.current) return
    initStarted.current = true
    keycloak
      .init({ onLoad: 'login-required', pkceMethod: 'S256' })
      .then((auth) => setAuthenticated(auth))
      .catch(() => setAuthenticated(false))
  }, [])

  if (authenticated === null) return <div style={styles.loading}>Anmeldung wird geprüft …</div>
  if (!authenticated) return (
    <div style={styles.loading}>
      <div>
        <p>Anmeldung fehlgeschlagen.</p>
        <p style={{ fontSize: '0.85rem', color: '#666', marginTop: '0.5rem' }}>
          Keycloak erreichbar? Starte den Stack mit:<br />
          <code style={{ background: '#f0f0f0', padding: '0.2rem 0.4rem', borderRadius: 3 }}>
            docker compose -f infra/docker-compose.yml up -d
          </code><br /><br />
          Oder aktiviere den Dev-Bypass (kein Docker nötig):<br />
          <code style={{ background: '#f0f0f0', padding: '0.2rem 0.4rem', borderRadius: 3 }}>
            VITE_DEV_SKIP_AUTH=true in frontend/.env.local
          </code>
        </p>
      </div>
    </div>
  )

  const displayName = DEV_SKIP_AUTH
    ? DEV_MOCK_USERNAME
    : (keycloak.tokenParsed?.preferred_username ?? '')

  return (
    <BrowserRouter>
      <header style={styles.header}>
        <span style={styles.title}>IPS Klinisches Portal</span>
        {DEV_SKIP_AUTH && (
          <span style={styles.devBadge}>⚠️ Dev-Bypass – kein echtes Login</span>
        )}
        <span style={styles.user}>
          {displayName}
          {' '}
          {!DEV_SKIP_AUTH && (
            <button style={styles.logoutBtn} onClick={() => keycloak.logout()}>Abmelden</button>
          )}
        </span>
      </header>
      <main style={styles.main}>
        <Routes>
          <Route path="/" element={<Navigate to="/patients" replace />} />
          <Route path="/patients" element={<PatientList />} />
          <Route path="/patients/:id" element={<PatientView />} />
          <Route path="/patients/:id/review" element={<ReviewScreen />} />
          <Route path="/patients/:id/history" element={<History />} />
        </Routes>
      </main>
    </BrowserRouter>
  )
}

const styles: Record<string, React.CSSProperties> = {
  loading: { display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', fontFamily: 'sans-serif' },
  header: { background: '#1a3c5e', color: '#fff', padding: '0.75rem 1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  title: { fontWeight: 700, fontSize: '1.1rem', letterSpacing: '0.02em' },
  user: { fontSize: '0.9rem' },
  logoutBtn: { background: 'transparent', border: '1px solid #fff', color: '#fff', padding: '0.2rem 0.6rem', cursor: 'pointer', borderRadius: 3 },
  devBadge: { background: '#f39c12', color: '#000', fontSize: '0.75rem', fontWeight: 700, padding: '0.15rem 0.5rem', borderRadius: 3 },
  main: { maxWidth: 1200, margin: '0 auto', padding: '1.5rem' },
}
