# Traps – Patient P001 (Hermine Bruckner)

## Trap 1 – Allergie nur im Pflegebericht (Trap-Typ 1)
**Beschreibung:** Die Patientin gibt beim Aufnahmegespräch gegenüber der Pflegeperson an, ASS (Acetylsalicylsäure) nicht zu vertragen – „sei ihr immer schlecht geworden davon". Dieser Hinweis erscheint **ausschließlich im Pflegebericht vom Aufnahmeabend** (D005). Der Aufnahmebefund (D004), die Hausarzt-Zuweisung (D003) und der Anästhesiebefund (D007) dokumentieren alle **„keine bekannten Allergien"**.  
**Beteiligte Dokumente:** P001-D003, P001-D004, P001-D005, P001-D007, P001-D028  
**Korrekte IPS-Behandlung:** ASS-Intoleranz als `allergies_intolerances` mit `verification: unconfirmed` eintragen. Nicht als bestätigte Allergie. Nicht ignorieren.

---

## Trap 2 – Verdachtsdiagnose Lungenembolie, später ausgeschlossen (Trap-Typ 2)
**Beschreibung:** Im Verlaufsbericht vom 07.09. (D014) und im Röntgenbefund (D015) wird klinisch eine Lungenembolie erwogen. Im ICU-Verlegungsbericht (D016) wird ebenfalls auf diese Möglichkeit hingewiesen. Die CT-Pulmonalisangiographie vom 08.09. (D017) schließt eine Lungenembolie **definitiv aus**. Der Entlassungsbrief (D028) bestätigt den Ausschluss.  
**Beteiligte Dokumente:** P001-D014, P001-D015, P001-D016, P001-D017, P001-D028  
**Korrekte IPS-Behandlung:** Lungenembolie darf **nicht** in `problems_active` oder `past_history` erscheinen. Sie gehört in `must_not_include` mit `reason: ruled out`.

---

## Trap 3 – Medikament gestartet, Dosis geändert, gestoppt (Trap-Typ 3)
**Beschreibung:** Heparin durchläuft drei Phasen: (a) Start als s.c. Thromboseprophylaxe ab 04.09. (D008); (b) Umstellung auf i.v. Heparin-Perfusor bei Vorhofflimmern ab 07.09. (D016) mit aPTT-gesteuerter Dosierung; (c) Stopp am 11.09. nach Beginn von Apixaban p.o. (D020, D021). Parallel gilt: Ampicillin/Sulbactam i.v. gestartet (D016), nach 4 Tagen umgestellt auf Amoxicillin/Clavulansäure p.o. (D020), welche dann nach 10 Tagen Gesamtantibiose beendet wird (D023).  
**Beteiligte Dokumente:** P001-D008, P001-D016, P001-D020, P001-D021, P001-D023  
**Korrekte IPS-Behandlung:** Heparin und beide Antibiotika in `medication_stopped_during_stay` eintragen; sie dürfen **nicht** in `medication_at_discharge` erscheinen.

---

## Trap 4 – Negationen (Trap-Typ 4)
**Beschreibung:** Mehrere Dokumente enthalten explizite Negationen, die ein KI-System fehlinterpretieren könnte:
- „kein Hinweis auf Infekt" (D011) – bezieht sich auf Wundinfektion, nicht auf die später aufgetretene Pneumonie
- „Kein Anhalt für Lungenembolie" (D017, D018) – nach initialem Verdacht
- „kein Hinweis auf frische Ischämie" (D007) – präoperatives EKG
- „keine RG" (D011, D005) – präoperativ/früh postoperativ, vor Auftreten der Pneumonie
- „kein Thrombus im LA-Appendage" (D019) – bei Echo  
**Beteiligte Dokumente:** P001-D005, P001-D007, P001-D011, P001-D017, P001-D018, P001-D019  
**Korrekte IPS-Behandlung:** Negierte Befunde dürfen **nicht** als Diagnosen übernommen werden. Nur der positiv bestätigte Befund (Pneumonie, VHF) zählt.

---

## Trap 5 – Widerspruch Apixaban-Dosis zwischen Dokumenten (Trap-Typ 7)
**Beschreibung:** Der ICU-Verlegungsbericht (D021) dokumentiert die Apixaban-Dosis fälschlicherweise als **„5mg 1-0-1"**. Das Kardio-Konsil (D019) empfiehlt **„5mg 2x täglich"** (= 5mg 2-0-2), und der darauffolgende Verlaufseintrag (D022) korrigiert diesen Fehler explizit auf **„5mg 2-0-2"**. Der Entlassungsbrief (D028) bestätigt die korrekte Dosis 2-0-2.  
**Beteiligte Dokumente:** P001-D019, P001-D021, P001-D022, P001-D028  
**Korrekte IPS-Behandlung:** Die spätere, korrigierende Dokumentation (D022) und der Entlassungsbrief (D028) sind maßgeblich: Apixaban 5mg **2-0-2**.

---

## Trap 6 – Patientenangabe ohne klinische Bestätigung (Trap-Typ 8)
**Beschreibung:** Die Patientin berichtet der Pflegeperson am 18.09. (D024), sie habe „früher Magenprobleme mit einem Blutungsgeschwür" gehabt. Diese Angabe erscheint **nirgendwo sonst** in der Dokumentation – weder in der Hausarzt-Zuweisung, noch im Aufnahmebefund, noch in früheren Befunden.  
**Beteiligte Dokumente:** P001-D024  
**Korrekte IPS-Behandlung:** Ulcus/Magenblutung darf **nicht** in `past_history` erscheinen. Sie gehört in `must_not_include` mit `reason: unconfirmed`.

---

## Trap 7 – Implantat nur in OP-Bericht und Radiologiebefund dokumentiert (Trap-Typ 10)
**Beschreibung:** Die genauen technischen Daten des Implantats (Hersteller: ProJoint GmbH, Modell PJ-CeraMax, Pfanne Ø52mm, Schaft Gr.5, Keramik-Keramik) stehen **nur im OP-Bericht** (D009) und im Röntgenbefund (D010). Der Aufnahmebefund, die Verlaufseinträge und die Pflegeberichte erwähnen das Implantat nicht im Detail.  
**Beteiligte Dokumente:** P001-D009, P001-D010, P001-D028  
**Korrekte IPS-Behandlung:** Das Implantat muss in `medical_devices_implants` mit vollem Modellnamen eingetragen werden, auch wenn es nur in diesen technischen Berichten erwähnt wird.

---

## Trap 8 – Z.n. Radiusfraktur: gelöste Vorerkrankung, nicht aktives Problem (Trap-Typ 6)
**Beschreibung:** Die distale Radiusfraktur links aus 06/2021 ist vollständig verheilt und hat keine Relevanz für den aktuellen Aufenthalt. Sie wird korrekt in Vorbriefen und Zuweisungen als Vorgeschichte erwähnt (D002, D003, D004).  
**Beteiligte Dokumente:** P001-D002, P001-D003, P001-D004  
**Korrekte IPS-Behandlung:** In `past_history` mit `resolved: 2021`, **nicht** in `problems_active`.
