/**
 * keycloak.ts – Keycloak OIDC client singleton.
 * Reads config from Vite env variables (set at build time or via nginx env injection).
 *
 * Dev bypass: set VITE_DEV_SKIP_AUTH=true in frontend/.env.local to skip
 * Keycloak entirely and use a mock token. Never set this in production.
 */
import Keycloak from 'keycloak-js'

export const DEV_SKIP_AUTH =
  import.meta.env.VITE_DEV_SKIP_AUTH === 'true' && import.meta.env.DEV

// Mock token payload for dev bypass — matches demo user dr.mueller
export const DEV_MOCK_TOKEN = 'dev-mock-token'
export const DEV_MOCK_USERNAME = 'dr.mueller (Dev-Modus)'

const keycloak = new Keycloak({
  url: import.meta.env.VITE_KEYCLOAK_URL ?? 'http://localhost:8180',
  realm: import.meta.env.VITE_KEYCLOAK_REALM ?? 'hackathon',
  clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID ?? 'ips-frontend',
})

export default keycloak
