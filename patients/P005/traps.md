# Traps – Patient P005 (Monika Steinbauer)

## Trap 1 – NSAID-Unverträglichkeit nur im Pflegebericht (telefonisch) (Trap-Typ 1)
**Beschreibung:** Im Telefonkontakt nach Zyklus 1 berichtet die Patientin der Pflegeperson (D006), sie vertrage keine Ibuprofen – einmal sei sie „ganz aufgeschwollen". Diese Information erscheint **ausschließlich im Pflegebericht** (Telefonkontakt 28.02.). Weder im Aufnahmebefund (D002) noch in der Onkologie-Erstvorstellung noch im OP-Protokoll (D003) ist eine Allergie vermerkt. Erst am 04.03. (D007) wird die Angabe aufgegriffen und als Unverträglichkeit eingetragen.  
**Beteiligte Dokumente:** P005-D002, P005-D003, P005-D006, P005-D007  
**Korrekte IPS-Behandlung:** Ibuprofen/NSAID-Intoleranz in `allergies_intolerances` mit `verification: unconfirmed`. Nicht ignorieren, aber nicht als bestätigte Allergie werten.

---

## Trap 2 – V.a. Lebermetastase, durch MRT ausgeschlossen (Trap-Typ 2)
**Beschreibung:** Die Sonographie vom 05.04. (D009) beschreibt einen echoarmen Leberherd und stellt die Differentialdiagnose „Metastase vs. Hämangiom". Das MRT vom 15.04. (D010) klassifiziert den Befund **eindeutig als kavernöses Hämangiom**. Im Verlaufseintrag D011 wird das Ergebnis als „kein Metastasenverdacht mehr" kommuniziert.  
**Beteiligte Dokumente:** P005-D009, P005-D010, P005-D011  
**Korrekte IPS-Behandlung:** Lebermetastase darf **nicht** in `problems_active` erscheinen. Sie gehört in `must_not_include` mit `reason: ruled out`.

---

## Trap 3 – Ondansetron: Regime geändert; G-CSF: erst abgelehnt, dann gestartet (Trap-Typ 3 / Typ 7)
**Beschreibung (a) Ondansetron:** Nach Zyklus 1 reichte Ondansetron als alleinige Antiemese nicht aus. Ab Zyklus 2 wurde auf Triple-Antiemese (Aprepitant + Ondansetron + Dexamethason) umgestellt. Das Regime hat sich geändert: Ondansetron ist zwar noch Teil der Therapie, aber in reduzierter Rolle (nur noch Reserve-Antiemese p.o.).  
**Beschreibung (b) G-CSF-Widerspruch:** Im Verlaufseintrag zu Zyklus 1 (D005) und Zyklus 2 (D008) steht explizit: **„G-CSF nicht angeordnet"**. Nach der schweren Neutropenie post Zyklus 3 wird G-CSF (Filgrastim) am 19.04. therapeutisch gestartet (D011). Ein späterer Verlaufseintrag (D009) hatte noch festgehalten: „G-CSF nicht angeordnet (Leukos >3,5 G/l)". Diese Entscheidung wird durch die Neutropenie-Episode revidiert.  
**Beteiligte Dokumente:** P005-D005, P005-D007, P005-D008, P005-D009, P005-D011, P005-D015  
**Korrekte IPS-Behandlung:** Filgrastim ab Zyklus 4 primärprophylaktisch in `medication_at_discharge`. Piperacillin/Tazobactam (stationäre Episode) in `medication_stopped_during_stay`. Die frühere Entscheidung „G-CSF nicht notwendig" ist überholt – späteres Dokument (D011, D015) ist maßgeblich.

---

