# Traps – Patient P004 (Rudolf Hofer)

## Trap 1 – Sulfonamid-Allergie nur im Pflegebericht, Aufnahmebefund sagt „keine Allergien" (Trap-Typ 1)
**Beschreibung:** Der Aufnahmebefund (D004) und die Hausarzt-Zuweisung (D003) vermerken beide **„keine bekannten Allergien"**. Die Tochter berichtet am Aufnahmetag der Pflegeperson (D005) über eine mögliche Co-Trimoxazol-Reaktion des Vaters vor ca. 20 Jahren (Hautausschlag) – sie ist selbst unsicher ob es Co-Trimoxazol war. Diese Angabe erscheint nur im Pflegebericht. Erst am nächsten Tag (D009) klärt der Stationsarzt rück und trägt es als unbestätigte Allergie ein. Der Entlassungsbrief (D016) vermerkt die Sulfonamid-Vorsicht als CAVE.  
**Beteiligte Dokumente:** P004-D003, P004-D004, P004-D005, P004-D009, P004-D016  
**Korrekte IPS-Behandlung:** Sulfonamide (Co-Trimoxazol) in `allergies_intolerances` mit `verification: unconfirmed`, `criticality: unknown`.

---

## Trap 2 – V.a. Pneumonie erwähnt, danach nicht mehr aufrechterhalten (Trap-Typ 2)
**Beschreibung:** Im Verlaufseintrag vom 05.11. (D008) wird das erhöhte CRP kurz als „V.a. Pneumonie?" diskutiert. Gleichzeitig wird dort festgehalten: **„V.a. Pneumonie aktuell nicht aufrechterhalten"**, da der Rö-Thorax vom 04.11. (D007) explizit „kein Anhalt für Pneumonie" zeigt und das CRP der Stauung zugeschrieben wird.  
**Beteiligte Dokumente:** P004-D007, P004-D008  
**Korrekte IPS-Behandlung:** Pneumonie darf **nicht** in `problems_active` oder `past_history` erscheinen. Sie gehört in `must_not_include` mit `reason: ruled out`.

---

## Trap 3 – Spironolacton: pausiert wegen Hyperkaliämie, dann dauerhaft gestoppt (Trap-Typ 3)
**Beschreibung:** Spironolacton 25mg war Teil der Heimmedikation und wird bei Aufnahme zunächst weitergeführt, dann am 05.11. pausiert (D008, K+ 5,2). Nach K+-Normalisierung wird es **nicht** wieder aufgenommen, sondern durch Eplerenon 25mg ersetzt (D010, D012). Der Verlauf: Start (Heimmedikation) → Pause 05.11. → dauerhafter Stopp 09.11. → Eplerenon NEU. Im Verlaufseintrag (D008) wird Spironolacton als **„Spiro"** abgekürzt.  
**Beteiligte Dokumente:** P004-D001, P004-D003, P004-D008, P004-D010, P004-D012, P004-D016  
**Korrekte IPS-Behandlung:** Spironolacton in `medication_stopped_during_stay`. Eplerenon als neu in `medication_at_discharge`. Spironolacton darf **nicht** in `medication_at_discharge` erscheinen.

---

## Trap 4 – Negationen (Trap-Typ 4)
**Beschreibung:** Mehrere explizite Negationen:
- „kein Anhalt für Pneumonie" (D007) – Rö-Thorax-Befund
- „keine klinisch relevanten VT-Episoden" (D013) – SM-Speicher
- „kein Perikarderguss" (D010) – Echo
- „kein offener Herzeingriff" (D016, D015) – zur Klarstellung  
**Beteiligte Dokumente:** P004-D007, P004-D010, P004-D013, P004-D015, P004-D016  
**Korrekte IPS-Behandlung:** Keine dieser negierten Befunde als Diagnose übernehmen.

---

## Trap 5 – Widerspruch EF 30% vs. EF 35% zwischen Dokumenten (Trap-Typ 7)
**Beschreibung:** Im Kardiologie-Konsil (D010) wird explizit festgehalten: „Im Aufnahmebefund wurde EF nicht dokumentiert; bei Rückfrage an Assistenzarzt wurde dort von **'EF 30%'** gesprochen." Der Echokardiographie-Befund ergibt **EF 35%**. Der Echobefund durch den Kardiologen ist das maßgebliche Dokument.  
**Beteiligte Dokumente:** P004-D004, P004-D010  
**Korrekte IPS-Behandlung:** EF = **35%** (Echokardiographie, D010). Die mündliche Angabe „EF 30%" ist inkorrekt und aus dem Aufnahmebefund entstammt, der diese nicht dokumentiert hatte.

---

## Trap 6 – Patientenangabe „Herzoperation" ohne Bestätigung (Trap-Typ 8)
**Beschreibung:** Der demente Patient berichtet wiederholt (D005 Pflegebericht, D015 Pflegebericht vor Entlassung), er sei „früher am Herzen operiert" worden. Die Tochter und der Vorbefund (D001, Klinikum Linz-Nord 2019) belegen eindeutig: **kein offener Herzeingriff**, nur SM-Implantation. Die Angabe des Patienten ist krankheitsbedingt unzuverlässig.  
**Beteiligte Dokumente:** P004-D001, P004-D005, P004-D015, P004-D016  
**Korrekte IPS-Behandlung:** Keine Herzoperation (Bypass, Klappenersatz) in `past_history`. In `must_not_include` mit `reason: unconfirmed`. Das Implantat (SM) ist korrekt zu dokumentieren.

---

## Trap 7 – Familienanamnese Tochter mit DCM (Trap-Typ 5)
**Beschreibung:** In D002 (Neurologie-Ambulanz) wird erwähnt: „Tochter mit genetisch gesicherter dilatativer Kardiomyopathie (LMNA-Mutation)." Dies ist eine Familienanamnese der Tochter, nicht die eigene Erkrankung des Patienten.  
**Beteiligte Dokumente:** P004-D002  
**Korrekte IPS-Behandlung:** In `must_not_include` mit `reason: family history`. **Nicht** in `problems_active`.

---

## Trap 8 – Schrittmacher nur in altem Entlassungsbrief und Radiologiebefund (Trap-Typ 10)
**Beschreibung:** Die technischen Implantatdaten des Herzschrittmachers (Modell: Medtronic Advisa DR MRI SureScan, Modus DDD, Implantationsdatum 15.03.2019) stehen vollständig nur im **Entlassungsbrief von 2019** (D001) und werden bei der SM-Kontrolle (D013) bestätigt. Der Röntgenbefund (D007) erwähnt „Schrittmacher-Aggregat … in korrekter Lage" ohne Modellangabe. Aufnahme- und Verlaufsdokumentation nennen das SM nur kursorisch.  
**Beteiligte Dokumente:** P004-D001, P004-D007, P004-D013, P004-D016  
**Korrekte IPS-Behandlung:** Schrittmacher mit vollständigen Angaben in `medical_devices_implants`, auch wenn Modelldetails nur in D001 und D013 stehen.

---

## Trap 9 – Abkürzung „Spiro" für Spironolacton (Trap-Typ 9)
**Beschreibung:** Im Verlaufseintrag D008 wird das Medikament konsequent als **„Spiro"** bezeichnet statt „Spironolacton". Diese klinische Kurzform könnte von einem NLP-System nicht automatisch aufgelöst werden.  
**Beteiligte Dokumente:** P004-D008  
**Korrekte IPS-Behandlung:** „Spiro" = Spironolacton (ATC C03DA01) normalisieren.
