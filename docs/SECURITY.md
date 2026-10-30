# Sicherheit – IPS Hackathon Tool

## Implementierte Sicherheitsmaßnahmen (Hackathon)

### Authentifizierung & Autorisierung
- **OpenID Connect (OIDC)** via Keycloak: alle Backend-Endpoints erfordern ein gültiges Bearer-Token.
- **Practitioner-ID ausschließlich aus Token:** Der Arzt-Identifier wird nur aus dem validierten OIDC-Token (`fhir_practitioner_id` claim) entnommen – nie aus dem Request-Body oder Query-Parametern.
- **Zuweisung geprüft:** Jeder Endpoint prüft per `CareTeam`-Ressource, ob der angemeldete Arzt dem Patienten zugewiesen ist. Nicht zugewiesene Patienten sind nicht sichtbar und nicht zugreifbar (403).
- **Rollenprüfung:** Nur Nutzer mit der Realm-Rolle `clinician` dürfen auf klinische Daten zugreifen.

### Netzwerk
- **HAPI FHIR Server**: nur auf internem Docker-Netz erreichbar, kein Host-Port-Binding.
- **PostgreSQL**: nur auf internem Docker-Netz.
- **CORS**: ausschließlich die konfigurierte Frontend-Origin erlaubt (`FRONTEND_ORIGIN` env var).
- **Security Headers**: `X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`, `Cache-Control: no-store` auf jedem Response.

### Datenschutz
- Keine Patientendaten in Logs, Fehlermeldungen oder Browser-Storage.
- API-Keys ausschließlich via Umgebungsvariablen; `.env` in `.gitignore`.
- Pseudonymisierung vor jedem LLM-Aufruf (Details in `DATA_PROTECTION.md`).

### Freigabe-Sicherheit
- Freigabe (`/approve`) blockiert wenn: (a) rote Einträge vorhanden, (b) FHIR-Validierung Fehler hat, (c) Arzt Bestätigung-Checkbox nicht angehakt.
- Composition bleibt `preliminary` bis zur expliziten Freigabe.
- KI ist nie als Author eingetragen – nur als `assembler` Device in Provenance.

### Auditierung
- Jeder Lese- und Schreibzugriff auf Patientendaten erzeugt einen `AuditEvent` im FHIR-Server.
- AuditEvents enthalten: Wer, Wann, Welche Ressource, Welche Aktion – keine klinischen Inhalte.

## Was für Produktion zusätzlich benötigt wird

| Bereich | Maßnahme |
|---------|----------|
| **SSO** | Integration mit Krankenhaus-Identity-Provider (Active Directory, LDAP) statt lokaler Keycloak-Users |
| **MFA** | Verpflichtende Zwei-Faktor-Authentifizierung für alle klinischen Nutzer |
| **TLS** | TLS 1.3 auf allen Verbindungen; interne Service-zu-Service-Verbindungen mit mTLS |
| **Secrets Management** | HashiCorp Vault oder Cloud KMS statt Umgebungsvariablen für Schlüssel |
| **Netzwerksegmentierung** | Firewall-Regeln zwischen allen Netzwerkzonen; kein Internet-Zugang aus dem internen Netz |
| **Verschlüsselte Volumes** | LUKS / Cloud-Provider Disk Encryption für alle Datenbankvolumes |
| **Backup-Verschlüsselung** | Alle Backups AES-256-verschlüsselt, Wiederherstellung getestet |
| **Penetrationstest** | Jährlicher externer Pentest |
| **SIEM / Monitoring** | Zentralisiertes Log-Management, Anomalieerkennung, Alerting bei unautorisierten Zugriffen |
| **Incident Response** | Dokumentierter Prozess: Erkennung → Meldung (72h DSGVO) → Eindämmung → Analyse → Recovery |
| **Retention Policy** | Automatisches Löschen von Entwürfen nach konfigurierter Frist; Einhaltung gesetzlicher Aufbewahrungsfristen |
| **Rate Limiting** | API-Rate-Limiting pro Nutzer zum Schutz vor Abuse |
| **Dependency Scanning** | Automatisierte CVE-Prüfung aller Dependencies in CI/CD |
| **Container Hardening** | Non-root Container, read-only Filesysteme, minimale Images |
