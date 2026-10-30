# Datenschutz – IPS Hackathon Tool

## Wann darf KI Patientendaten verarbeiten?

Gesundheitsdaten sind nach **DSGVO Art. 9** besondere Kategorien personenbezogener Daten und genießen erhöhten Schutz. Die Verarbeitung ist grundsätzlich verboten – außer bei Vorliegen einer ausdrücklichen Rechtsgrundlage (z.B. Art. 9 Abs. 2 lit. h: Gesundheitsversorgung, Behandlung).

Dieses Tool unterscheidet drei Modi:

| Modus | Datenart | Bedingung |
|-------|----------|-----------|
| `synthetic` | Vollständig synthetische Testdaten | Immer erlaubt |
| `pseudonymized` | Echte Daten, pseudonymisiert | Erfordert vollständige DSGVO-Prüfliste |
| `real` | Echte Klardaten | Zusätzliche explizite Genehmigung erforderlich |

## Implementierte Sicherheitsmaßnahmen (dieses Tool)

1. **Datenschutz-Gate (Step 1):** Jeder Lauf prüft den Modus und die DSGVO-Checkliste bevor irgendeine Verarbeitung stattfindet. Bei fehlenden Voraussetzungen verweigert das Tool die Ausführung mit Fehlermeldung.

2. **Pseudonymisierung vor LLM-Aufruf (Step 2):** Namen, Geburtsdaten, Versicherungsnummern und Einrichtungsnamen werden durch Tokens ersetzt (`[PAT-NAME]`, `[FAC-001]` etc.) bevor Text an das LLM gesendet wird. Die Zuordnungstabelle verbleibt **ausschließlich im Arbeitsspeicher** und wird nie auf Disk geschrieben.

3. **Datensparsamkeit:** Das LLM erhält ausschließlich die Dokumententexte. Die Datei `patient.json` und `ground_truth_ips.json` werden nie an das LLM übermittelt.

4. **Keine sensiblen Daten in Logs:** Das Audit-Log enthält Zeitstempel, Pseudonym-Token, Modellname, Modus, Erfolgsstatus – aber keine klinischen Inhalte und keine Klarnamen.

5. **API-Keys ausschließlich via Umgebungsvariablen:** Keine Secrets im Code oder Repository. `.env`-Dateien sind in `.gitignore` ausgeschlossen.

6. **Verschlüsselung at rest (non-synthetic):** Ausgaben im Modus `pseudonymized` und `real` werden mit AES-256-GCM verschlüsselt geschrieben (`crypto.py`). Der Schlüssel wird via Umgebungsvariable übergeben.

7. **Human in the Loop:** Alle Ausgaben sind Entwürfe (`status: preliminary`). Ein klinischer Experte muss prüfen und freigeben. Die Freigabe erfordert explizite Bestätigung.

8. **Transparenz:** Der Entlassungsbrief-Entwurf und die FHIR Composition enthalten explizit den Hinweis auf KI-Generierung und Prüfpflicht.

9. **Keine KI als Autor:** In FHIR Provenance und Composition ist die KI als `assembler` (Device), nicht als `author` eingetragen. Der Arzt wird erst bei der Freigabe als Author gesetzt.

## Was ein Krankenhaus zusätzlich benötigt (Produktion)

| Maßnahme | Beschreibung |
|----------|-------------|
| **Zugangssteuerung** | Role-based Access Control (RBAC) per Abteilung und Patient; Multi-Faktor-Authentifizierung für klinisches Personal |
| **Netzwerksegmentierung** | FHIR-Server und LLM-Endpoint in isolierten Netzwerkzonen; keine direkte Internet-Konnektivität |
| **Datenschutz-Folgenabschätzung** | DPIA nach Art. 35 DSGVO mit Risikobewertung und Maßnahmenplan |
| **Auftragsverarbeitungsvertrag** | AVV nach Art. 28 DSGVO mit LLM-Anbieter, inkl. Standort EU, keine Trainingsnutzung, Löschfristen |
| **Aufbewahrungsfristen** | Technische Umsetzung der gesetzlichen Aufbewahrungsfristen (AT: 10 Jahre Krankenakten) |
| **Penetrationstest** | Jährlicher Pentest der gesamten Infrastruktur |
| **Monitoring & Alerting** | Anomalieerkennung, Zugriffsprotokollierung, Sicherheitsvorfallsmanagement |
| **Incident Response** | Dokumentierter Prozess zur Meldung von Datenschutzverletzungen (72h-Frist nach Art. 33 DSGVO) |
| **Backup & Recovery** | Verschlüsselte Backups, getestete Wiederherstellung |
| **Zertifizierung** | ISO 27001 / IEC 27799 (Gesundheitswesen) empfohlen |
| **Verschlüsselung in transit** | TLS 1.3 für alle Verbindungen; kein Klartext intern |

## Medizinproduktrecht & EU AI Act

Wenn dieses Tool **klinische Entscheidungen beeinflusst** (z.B. durch Vorschlag einer Diagnose, die ein Arzt übernimmt), kann es als:

- **Medizinprodukt (MDR 2017/745)** der Klasse IIa oder höher einzustufen sein → CE-Kennzeichnung, QMS, klinische Bewertung erforderlich.
- **Hochrisiko-KI-System (EU AI Act Art. 6, Anhang III)** einzustufen sein → Konformitätsbewertung, Registrierung, Transparenzpflichten.

**Dieser Prototyp ist explizit als Hackathon-Demonstrator ohne Produktionszulassung erstellt. Er darf nicht für echte klinische Entscheidungen eingesetzt werden.**
