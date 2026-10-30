# Traps – Patient P002 (Gerald Wimmer)

## Trap 1 – KM-Reaktion nur im Pflegebericht (Trap-Typ 1)
**Beschreibung:** Der Patient berichtet der Pflegeperson (D007) über eine frühere Reaktion auf jodhaltiges Kontrastmittel (Flush, Kurzatmigkeit). Diese Information erscheint **nicht** im Aufnahmebefund (D004), der Hausarzt-Zuweisung (D003) oder früheren Befunden – ausschließlich im Pflegebericht. Erst daraufhin wird sie vom Stationsarzt aufgegriffen (D008) und im weiteren Verlauf als unbestätigte pseudoallergische Reaktion dokumentiert.  
**Beteiligte Dokumente:** P002-D003, P002-D004, P002-D007, P002-D008, P002-D015  
**Korrekte IPS-Behandlung:** KM-Reaktion in `allergies_intolerances` mit `verification: unconfirmed` eintragen.

---

## Trap 2 – STEMI-Diagnose reklassifiziert zu NSTEMI (Trap-Typ 7)
**Beschreibung:** Die Hausärztin stellt im EKG ST-Hebungen fest und überweist mit der Diagnose „V.a. STEMI Hinterwand" (D003). Der Aufnahmebefund schreibt diese Verdachtsdiagnose zunächst fort (D004). Der diensthabende OA bewertet das EKG neu und klassifiziert den Befund als **NSTEMI** (D006). Der Entlassungsbrief (D015) bestätigt: NSTEMI.  
**Beteiligte Dokumente:** P002-D003, P002-D004, P002-D006, P002-D015  
**Korrekte IPS-Behandlung:** Diagnose ist **NSTEMI** (I21.4). STEMI darf **nicht** in `problems_active` erscheinen. Der spätere, fachärztliche Befund ist maßgeblich.

---

## Trap 3 – Statin: gestartet, gewechselt (Trap-Typ 3)
**Beschreibung:** Simvastatin 40mg wird am 14.10. als erstes Statin gestartet (D006). Am nächsten Tag (D010) wird es auf Atorvastatin 80mg umgestellt (leitliniengerechte Hochdosistherapie nach ACS). Simvastatin wird explizit gestoppt.  
**Beteiligte Dokumente:** P002-D006, P002-D010, P002-D014  
**Korrekte IPS-Behandlung:** Atorvastatin 80mg in `medication_at_discharge`. Simvastatin in `medication_stopped_during_stay`. Simvastatin darf **nicht** in `medication_at_discharge` erscheinen.

---

## Trap 4 – Negation: kein STEMI, kein KM-Schaden, kein Herzstolpern-EKG (Trap-Typ 4)
**Beschreibung:** Mehrere Negationen könnten fehlinterpretiert werden:
- „kein Hinweis auf mechanische Komplikation" (D011) – nicht als positiver Befund übernehmen
- „keine Reaktion" auf KM während Intervention (D009) – schließt nicht aus, dass Intoleranz besteht
- „kein signifikanter Befund" RCX (D009) – RCX nicht als Interventionsziel dokumentieren
- Metformin-Pause ist **temporär**, kein Stopp: „Wiederaufnahme morgen geplant" (D010)  
**Beteiligte Dokumente:** P002-D009, P002-D010, P002-D011  
**Korrekte IPS-Behandlung:** Keine dieser Negationen als aktive Diagnose übernehmen.

---

## Trap 5 – Familienanamnese Vater-Herzinfarkt (Trap-Typ 5)
**Beschreibung:** In D001 und D002 wird erwähnt: „Vater verstorben an Herzinfarkt mit 61 Jahren." Dies ist eine Familienanamnese, keine eigene Erkrankung des Patienten.  
**Beteiligte Dokumente:** P002-D001, P002-D002  
**Korrekte IPS-Behandlung:** Gehört in `must_not_include` mit `reason: family history`. **Nicht** in `past_history` oder `problems_active`.

---

## Trap 6 – Unbestätigtes Herzstolpern (Trap-Typ 8)
**Beschreibung:** Der Patient berichtet am 16.10. (D013) über gelegentliches Herzstolpern in den Monaten vor dem Aufenthalt – nie untersucht, kein EKG. Kein Arzt greift diese Angabe auf, keine weitere Abklärung erfolgt im Aufenthalt.  
**Beteiligte Dokumente:** P002-D013  
**Korrekte IPS-Behandlung:** In `must_not_include` mit `reason: unconfirmed`. Nicht als Arrhythmie oder Vorerkrankung eintragen.

---

## Trap 7 – Implantat (Stent) nur im Katheter-Bericht (Trap-Typ 10)
**Beschreibung:** Die genauen Stent-Daten (Hersteller Biotronik, Modell Orsiro Mission, 3,0×18mm, Sirolimus) stehen **nur im Herzkatheter-Bericht** (D009) und werden im Entlassungsbrief (D015) kurz erwähnt. Kein anderer Verlaufseintrag nennt die technischen Implantatdaten.  
**Beteiligte Dokumente:** P002-D009, P002-D015  
**Korrekte IPS-Behandlung:** DES mit Modellangabe in `medical_devices_implants` eintragen.

---

## Trap 8 – Abkürzung/Schreibweise „Tikagrelor" vs. „Ticagrelor" (Trap-Typ 9)
**Beschreibung:** In der Medikationsanordnung (D014) wird das Medikament als **„Tikagrelor"** geschrieben (deutsche Phonetik, in österreichischen klinischen Texten gelegentlich so anzutreffen). In allen anderen Dokumenten (D009, D015) steht die korrekte Schreibweise **„Ticagrelor"**.  
**Beteiligte Dokumente:** P002-D009, P002-D014, P002-D015  
**Korrekte IPS-Behandlung:** Beides meint dasselbe Präparat (ATC B01AC24). In der IPS korrekte Schreibweise „Ticagrelor" verwenden.
