# Traps – Patient P006 (Florian Kastner)

## Trap 1 – Latex-Allergie nur im Pflegebericht (Notfallausweis), Aufnahme sagt „keine Allergien" (Trap-Typ 1)
**Beschreibung:** Der Hausarzt (D004) zitiert die Patientenangabe „keine bekannten Allergien" und der Aufnahmebefund (D005) vermerkt ebenfalls „Allergien: keine bekannt". Der Patient trägt jedoch einen **Notfallausweis bei sich**, den die Pflegeperson bei der Aufnahme entdeckt: bestätigte Latex-Allergie mit anaphylaktischer Reaktion 2020. Dieser Hinweis erscheint erstmals im Pflegebericht (D006). Der OA greift die Information am nächsten Tag auf (D009) und korrigiert die Akte. Der Entlassungsbrief (D013) hält fest, dass die Allergie im Aufnahmebefund fehlte.  
**Beteiligte Dokumente:** P006-D004, P006-D005, P006-D006, P006-D008, P006-D009, P006-D013  
**Korrekte IPS-Behandlung:** Latex-Allergie als **bestätigt** eintragen (`verification: confirmed`, `criticality: high`), gestützt auf Vorbefund D002 (Allergiebefund 2020).

---

## Trap 2 – V.a. kortikale Kontusion im CCT, durch MRT ausgeschlossen (Trap-Typ 2)
**Beschreibung:** Das CCT (D007) beschreibt eine „kleine hypodense Zone links temporal" und stellt die Differentialdiagnose „postiktuales Ödem vs. kortikale Kontusion". Das MRT (D011) klärt dies eindeutig: **kein Nachweis einer kortikalen Kontusion**, ausschließlich postiktuales Phänomen. Der Verlaufseintrag D012 bestätigt: „Kein Kontusionsnachweis."  
**Beteiligte Dokumente:** P006-D007, P006-D009, P006-D011, P006-D012, P006-D013  
**Korrekte IPS-Behandlung:** Kortikale Kontusion darf **nicht** in `problems_active` erscheinen. In `must_not_include` mit `reason: ruled out`.

---

## Trap 3 – Widerspruch letzter Anfall: „6 Monate" (Zuweisung) vs. „9 Monate" (Neurologie-Ambulanz) (Trap-Typ 7)
**Beschreibung:** Der Einweisungsbrief (D004) notiert die Patientenangabe „letzter Anfall vor ca. 6 Monaten". Der detaillierte Neurologie-Ambulanzbefund vom 15.01.2024 (D003) dokumentiert exakt: letzter Anfall **05.11.2023**, d.h. ca. 9 Monate vor dem aktuellen Aufenthalt (08/2024). Der OA (D009) stellt explizit klar: „Ambulanzbefund vom 15.01.2024 ist die maßgebliche Quelle." Der Entlassungsbrief (D013) wiederholt die Korrektur.  
**Beteiligte Dokumente:** P006-D003, P006-D004, P006-D009, P006-D013  
**Korrekte IPS-Behandlung:** Letzter Anfall = **05.11.2023** (lt. D003). Die Angabe „6 Monate" aus D004 in `must_not_include` mit `reason: contradicted by authoritative document`.

---

## Trap 4 – Negationen (Trap-Typ 4)
**Beschreibung:** Wichtige Negationen:
- „kein Anhalt für intrakranielle Blutung" (D007) – CCT-Befund
- „kein Nachweis kortikaler Kontusion" (D011) – MRT-Befund
- „kein Anhalt für Tumor oder Hippokampussklerose" (D011) – MRT
- „kein weiterer Anfall stationär" (D013)
- „Valproat NICHT gestartet", „Carbamazepin … jetzt kein Start" (D012)  
**Beteiligte Dokumente:** P006-D007, P006-D011, P006-D012, P006-D013  
**Korrekte IPS-Behandlung:** Keine dieser negierten Befunde als Diagnose oder Medikation übernehmen.

---

## Trap 5 – Familienanamnese Vater mit Epilepsie (Trap-Typ 5)
**Beschreibung:** In D001 (Erstdiagnose 2017) und D003 (Ambulanzbefund 2024) wird erwähnt: „Vater mit bekannter Epilepsie". Dies ist die Erkrankung des Vaters, nicht des Patienten selbst.  
**Beteiligte Dokumente:** P006-D001, P006-D003  
**Korrekte IPS-Behandlung:** In `must_not_include` mit `reason: family history`. Nicht in `problems_active` des Patienten.

---

## Trap 6 – Fieberkrämpfe als gelöste Vorerkrankung (Trap-Typ 6)
**Beschreibung:** Im Entlassungsbrief der Erstdiagnose (D001) werden Fieberkrämpfe im Säuglingsalter (18. und 24. Lebensmonat, einfach, benigne) erwähnt. Diese sind vollständig überwunden und haben keine Relation zur aktuellen fokalen Epilepsie (kein Kausalzusammenhang dokumentiert).  
**Beteiligte Dokumente:** P006-D001  
**Korrekte IPS-Behandlung:** Fieberkrämpfe in `past_history` mit `resolved: 2002`. **Nicht** in `problems_active`.

---

## Trap 7 – Unbestätigter fokaler Anfall (Kribbeln li. Arm) (Trap-Typ 8)
**Beschreibung:** Im Pflegebericht (D006) berichtet der Patient über mögliches Kribbeln im linken Arm einige Wochen zuvor – „möglicherweise ein kleiner fokaler Anfall", aber nicht gemeldet und „nicht verifizierbar". Diese Angabe wird weder durch ärztliche Dokumentation noch durch EEG-Befunde gestützt.  
**Beteiligte Dokumente:** P006-D006  
**Korrekte IPS-Behandlung:** In `must_not_include` mit `reason: unconfirmed`. Nicht als gesicherter Anfall oder separate Diagnose eintragen.

---

## Trap 8 – „Leve" als Abkürzung für Levetiracetam (Trap-Typ 9)
**Beschreibung:** Im Verlaufseintrag D012 wird Levetiracetam konsequent als **„Leve"** abgekürzt: „Leve-Erhöhung sollte zunächst versucht werden." Diese Abkürzung ist in österreichischen Neurologieabteilungen üblich, könnte aber von einem NLP-System nicht automatisch aufgelöst werden.  
**Beteiligte Dokumente:** P006-D012  
**Korrekte IPS-Behandlung:** „Leve" = Levetiracetam (ATC N03AX14) normalisieren.

---

## Trap 9 – Valproat und Carbamazepin diskutiert, aber nicht gestartet (Trap-Typ 3 / Typ 4)
**Beschreibung:** Im Verlaufseintrag D012 werden zwei weitere Antiepileptika erwogen: Valproat (als Kombinationspartner) und Carbamazepin (als Monotherapie-Alternative). Beide werden explizit **nicht gestartet** – Valproat wegen Interaktionspotential, Carbamazepin als Möglichkeit für späteres Versagen der erhöhten Levetiracetam-Dosis. Ein KI-System könnte diese Medikamente fälschlicherweise als verordnet extrahieren.  
**Beteiligte Dokumente:** P006-D012  
**Korrekte IPS-Behandlung:** Valproat und Carbamazepin in `must_not_include` mit `reason: ruled out (discussed but not started)`. Sie dürfen nicht in `medication_at_discharge` erscheinen.
