# Traps – Patient P003 (Sabine Gruber)

## Trap 1 – Penicillin-Allergie nur im Pflegebericht, Aufnahme sagt „keine Allergien" (Trap-Typ 1)
**Beschreibung:** Der Bereitschaftsarzt (D003) und der Aufnahmebefund (D004) dokumentieren beide **„keine bekannten Allergien"**. In der Aufnahmenacht berichtet die Patientin der Pflegeperson explizit von ihrer Penicillin-Allergie (D005). Diese Information ist ausschließlich im Pflegebericht vermerkt und wird erst dann durch den OA aufgegriffen (D008) und für die Anästhesie- und Antibiotikaplanung berücksichtigt. Der Entlassungsbrief (D014) hält explizit fest, dass der Aufnahmebefund fälschlicherweise „keine Allergien" vermerkt hatte und dies korrigiert wurde.  
**Beteiligte Dokumente:** P003-D003, P003-D004, P003-D005, P003-D008, P003-D014  
**Korrekte IPS-Behandlung:** Penicillin-Allergie (Urtikaria) als **bestätigt** eintragen (`verification: confirmed`), gestützt auf Vorbefund D001 (Kinderkrankenhaus 2009). Nicht ignorieren.

---

## Trap 2 – V.a. Perforation aus dem Sono, intraoperativ ausgeschlossen (Trap-Typ 2)
**Beschreibung:** Der Sonographiebefund (D007) beschreibt freie Flüssigkeit periappendizeal und kann eine Perforation „nicht sicher ausschließen". Der OA notiert in D008 ebenfalls „V.a. beginnende Perforation". Der OP-Bericht (D010) stellt jedoch **intraoperativ eindeutig fest: keine Perforation** (phlegmonöse Appendizitis). Der Entlassungsbrief (D014) bestätigt „nicht perforiert".  
**Beteiligte Dokumente:** P003-D007, P003-D008, P003-D010, P003-D014  
**Korrekte IPS-Behandlung:** Diagnose ist **akute phlegmonöse Appendizitis, nicht perforiert**. „Perforierte Appendizitis" darf nicht in `problems_active` erscheinen. Sie gehört in `must_not_include` mit `reason: ruled out`.

---

## Trap 3 – Metamizol gestartet, nach OP auf Paracetamol gewechselt (Trap-Typ 3)
**Beschreibung:** Bei Aufnahme wird Metamizol 1g i.v. als Analgetikum angeordnet (D004) und in der Nacht verabreicht. Im OP-Bericht (D010) wird explizit angeordnet: **„Metamizol stopp → Paracetamol 1g i.v./p.o."** Paracetamol wird bei Entlassung mitgegeben, Metamizol nicht.  
**Beteiligte Dokumente:** P003-D004, P003-D008, P003-D010, P003-D014  
**Korrekte IPS-Behandlung:** Metamizol in `medication_stopped_during_stay`. Paracetamol (kurzfristig) in `medication_at_discharge`. Metamizol darf nicht in der Entlassungsmedikation stehen.

---

## Trap 4 – Negationen (Trap-Typ 4)
**Beschreibung:** Mehrere klinisch wichtige Negationen sind dokumentiert:
- „kein Hinweis auf Pankreatitis" (D006, Labor: Lipase normal) – Pankreatitis ist keine Diagnose
- „kein Hinweis auf Ovarialkarzinom oder Endometriose" (D012) – diese Diagnosen dürfen nicht aus diesem Satz abgeleitet werden
- „kein freies Gas" (D007) – kein Pneumoperitoneum präoperativ
- „kein Bronchospasmus" (D009) – Asthma perioperativ komplikationslos  
**Beteiligte Dokumente:** P003-D006, P003-D007, P003-D009, P003-D012  
**Korrekte IPS-Behandlung:** Keine der negierten Befunde als Diagnose übernehmen.

---

## Trap 5 – Familienanamnese Mutter mit Asthma (Trap-Typ 5)
**Beschreibung:** In D001 und D002 wird erwähnt: „Mutter ebenfalls Asthmatikerin" bzw. „Mutter mit Asthma bronchiale." Dies ist eine Familienanamnese, keine eigene Erkrankung.  
**Beteiligte Dokumente:** P003-D001, P003-D002  
**Korrekte IPS-Behandlung:** Gehört in `must_not_include` mit `reason: family history`. **Nicht** in `problems_active` oder `past_history`.

---

## Trap 6 – Follikelzyste als vorübergehender Befund, kein aktives Problem (Trap-Typ 2 / Typ 6)
**Beschreibung:** Die Follikelzyste links wird sonographisch und intraoperativ beschrieben (D007, D010) und durch das Gynäko-Konsil (D012) als benigne eingestuft. Das Konsil empfiehlt ambulante Kontrolle. Die Zyste ist kein behandlungsbedürftiges Problem.  
**Beteiligte Dokumente:** P003-D007, P003-D010, P003-D012, P003-D014  
**Korrekte IPS-Behandlung:** Follikelzyste in `must_not_include` als `reason: ruled out` (keine relevante Pathologie). Nicht in `problems_active`.

---

## Trap 7 – Unbestätigte Laktoseintoleranz (Trap-Typ 8)
**Beschreibung:** Die Patientin berichtet der Pflegeperson (D005) über eine selbst diagnostizierte Laktoseintoleranz. Diese Angabe erscheint nirgendwo sonst in den Dokumenten und wurde nie klinisch bestätigt (kein Atemtest, kein Arztbefund).  
**Beteiligte Dokumente:** P003-D005  
**Korrekte IPS-Behandlung:** Laktoseintoleranz in `must_not_include` mit `reason: unconfirmed`. Nicht in `allergies_intolerances`.

---

## Trap 8 – „Pen-Allergie" als Abkürzung (Trap-Typ 9)
**Beschreibung:** In D008 (OA-Verlaufseintrag) wird die Allergie als **„Pen-Allergie"** abgekürzt (österreichisch-klinischer Jargon). In D001 (Vorbefund Kinderkrankenhaus) steht „CAVE Pen-Allergie!". Der korrekte Term lautet „Penicillin-Allergie". Ein NLP-System könnte „Pen-Allergie" nicht automatisch als Penicillin erkennen.  
**Beteiligte Dokumente:** P003-D001, P003-D008  
**Korrekte IPS-Behandlung:** Als „Penicillin (Amoxicillin)" in `allergies_intolerances` normalisieren.
