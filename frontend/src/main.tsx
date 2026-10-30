import ReactDOM from 'react-dom/client'
import App from './App'

// StrictMode is intentionally omitted: keycloak-js throws if .init() is called
// twice, which StrictMode triggers in development by design (double-invoking effects).
ReactDOM.createRoot(document.getElementById('root')!).render(<App />)