## Trap 4 – Negationen (Trap-Typ 4)
**Beschreibung:** Klinisch wichtige Negationen:
- „Kein Anhalt für Lebermetastase" (D010) – nach initialem Verdacht
- „keine akute Reaktion" bei Chemo-Infusionen (D005, D008) – nicht als Allergiebeweis
- „Blutkulturen steril" (D014) – kein positives Blutkultur-Ergebnis
- „kein Pneumothorax" post Port-Anlage (D004) – keine Komplikation  
**Beteiligte Dokumente:** P005-D004, P005-D005, P005-D008, P005-D010, P005-D014  
**Korrekte IPS-Behandlung:** Keine der negierten Befunde als Diagnose übernehmen.

---

## Trap 5 – Familienanamnese Mutter mit Mammakarzinom (Trap-Typ 5)
**Beschreibung:** In D001 (Entlassungsbrief 2015) und D002 (Onkologie-Erstvorstellung) wird erwähnt: „Mutter verstorben an Mammakarzinom mit 64 Jahren." Dies ist die Erkrankung der Mutter, nicht der Patientin.  
**Beteiligte Dokumente:** P005-D001, P005-D002  
**Korrekte IPS-Behandlung:** In `must_not_include` mit `reason: family history`. Nicht in `problems_active`.

---

## Trap 6 – Benigne Struma als gelöste Vorerkrankung (Trap-Typ 6)
**Beschreibung:** Die benigne multinodöse Struma (E04.2) war die Indikation für die Thyreoidektomie 2015 und ist nach der vollständigen Entfernung der Schilddrüse als **gelöste Vorerkrankung** zu werten. Die Konsequenz (Levothyroxin-Dauertherapie) ist aktiv, nicht aber die Struma selbst.  
**Beteiligte Dokumente:** P005-D001  
**Korrekte IPS-Behandlung:** Struma in `past_history` mit `resolved: 2015`. Der Zustand nach Thyreoidektomie mit Levothyroxin-Substitutionsbedarf ist das aktive Problem (E89.0).

---

## Trap 7 – Unbestätigte Fingerneuropathie (Trap-Typ 8)
**Beschreibung:** Die Patientin berichtet in D009 (Zyklus 3 Tag 1) und wiederholt in D011 und D016 über Kribbeln in den Fingerkuppen. Es wird explizit festgehalten: **kein objektivierbarer neurologischer Befund**, kein formeller Neurologie-Befund erhoben. Epirubicin gilt nicht als Ursache (Paclitaxel kommt später). Die Angabe bleibt klinisch nicht bestätigt.  
**Beteiligte Dokumente:** P005-D009, P005-D011, P005-D016  
**Korrekte IPS-Behandlung:** Polyneuropathie in `must_not_include` mit `reason: unconfirmed`. Nicht in `problems_active`.

---

## Trap 8 – „Epiru" als Abkürzung für Epirubicin (Trap-Typ 9)
**Beschreibung:** Im Verlaufseintrag zu Zyklus 2 (D008) wird Epirubicin als **„Epiru"** abgekürzt: „Epiru 90mg/m² (= 155mg) i.v.". In allen anderen Dokumenten (D005, D009, D016) wird der Wirkstoff korrekt als „Epirubicin" ausgeschrieben.  
**Beteiligte Dokumente:** P005-D005, P005-D008, P005-D009  
**Korrekte IPS-Behandlung:** „Epiru" = Epirubicin (ATC L01DB03) normalisieren.

---

## Trap 9 – Port-Katheter nur in OP-Bericht und Röntgen (Trap-Typ 10)
**Beschreibung:** Die vollständigen technischen Daten des Port-Katheters (Modell: Bard PowerPort, 8F, Titan-Reservoir, V. subclavia rechts, Spitze V. cava superior) sind ausschließlich im **OP-Bericht** (D003) und im **Röntgenbefund** post-OP (D004) dokumentiert. Alle späteren Verlaufseinträge erwähnen den Port nur kursorisch als „Port" oder „Port-Eintrittsstelle".  
**Beteiligte Dokumente:** P005-D003, P005-D004  
**Korrekte IPS-Behandlung:** Port-Katheter mit vollständigen Angaben in `medical_devices_implants`, auch wenn Details nur in D003 und D004 stehen.
