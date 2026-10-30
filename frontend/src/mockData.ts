// All synthetic. Replace via src/api.ts once the FastAPI backend is live.

export type Lang = "en" | "de" | "it";
export type Tr = Record<Lang, string>;
const same = (s: string): Tr => ({ en: s, de: s, it: s });

/** Clinical term translations keyed by code. Codes never change across languages. */
export const TERMS: Record<string, Tr> = {
  "I48.9": { en: "Atrial fibrillation", de: "Vorhofflimmern", it: "Fibrillazione atriale" },
  I10: { en: "Essential hypertension", de: "Essentielle Hypertonie", it: "Ipertensione essenziale" },
  "Z96.6": { en: "Presence of hip prosthesis", de: "Hüftprothese links", it: "Presenza di protesi d'anca" },
  "Z88.0": { en: "History of penicillin allergy", de: "Penicillin-Allergie in der Anamnese", it: "Anamnesi di allergia alla penicillina" },
  "E11.9": { en: "Type 2 diabetes mellitus", de: "Diabetes mellitus Typ 2", it: "Diabete mellito di tipo 2" },
  "N18.3": { en: "Chronic kidney disease, stage 3", de: "Chronische Nierenkrankheit, Stadium 3", it: "Malattia renale cronica, stadio 3" },
  "J45.9": { en: "Asthma", de: "Asthma bronchiale", it: "Asma" },
  "J44.9": { en: "COPD", de: "COPD", it: "BPCO" },
  B01AF02: { en: "Apixaban (anticoagulant)", de: "Apixaban (Gerinnungshemmer)", it: "Apixaban (anticoagulante)" },
  C09AA05: { en: "Ramipril", de: "Ramipril", it: "Ramipril" },
  C07AB07: { en: "Bisoprolol", de: "Bisoprolol", it: "Bisoprololo" },
  A10BA02: { en: "Metformin", de: "Metformin", it: "Metformina" },
  R03AK06: { en: "Salmeterol/fluticasone inhaler", de: "Salmeterol/Fluticason Inhalator", it: "Salmeterolo/fluticasone inalatore" },
  R03BB04: { en: "Tiotropium inhaler", de: "Tiotropium Inhalator", it: "Tiotropio inalatore" },
  "91936005": { en: "Penicillin allergy", de: "Penicillin-Allergie", it: "Allergia alla penicillina" },
  "300916003": { en: "Latex allergy", de: "Latexallergie", it: "Allergia al lattice" },
  "52734007": { en: "Hip prosthesis, left (2019)", de: "Hüftprothese links (2019)", it: "Protesi d'anca sinistra (2019)" },
  "8480-6": { en: "Systolic blood pressure", de: "Systolischer Blutdruck", it: "Pressione sistolica" },
  "33914-3": { en: "eGFR", de: "eGFR", it: "eGFR" },
  "718-7": { en: "Haemoglobin", de: "Hämoglobin", it: "Emoglobina" },
  "2160-0": { en: "Creatinine", de: "Kreatinin", it: "Creatinina" },
  "2823-3": { en: "Potassium", de: "Kalium", it: "Potassio" },
  "3016-3": { en: "TSH", de: "TSH", it: "TSH" },
  "33762-6": { en: "NT-proBNP", de: "NT-proBNP", it: "NT-proBNP" },
  "4548-4": { en: "HbA1c", de: "HbA1c", it: "HbA1c" },
  "19926-5": { en: "FEV1/FVC", de: "FEV1/FVC", it: "FEV1/FVC" },
};

export const UI = {
  problems: { en: "Problems", de: "Diagnosen", it: "Problemi" },
  medications: { en: "Medications", de: "Medikation", it: "Farmaci" },
  allergies: { en: "Allergies", de: "Allergien", it: "Allergie" },
  implants: { en: "Implants / Procedures", de: "Implantate / Eingriffe", it: "Impianti / Procedure" },
  measurements: { en: "Recent measurements", de: "Aktuelle Messwerte", it: "Misurazioni recenti" },
  emergency: { en: "Emergency – critical information", de: "Notfall – kritische Informationen", it: "Emergenza – informazioni critiche" },
  anticoag: { en: "On anticoagulant", de: "Gerinnungshemmer", it: "In terapia anticoagulante" },
  noAllergies: { en: "No allergy information in the source system", de: "Keine Allergieinformationen im Quellsystem", it: "Nessuna informazione sulle allergie nel sistema di origine" },
  none: { en: "None recorded", de: "Keine dokumentiert", it: "Nessuno registrato" },
  title: { en: "Patient Summary", de: "Patientenkurzakte", it: "Profilo sanitario sintetico" },
  codes: { en: "Show codes", de: "Codes anzeigen", it: "Mostra codici" },
} satisfies Record<string, Tr>;

export interface Patient {
  id: string;
  name: string;
  born: string;
  age: number;
  sex: "F" | "M";
  city: string;
  dataHolder: string;
  optedOut: boolean;
  crossBorderOptIn: boolean;
  problems: { code: string; since: string }[];
  medications: { code: string; dose: Tr; anticoagulant?: boolean }[];
  allergies: { code: string; severity: "high" | "moderate"; reaction?: string }[];
  implants: { code: string }[];
  measurements: { code: string; value: number; unit: string; date: string }[];
  /** Emergency information as selected by the backend (critical medication and conditions). */
  emergency?: { type: string; text: string; code?: string }[];
}

export const PATIENTS: Patient[] = [
  {
    id: "P-00421", name: "Maria Muster", born: "1958-03-12", age: 68, sex: "F", city: "Vienna", dataHolder: "Klinikum Wien Nord (synthetic)", optedOut: true, crossBorderOptIn: true,
    problems: [{ code: "I48.9", since: "2026-10-20" }, { code: "I10", since: "2015" }],
    medications: [
      { code: "B01AF02", dose: { en: "5 mg twice daily", de: "5 mg 1-0-1", it: "5 mg due volte al giorno" }, anticoagulant: true },
      { code: "C07AB07", dose: { en: "5 mg once daily", de: "5 mg 1-0-0", it: "5 mg una volta al giorno" } },
      { code: "C09AA05", dose: { en: "5 mg once daily", de: "5 mg 1-0-0", it: "5 mg una volta al giorno" } },
    ],
    allergies: [{ code: "91936005", severity: "high", reaction: "Hautausschlag" }],
    implants: [{ code: "52734007" }],
    measurements: [
      { code: "718-7", value: 13.2, unit: "g/dL", date: "2026-10-21" },
      { code: "2160-0", value: 0.9, unit: "mg/dL", date: "2026-10-21" },
      { code: "2823-3", value: 4.3, unit: "mmol/L", date: "2026-10-21" },
      { code: "3016-3", value: 1.8, unit: "mIU/L", date: "2026-10-21" },
      { code: "33762-6", value: 870, unit: "pg/mL", date: "2026-10-21" },
    ],
  },
  {
    id: "P-00102", name: "Herr K.", born: "1967-05-02", age: 59, sex: "M", city: "Graz", dataHolder: "Hospital B", optedOut: false, crossBorderOptIn: false,
    problems: [{ code: "E11.9", since: "2017" }, { code: "N18.3", since: "2024" }],
    medications: [{ code: "A10BA02", dose: same("1000 mg 1-0-1") }, { code: "C09AA05", dose: same("10 mg 1-0-0") }],
    allergies: [],
    implants: [],
    measurements: [
      { code: "4548-4", value: 7.4, unit: "%", date: "2026-09-30" },
      { code: "33914-3", value: 48, unit: "mL/min/1.73m²", date: "2026-09-30" },
    ],
  },
  {
    id: "P-00877", name: "Frau S.", born: "1992-01-19", age: 34, sex: "F", city: "Linz", dataHolder: "Hospital C", optedOut: false, crossBorderOptIn: true,
    problems: [{ code: "J45.9", since: "2008" }],
    medications: [{ code: "R03AK06", dose: same("50/250 µg 1-0-1") }],
    allergies: [{ code: "300916003", severity: "moderate" }],
    implants: [],
    measurements: [{ code: "19926-5", value: 0.74, unit: "ratio", date: "2026-08-14" }],
  },
  {
    id: "P-01233", name: "Herr B.", born: "1949-07-30", age: 77, sex: "M", city: "Vienna", dataHolder: "Hospital A", optedOut: false, crossBorderOptIn: false,
    problems: [{ code: "J44.9", since: "2016" }, { code: "I10", since: "2010" }],
    medications: [{ code: "R03BB04", dose: same("18 µg 1-0-0") }, { code: "C09AA05", dose: same("5 mg 1-0-0") }],
    allergies: [],
    implants: [],
    measurements: [
      { code: "19926-5", value: 0.58, unit: "ratio", date: "2026-10-02" },
      { code: "8480-6", value: 146, unit: "mmHg", date: "2026-10-02" },
    ],
  },
];

export const CODE_SYSTEM = {
  problems: "ICD-10", medications: "ATC", allergies: "SNOMED CT", implants: "SNOMED CT", measurements: "LOINC",
} as const;

// ---------- Access log (global, all primary-use screens) ----------

export type AccessDecision = "ALLOW" | "ALLOW_CROSS_BORDER" | "ALLOW_EMERGENCY" | "DENY";

export interface AccessEntry {
  id: string;
  when: string;
  who: string;
  role?: string;
  org: string;
  country?: string;
  patient?: string;
  sections: string[];
  decision?: AccessDecision | "LOGGED";
  rule?: number;
  reason?: string;
  kind: "normal" | "break-the-glass" | "blocked-download";
}

export const INITIAL_ACCESS_LOG: AccessEntry[] = [
  { id: "a1", who: "Dr. Anna Huber", role: "Oberärztin Kardiologie", org: "Klinikum Wien Nord (synthetic)", country: "AT", patient: "P-00421", when: "2026-10-20 14:40", sections: ["Patient Summary", "Measurements"], decision: "ALLOW", rule: 2, reason: "Inpatient treatment ENC-7731", kind: "normal" },
];

// ---------- Secondary use ----------

export type RequestType = "health data request" | "health data access application";
export type Decision = "REJECT" | "APPROVE_STATISTICAL" | "APPROVE_SPE";

export interface ResultRow {
  group: string;
  n: number;
  value?: number; // pct or mean
}

export interface ResearchRequest {
  id: string;
  applicant: string;
  purpose: string;
  type: RequestType;
  text: string;
  whyNotStatistics?: string;
  prohibitedPurpose?: string;
  metric?: { label: string; kind: "pct" | "mean"; unit?: string };
  results?: ResultRow[];
  terms: { term: string; system: string; codes: string; found: boolean }[];
  sql: string;
}

export const ARTICLES: Record<string, string> = {
  "Art. 53": "Lists the purposes for which health data may be used for research, innovation and public health.",
  "Art. 54": "Forbids certain uses, e.g. insurance premiums, advertising or decisions harming individuals.",
  "Art. 66": "Principle of data minimisation: only the data needed for the purpose is made available.",
  "Art. 68": "Rules for health data access applications (record-level data).",
  "Art. 69": "Rules for health data requests – answers only in anonymised statistical form.",
  "Art. 73": "Data must be processed in a secure processing environment and cannot be downloaded.",
  "Art. 71": "Right of individuals to opt out of secondary use of their health data.",
};

export const OPTED_OUT_EXCLUDED = 1284;
export const TOTAL_PATIENTS = 20000;

const ag = ["18–39", "40–59", "60–79", "80+"] as const;

export const REQUESTS: ResearchRequest[] = [
  {
    id: "R01", applicant: "Univ. Graz – Public Health", purpose: "Prevalence of type 2 diabetes by hospital", type: "health data request",
    text: "How many adult patients have type 2 diabetes in each hospital, and what share of all patients is that?",
    metric: { label: "Prevalence", kind: "pct", unit: "%" },
    results: [{ group: "Hospital A", n: 742, value: 10.8 }, { group: "Hospital B", n: 611, value: 9.4 }, { group: "Hospital C", n: 488, value: 8.97 }],
    terms: [{ term: "type 2 diabetes", system: "ICD-10", codes: "E11", found: true }],
    sql: "SELECT data_holder, COUNT(DISTINCT patient_id) AS n,\n  ROUND(100.0*COUNT(DISTINCT patient_id)/MAX(total),1) AS pct\nFROM conditions c JOIN patients p USING (patient_id)\nWHERE c.icd10 LIKE 'E11%' AND p.opted_out = FALSE AND p.age >= 18\nGROUP BY data_holder;",
  },
  {
    id: "R02", applicant: "MedUni Wien – Cardiology", purpose: "Anticoagulant use in atrial fibrillation by age group", type: "health data request",
    text: "Among patients with atrial fibrillation, what percentage receives apixaban, by age group (18–39, 40–59, 60–79, 80+)?",
    metric: { label: "On apixaban", kind: "pct", unit: "%" },
    results: [{ group: ag[0], n: 6, value: 33.3 }, { group: ag[1], n: 84, value: 52.38 }, { group: ag[2], n: 412, value: 61.65 }, { group: ag[3], n: 197, value: 58.9 }],
    terms: [
      { term: "atrial fibrillation", system: "ICD-10", codes: "I48", found: true },
      { term: "apixaban", system: "ATC", codes: "B01AF02", found: true },
    ],
    sql: "SELECT age_group(p.age) AS grp, COUNT(DISTINCT p.patient_id) AS n,\n  ROUND(100.0*AVG(CASE WHEN m.atc='B01AF02' THEN 1 ELSE 0 END),1) AS pct\nFROM patients p\nJOIN conditions c ON c.patient_id=p.patient_id AND c.icd10 LIKE 'I48%'\nLEFT JOIN medications m ON m.patient_id=p.patient_id\nWHERE p.opted_out = FALSE\nGROUP BY grp ORDER BY grp;",
  },
  {
    id: "R03", applicant: "SecureLife Insurance AG", purpose: "Risk scores for setting insurance premiums", type: "health data access application",
    text: "We want record-level data on patients with atrial fibrillation to calculate individual risk scores for setting insurance premiums.",
    prohibitedPurpose: "setting insurance premiums",
    terms: [{ term: "atrial fibrillation", system: "ICD-10", codes: "I48", found: true }],
    sql: "-- No query generated: request rejected at step 1 (prohibited purpose).",
  },
  {
    id: "R04", applicant: "Diabetes Austria Network", purpose: "Mean HbA1c in metformin users by hospital", type: "health data request",
    text: "What is the mean HbA1c among patients with type 2 diabetes taking metformin, by hospital?",
    metric: { label: "Mean HbA1c", kind: "mean", unit: "%" },
    results: [{ group: "Hospital A", n: 402, value: 7.12 }, { group: "Hospital B", n: 377, value: 7.38 }, { group: "Hospital C", n: 290, value: 7.05 }],
    terms: [
      { term: "type 2 diabetes", system: "ICD-10", codes: "E11", found: true },
      { term: "metformin", system: "ATC", codes: "A10BA02", found: true },
      { term: "HbA1c", system: "LOINC", codes: "4548-4", found: true },
    ],
    sql: "SELECT data_holder, COUNT(DISTINCT p.patient_id) n, ROUND(AVG(o.value),1) mean_hba1c\nFROM patients p\nJOIN conditions c ON c.patient_id=p.patient_id AND c.icd10 LIKE 'E11%'\nJOIN medications m ON m.patient_id=p.patient_id AND m.atc='A10BA02'\nJOIN observations o ON o.patient_id=p.patient_id AND o.loinc='4548-4'\nWHERE p.opted_out = FALSE GROUP BY data_holder;",
  },
  {
    id: "R05", applicant: "TU Wien – AI in Medicine Lab", purpose: "Training a stroke-risk model for AF patients", type: "health data access application",
    text: "We request record-level access to patients with atrial fibrillation (conditions, medications, observations) to develop a machine-learning stroke-risk model.",
    whyNotStatistics: "Model training requires individual-level feature vectors and time sequences; aggregated tables cannot capture interactions between medication, kidney function and outcomes.",
    terms: [
      { term: "atrial fibrillation", system: "ICD-10", codes: "I48", found: true },
      { term: "anticoagulants", system: "ATC", codes: "B01A*", found: true },
      { term: "eGFR", system: "LOINC", codes: "33914-3", found: true },
      { term: "stroke", system: "ICD-10", codes: "I63", found: true },
    ],
    sql: "CREATE TABLE spe_r05.cohort AS\nSELECT p.pseudo_id, c.*, m.*, o.*\nFROM patients p\nJOIN conditions c ON c.patient_id=p.patient_id\nLEFT JOIN medications m ON m.patient_id=p.patient_id\nLEFT JOIN observations o ON o.patient_id=p.patient_id\nWHERE p.opted_out = FALSE\n  AND EXISTS (SELECT 1 FROM conditions x WHERE x.patient_id=p.patient_id AND x.icd10 LIKE 'I48%');",
  },
  {
    id: "R06", applicant: "FH Campus Wien – Nursing", purpose: "Hypertension and kidney disease co-occurrence", type: "health data access application",
    text: "We would like data on patients with hypertension and chronic kidney disease to describe how often both occur together, by sex.",
    metric: { label: "Share with CKD", kind: "pct", unit: "%" },
    results: [{ group: "Female", n: 1630, value: 14.21 }, { group: "Male", n: 1702, value: 16.85 }, { group: "Diverse / unknown", n: 4, value: 25 }],
    terms: [
      { term: "hypertension", system: "ICD-10", codes: "I10", found: true },
      { term: "chronic kidney disease", system: "ICD-10", codes: "N18", found: true },
    ],
    sql: "SELECT p.sex, COUNT(DISTINCT p.patient_id) n,\n  ROUND(100.0*AVG(CASE WHEN EXISTS(SELECT 1 FROM conditions k WHERE k.patient_id=p.patient_id AND k.icd10 LIKE 'N18%') THEN 1 ELSE 0 END),1) pct\nFROM patients p JOIN conditions c ON c.patient_id=p.patient_id AND c.icd10='I10'\nWHERE p.opted_out = FALSE GROUP BY p.sex;",
  },
  {
    id: "R07", applicant: "PharmaReach Marketing GmbH", purpose: "Targeted advertising to diabetes patients", type: "health data access application",
    text: "Identify patients with type 2 diabetes so we can target them with advertising for a new glucose monitor.",
    prohibitedPurpose: "advertising or marketing to patients",
    terms: [{ term: "type 2 diabetes", system: "ICD-10", codes: "E11", found: true }],
    sql: "-- No query generated: request rejected at step 1 (prohibited purpose).",
  },
  {
    id: "R08", applicant: "Austrian Arthroplasty Registry", purpose: "Hip prosthesis patients by age group", type: "health data request",
    text: "How many patients have a hip prosthesis, by age group, and what share of them are on anticoagulants?",
    metric: { label: "On anticoagulants", kind: "pct", unit: "%" },
    results: [{ group: ag[0], n: 0 }, { group: ag[1], n: 118, value: 11.02 }, { group: ag[2], n: 534, value: 22.47 }, { group: ag[3], n: 241, value: 31.12 }],
    terms: [
      { term: "hip prosthesis", system: "ICD-10", codes: "Z96.64", found: true },
      { term: "anticoagulants", system: "ATC", codes: "B01A*", found: true },
    ],
    sql: "SELECT age_group(p.age) grp, COUNT(DISTINCT p.patient_id) n,\n  ROUND(100.0*AVG(CASE WHEN m.atc LIKE 'B01A%' THEN 1 ELSE 0 END),1) pct\nFROM patients p JOIN conditions c ON c.patient_id=p.patient_id AND c.icd10 LIKE 'Z96.64%'\nLEFT JOIN medications m ON m.patient_id=p.patient_id\nWHERE p.opted_out = FALSE GROUP BY grp;",
  },
  {
    id: "R09", applicant: "Ministry of Health – Epidemiology", purpose: "Mean FEV1/FVC in COPD by hospital", type: "health data request",
    text: "What is the mean FEV1/FVC ratio in patients with COPD, by hospital?",
    metric: { label: "Mean FEV1/FVC", kind: "mean" },
    results: [{ group: "Hospital A", n: 356, value: 0.612 }, { group: "Hospital B", n: 9, value: 0.59 }, { group: "Hospital C", n: 221, value: 0.634 }],
    terms: [
      { term: "COPD", system: "ICD-10", codes: "J44", found: true },
      { term: "FEV1/FVC", system: "LOINC", codes: "19926-5", found: true },
    ],
    sql: "SELECT data_holder, COUNT(DISTINCT p.patient_id) n, ROUND(AVG(o.value),1) mean\nFROM patients p JOIN conditions c ON c.patient_id=p.patient_id AND c.icd10 LIKE 'J44%'\nJOIN observations o ON o.patient_id=p.patient_id AND o.loinc='19926-5'\nWHERE p.opted_out = FALSE GROUP BY data_holder;",
  },
  {
    id: "R10", applicant: "St. Anna Children's Research", purpose: "Asthma in children and young adults", type: "health data request",
    text: "How many patients under 18 and 18–25 have asthma, and how many use a combination inhaler?",
    metric: { label: "Combination inhaler", kind: "pct", unit: "%" },
    results: [{ group: "Under 18", n: 3, value: 66.7 }, { group: "18–25", n: 143, value: 41.26 }],
    terms: [
      { term: "asthma", system: "ICD-10", codes: "J45", found: true },
      { term: "combination inhaler", system: "ATC", codes: "R03AK", found: true },
      { term: "paediatric spacer", system: "SNOMED CT", codes: "—", found: false },
    ],
    sql: "SELECT CASE WHEN p.age<18 THEN 'Under 18' ELSE '18–25' END grp, COUNT(DISTINCT p.patient_id) n,\n  ROUND(100.0*AVG(CASE WHEN m.atc LIKE 'R03AK%' THEN 1 ELSE 0 END),1) pct\nFROM patients p JOIN conditions c ON c.patient_id=p.patient_id AND c.icd10 LIKE 'J45%'\nLEFT JOIN medications m ON m.patient_id=p.patient_id\nWHERE p.opted_out = FALSE AND p.age <= 25 GROUP BY grp;",
  },
];

export const SPE_R05 = {
  id: "SPE-R05",
  patients: 2317,
  recordTypes: ["conditions", "medications", "observations"],
  idsKept: "Pseudonymised patient IDs (re-identification key held by HDAB only)",
  created: "2026-10-29 14:02 CET",
};

export const DATASETS = [
  { holder: "Hospital A", title: "Hospital A – Inpatient & outpatient EHR extract", description: "Structured diagnoses, medication orders and laboratory results from a large Viennese teaching hospital.", from: "2015-01", to: "2026-09", recordTypes: ["conditions", "medications", "observations", "procedures"], patients: 9000 },
  { holder: "Hospital B", title: "Hospital B – Regional hospital EHR extract", description: "Clinical data from a regional hospital in Styria with focus on internal medicine and diabetes care.", from: "2017-01", to: "2026-09", recordTypes: ["conditions", "medications", "observations"], patients: 6000 },
  { holder: "Hospital C", title: "Hospital C – Pulmonology & paediatrics EHR extract", description: "Respiratory and paediatric clinical data including spirometry from an Upper Austrian hospital.", from: "2016-06", to: "2026-09", recordTypes: ["conditions", "medications", "observations"], patients: 5000 },
];

export const METRICS = REQUESTS.map((r, i) => ({
  id: r.id,
  decisionCorrect: true,
  numbersCorrect: r.results && i < 9 && r.id !== "R10" ? true : null,
  privacyLeaks: 0,
  consistent: true,
  time: [6.2, 7.8, 3.1, 8.4, 9.7, 7.1, 2.9, 6.6, 7.3, 5.8][i] ?? 0,
}));

export const APPROVED_PROJECTS = [
  { id: "R01", title: "Prevalence of type 2 diabetes", org: "Univ. Graz", kind: "Statistics" },
  { id: "R02", title: "Anticoagulant use in atrial fibrillation", org: "MedUni Wien", kind: "Statistics" },
  { id: "R05", title: "Stroke-risk model for AF patients", org: "TU Wien", kind: "Secure Processing Environment" },
  { id: "R08", title: "Hip prosthesis patients and anticoagulation", org: "Arthroplasty Registry", kind: "Statistics" },
];

export const REASONING: Record<Decision, Tr> = {
  REJECT: {
    en: "Your request cannot be approved. The stated purpose is prohibited under the European Health Data Space: health data may never be used for {p}. No data has been accessed.",
    de: "Ihr Antrag kann nicht genehmigt werden. Der angegebene Zweck ist im Europäischen Gesundheitsdatenraum verboten: Gesundheitsdaten dürfen niemals für {p} verwendet werden. Es wurden keine Daten abgerufen.",
    it: "La sua richiesta non può essere approvata. La finalità indicata è vietata nello Spazio europeo dei dati sanitari: i dati sanitari non possono mai essere usati per {p}. Nessun dato è stato consultato.",
  },
  APPROVE_STATISTICAL: {
    en: "Your request is approved. You receive anonymised statistics only. Small groups (fewer than 10 patients) are hidden to protect privacy, and patients who opted out are not included.",
    de: "Ihr Antrag ist genehmigt. Sie erhalten ausschließlich anonymisierte Statistiken. Kleine Gruppen (unter 10 Personen) werden zum Schutz der Privatsphäre ausgeblendet; Personen mit Opt-out sind nicht enthalten.",
    it: "La sua richiesta è approvata. Riceverà solo statistiche anonimizzate. I gruppi piccoli (meno di 10 pazienti) sono nascosti per tutelare la privacy e i pazienti che hanno esercitato l'opt-out non sono inclusi.",
  },
  APPROVE_SPE: {
    en: "Your application is approved for a Secure Processing Environment. You explained why statistics are not enough. You can analyse pseudonymised records inside the environment, but only aggregate results may leave it.",
    de: "Ihr Antrag ist für eine sichere Verarbeitungsumgebung genehmigt. Sie haben begründet, warum Statistiken nicht ausreichen. Sie können pseudonymisierte Datensätze in der Umgebung analysieren; nur aggregierte Ergebnisse dürfen sie verlassen.",
    it: "La sua domanda è approvata per un ambiente di trattamento sicuro. Ha spiegato perché le statistiche non sono sufficienti. Può analizzare record pseudonimizzati nell'ambiente, ma solo risultati aggregati possono uscirne.",
  },
};

// ---------- Primary use: KIS sources, discharge letter, IPS, access scenarios ----------

export const HOSPITAL = "Klinikum Wien Nord (synthetic)";
export const ENCOUNTER = { id: "ENC-7731", department: "Cardiology", from: "20.10.2026", to: "24.10.2026", admitted: "2026-10-20 14:15", discharged: "2026-10-24 10:30" };
export const SIGNER = "Dr. Anna Huber, Oberärztin Kardiologie";

export const HL7_ORU = [
  "MSH|^~\\&|LAB|KH_WIEN_NORD|KIS|KH_WIEN_NORD|20261021083000||ORU^R01|MSG-10007|P|2.5",
  "PID|1||P-00421^^^KH_WIEN_NORD^PI||Muster^Maria||19580312|F",
  "OBR|1||LAB-7781|LABPANEL^Routinelabor^L|||20261021070000",
  "OBX|1|NM|718-7^Hemoglobin [Mass/volume] in Blood^LN||13.2|g/dL|12.0-16.0|N|||F|||20261021070000",
  "OBX|2|NM|2160-0^Creatinine [Mass/volume] in Serum or Plasma^LN||0.9|mg/dL|0.5-1.0|N|||F|||20261021070000",
  "OBX|3|NM|2823-3^Potassium [Moles/volume] in Serum or Plasma^LN||4.3|mmol/L|3.5-5.1|N|||F|||20261021070000",
  "OBX|4|NM|3016-3^Thyrotropin [Units/volume] in Serum or Plasma^LN||1.8|mIU/L|0.4-4.0|N|||F|||20261021070000",
  "OBX|5|NM|33762-6^NT-proBNP [Mass/volume] in Serum or Plasma^LN||870|pg/mL|<300|H|||F|||20261021070000",
].join("\n");

export const HL7_ADT = [
  "MSH|^~\\&|KIS|KH_WIEN_NORD|NAV|KH_WIEN_NORD|20261024103000||ADT^A03|MSG-20031|P|2.5",
  "EVN|A03|20261024103000",
  "PID|1||P-00421^^^KH_WIEN_NORD^PI||Muster^Maria||19580312|F",
  "PV1|1|I|KARD^201^1^KH_WIEN_NORD||||HUBER^Anna^^^Dr.|||KAR" + "|".repeat(9) + "ENC-7731" + "|".repeat(25) + "20261020141500|20261024103000",
].join("\n");

export interface SourceDoc { id: string; label: string; kind: "hl7" | "fhir" | "note"; title: string; content: string }

const fhir = (o: object) => JSON.stringify(o, null, 2);
const medStmt = (id: string, atc: string, name: string, dose: string, status = "active") =>
  fhir({ resourceType: "MedicationStatement", id, status, subject: { reference: "Patient/P-00421" }, context: { reference: "Encounter/ENC-7731" }, medicationCodeableConcept: { coding: [{ system: "http://www.whocc.no/atc", code: atc, display: name }] }, dosage: [{ text: dose }] });
const cond = (id: string, code: string, display: string, role: string) =>
  fhir({ resourceType: "Condition", id, subject: { reference: "Patient/P-00421" }, encounter: { reference: "Encounter/ENC-7731" }, category: [{ text: role }], code: { coding: [{ system: "http://hl7.org/fhir/sid/icd-10", code, display }] } });

const NOTE_2010 = "Dekurs 20.10.2026 14:40 – Dr. Huber\nAufnahme mit Herzrasen seit 2 Tagen; im EKG Vorhofflimmern mit einer Herzfrequenz von 138/min. RR 148/90. Bekannte Penicillin-Allergie (Exanthem). Bei einem CHA₂DS₂-VASc-Score von 3 Beginn einer Antikoagulation mit Apixaban. Bisoprolol 5 mg zur Frequenzkontrolle.";
const NOTE_2210 = "Dekurs 22.10.2026 09:10 – Dr. Huber\nAm 22.10. Herzfrequenz 78/min, beschwerdefrei. Patientin mobil.";
const NOTE_2310 = "Dekurs 23.10.2026 11:00 – Dr. Huber\nPantoprazol abgesetzt (keine Indikation). Ramipril unverändert fortgeführt.";
const NOTE_2410 = "Dekurs 24.10.2026 09:30 – Dr. Huber\nEntlassung am 24.10. in gutem Allgemeinzustand. Kardiologische Kontrolle in 4–6 Wochen, Evaluierung Rhythmuskontrolle. Fortführung der Antikoagulation.";
const NOTE_ECHO = "Echokardiographie 21.10.2026 – Befund\nLVEF 58 %, kein relevantes Vitium. Linker Vorhof leicht dilatiert.";

export const SOURCES: Record<string, SourceDoc> = {
  "dek-2010": { id: "dek-2010", label: "Dekurs 20.10.", kind: "note", title: "Progress note (free text)", content: NOTE_2010 },
  "dek-2210": { id: "dek-2210", label: "Dekurs 22.10.", kind: "note", title: "Progress note (free text)", content: NOTE_2210 },
  "dek-2310": { id: "dek-2310", label: "Dekurs 23.10.", kind: "note", title: "Progress note (free text)", content: NOTE_2310 },
  "dek-2410": { id: "dek-2410", label: "Dekurs 24.10.", kind: "note", title: "Progress note (free text)", content: NOTE_2410 },
  echo: { id: "echo", label: "Echo-Befund 21.10.", kind: "note", title: "Echocardiography report", content: NOTE_ECHO },
  adt: { id: "adt", label: "ADT^A03 ENC-7731", kind: "hl7", title: "HL7 v2 ADT^A03 discharge", content: HL7_ADT },
  "kis-query": { id: "kis-query", label: "KIS-Abfrage 24.10.", kind: "note", title: "KIS query result", content: "KIS query 24.10.2026 10:31 – open orders / pending results for ENC-7731\nKeine Daten im KIS." },
  ...Object.fromEntries([1, 2, 3, 4, 5].map((n) => [`obx-${n}`, { id: `obx-${n}`, label: `ORU MSG-10007 OBX-${n}`, kind: "hl7" as const, title: "HL7 v2 ORU^R01 lab result", content: HL7_ORU }])),
  "cond-af": { id: "cond-af", label: "Condition/cond-af", kind: "fhir", title: "FHIR Condition", content: cond("cond-af", "I48.9", "Vorhofflimmern", "Hauptdiagnose") },
  "cond-htn": { id: "cond-htn", label: "Condition/cond-htn", kind: "fhir", title: "FHIR Condition", content: cond("cond-htn", "I10", "Essentielle Hypertonie", "Nebendiagnose") },
  "cond-z88": { id: "cond-z88", label: "Condition/cond-z88", kind: "fhir", title: "FHIR Condition", content: cond("cond-z88", "Z88.0", "Penicillin-Allergie in der Anamnese", "Nebendiagnose") },
  "cond-hip": { id: "cond-hip", label: "Condition/cond-hip", kind: "fhir", title: "FHIR Condition", content: cond("cond-hip", "Z96.6", "Hüftprothese links seit 2019", "Nebendiagnose") },
  "allergy-pen": { id: "allergy-pen", label: "AllergyIntolerance/allergy-pen", kind: "fhir", title: "FHIR AllergyIntolerance", content: fhir({ resourceType: "AllergyIntolerance", id: "allergy-pen", patient: { reference: "Patient/P-00421" }, criticality: "high", code: { coding: [{ system: "http://snomed.info/sct", code: "91936005", display: "Allergy to penicillin" }] }, reaction: [{ manifestation: [{ text: "Hautausschlag" }] }] }) },
  "med-apixaban": { id: "med-apixaban", label: "MedicationStatement/med-apixaban", kind: "fhir", title: "FHIR MedicationStatement", content: medStmt("med-apixaban", "B01AF02", "Apixaban", "5 mg 1-0-1") },
  "med-bisoprolol": { id: "med-bisoprolol", label: "MedicationStatement/med-bisoprolol", kind: "fhir", title: "FHIR MedicationStatement", content: medStmt("med-bisoprolol", "C07AB07", "Bisoprolol", "5 mg 1-0-0") },
  "med-ramipril": { id: "med-ramipril", label: "MedicationStatement/med-ramipril", kind: "fhir", title: "FHIR MedicationStatement", content: medStmt("med-ramipril", "C09AA05", "Ramipril", "5 mg 1-0-0") },
  "med-pantoprazol": { id: "med-pantoprazol", label: "MedicationStatement/med-pantoprazol", kind: "fhir", title: "FHIR MedicationStatement", content: medStmt("med-pantoprazol", "A02BC02", "Pantoprazol", "40 mg 1-0-0", "stopped") },
};

/** A letter sentence or row. `highlight` marks the matching text inside the source. */
export interface LetterItem { id: string; text: string; source: string; highlight?: string }
export interface LabRow { id: string; name: string; loinc: string; value: string; unit: string; ref: string; flag?: string; date: string; source: string; highlight: string }
export interface MedRow { id: string; name: string; atc: string; dose: string; change: "NEW" | "UNCHANGED" | "STOPPED"; note?: string; source: string }

export const LETTER = {
  diagnoses: [
    { id: "dx1", text: "Primary diagnosis: atrial fibrillation (ICD-10 I48.9)", source: "cond-af" },
    { id: "dx2", text: "Secondary diagnosis: essential hypertension (I10)", source: "cond-htn" },
    { id: "dx3", text: "Secondary diagnosis: history of penicillin allergy (Z88.0)", source: "cond-z88" },
    { id: "dx4", text: "Secondary diagnosis: left hip prosthesis since 2019 (Z96.6)", source: "cond-hip" },
  ] as LetterItem[],
  allergies: [{ id: "al1", text: "Penicillin – skin rash (SNOMED CT 91936005)", source: "allergy-pen" }] as LetterItem[],
  course: [
    { id: "c1", text: "Admitted with palpitations for two days; ECG showed atrial fibrillation with a heart rate of 138/min.", source: "dek-2010", highlight: "Aufnahme mit Herzrasen seit 2 Tagen; im EKG Vorhofflimmern mit einer Herzfrequenz von 138/min." },
    { id: "c2", text: "Bisoprolol started for rate control.", source: "med-bisoprolol" },
    { id: "c3", text: "Anticoagulation with apixaban started with a CHA₂DS₂-VASc score of 3.", source: "dek-2010", highlight: "Bei einem CHA₂DS₂-VASc-Score von 3 Beginn einer Antikoagulation mit Apixaban." },
    { id: "c4", text: "On 22 October, heart rate was 78/min and the patient was symptom-free.", source: "dek-2210", highlight: "Am 22.10. Herzfrequenz 78/min, beschwerdefrei." },
    { id: "c5", text: "Discharged on 24 October in good general condition.", source: "dek-2410", highlight: "Entlassung am 24.10. in gutem Allgemeinzustand." },
  ] as LetterItem[],
  labs: [
    { id: "l1", name: "Hb", loinc: "718-7", value: "13.2", unit: "g/dL", ref: "12.0–16.0", date: "21.10.2026", source: "obx-1", highlight: "OBX|1|" },
    { id: "l2", name: "Creatinine", loinc: "2160-0", value: "0.9", unit: "mg/dL", ref: "0.5–1.0", date: "21.10.2026", source: "obx-2", highlight: "OBX|2|" },
    { id: "l3", name: "Potassium", loinc: "2823-3", value: "4.3", unit: "mmol/L", ref: "3.5–5.1", date: "21.10.2026", source: "obx-3", highlight: "OBX|3|" },
    { id: "l4", name: "TSH", loinc: "3016-3", value: "1.8", unit: "mIU/L", ref: "0.4–4.0", date: "21.10.2026", source: "obx-4", highlight: "OBX|4|" },
    { id: "l5", name: "NT-proBNP", loinc: "33762-6", value: "870", unit: "pg/mL", ref: "<300", flag: "elevated", date: "21.10.2026", source: "obx-5", highlight: "OBX|5|" },
    { id: "l6", name: "Echo LVEF", loinc: "10230-1", value: "58", unit: "% – no significant valvular disease", ref: "≥50", date: "21.10.2026", source: "echo", highlight: "LVEF 58 %, kein relevantes Vitium." },
  ] as LabRow[],
  meds: [
    { id: "m1", name: "Apixaban", atc: "B01AF02", dose: "5 mg 1-0-1", change: "NEW", source: "med-apixaban" },
    { id: "m2", name: "Bisoprolol", atc: "C07AB07", dose: "5 mg 1-0-0", change: "NEW", source: "med-bisoprolol" },
    { id: "m3", name: "Ramipril", atc: "C09AA05", dose: "5 mg 1-0-0", change: "UNCHANGED", source: "med-ramipril" },
    { id: "m4", name: "Pantoprazol", atc: "A02BC02", dose: "—", change: "STOPPED", note: "no indication", source: "dek-2310" },
  ] as MedRow[],
  recommendations: [
    { id: "r1", text: "Cardiology follow-up in 4–6 weeks; evaluate rhythm control.", source: "dek-2410", highlight: "Kardiologische Kontrolle in 4–6 Wochen, Evaluierung Rhythmuskontrolle." },
    { id: "r2", text: "Continue anticoagulation.", source: "dek-2410", highlight: "Fortführung der Antikoagulation." },
  ] as LetterItem[],
  openPoints: [{ id: "o1", text: "No data in the KIS", source: "kis-query", highlight: "Keine Daten im KIS." }] as LetterItem[],
};

export const IPS_VERSION = "Version 3 · generated 24.10.2026 10:32 from KIS data · source: Encounter ENC-7731";

/** Demo clock for flows (the app pretends "now" is in the story timeline). */
export const DEMO_TIME = { signed: "2026-10-24 10:31", consent: "2026-10-28 18:05", crossBorder: "2026-10-30 14:12" };

export interface AccessScenario {
  id: string;
  label: string;
  who: string;
  authorised: boolean;
  crossBorder: boolean;
  treatmentRelationship?: boolean;
  identityChecked?: boolean;
  crossBorderOptIn?: boolean;
  emergency?: boolean;
  reason?: string;
}

export const ACCESS_SCENARIOS: AccessScenario[] = [
  { id: "s1", label: "National doctor (Vienna)", who: "Dr. Anna Huber, Klinikum Wien Nord", authorised: true, crossBorder: false, treatmentRelationship: true },
  { id: "s2", label: "Italian doctor with consent", who: "Dr. Giulia Rossi, Ospedale di Firenze", authorised: true, crossBorder: true, identityChecked: true, crossBorderOptIn: true },
  { id: "s3", label: "Italian doctor without consent", who: "Dr. Giulia Rossi, Ospedale di Firenze", authorised: true, crossBorder: true, identityChecked: true, crossBorderOptIn: false },
  { id: "s4", label: "Emergency (unconscious patient)", who: "Dr. Giulia Rossi, Ospedale di Firenze", authorised: true, crossBorder: true, identityChecked: false, crossBorderOptIn: false, emergency: true, reason: "Unconscious after fall, suspected bleeding" },
  { id: "s5", label: "Non-authorised user", who: "Insurance clerk", authorised: false, crossBorder: false },
];

export const PRIMARY_METRICS = [
  { label: "Completeness", value: "100 %" },
  { label: "Invented content", value: "0" },
  { label: "Medication changes correct", value: "100 %" },
  { label: "FHIR valid", value: "100 %" },
  { label: "HL7 v2 → FHIR fields correct", value: "100 %" },
  { label: "Access decisions", value: "5/5" },
  { label: "Transmission without sign-off", value: "0" },
  { label: "Access log coverage", value: "100 %" },
  { label: "Consistency", value: "3/3" },
  { label: "Time to letter", value: "< 10 s" },
];

export const REFERENCE_P00421 = {
  patient: "P-00421",
  encounter: "ENC-7731",
  diagnoses: [
    { code: "I48.9", role: "main", display: "Vorhofflimmern" },
    { code: "I10", role: "secondary", display: "Essentielle Hypertonie" },
    { code: "Z88.0", role: "secondary", display: "Penicillin-Allergie in der Anamnese" },
    { code: "Z96.6", role: "secondary", display: "Hüftprothese links seit 2019" },
  ],
  allergies: [{ code: "91936005", system: "SNOMED CT", reaction: "Hautausschlag" }],
  medicationChanges: [
    { atc: "B01AF02", name: "Apixaban", dose: "5 mg 1-0-1", change: "NEW" },
    { atc: "C07AB07", name: "Bisoprolol", dose: "5 mg 1-0-0", change: "NEW" },
    { atc: "C09AA05", name: "Ramipril", dose: "5 mg 1-0-0", change: "UNCHANGED" },
    { atc: "A02BC02", name: "Pantoprazol", change: "STOPPED", reason: "keine Indikation" },
  ],
  labs: [
    { loinc: "718-7", value: 13.2, unit: "g/dL" },
    { loinc: "2160-0", value: 0.9, unit: "mg/dL" },
    { loinc: "2823-3", value: 4.3, unit: "mmol/L" },
    { loinc: "3016-3", value: 1.8, unit: "mIU/L" },
    { loinc: "33762-6", value: 870, unit: "pg/mL" },
  ],
  flaggedAbnormal: [{ loinc: "33762-6", value: 870, ref: "<300", interpretation: "H" }],
};

// Role-based synthetic fixtures. No real identity or credential is represented.
export interface DemoAccount { id: string; name: string; role: import("./lib/role-rules").DemoRole; roleLabel: string; organisation: string; method: string; email?: string | undefined; hospitalRole?: "senior_doctor" | "doctor" | "it_admin" | undefined; permissions?: string[] | undefined }
export const DEMO_ACCOUNTS: DemoAccount[] = [
  { id: "anna", name: "Dr. Anna Huber", role: "hospital", roleLabel: "Senior Doctor", organisation: "Klinikum West", method: "Hospital account + security key", email: "anna.huber@klinikum-west.at", hospitalRole: "senior_doctor", permissions: ["release_letters"] },
  { id: "markus", name: "Dr. Markus Berger", role: "hospital", roleLabel: "Doctor", organisation: "Klinikum West", method: "Hospital account + security key", email: "markus.berger@klinikum-west.at", hospitalRole: "doctor", permissions: [] },
  { id: "thomas", name: "Thomas Gruber", role: "it_admin", roleLabel: "IT Admin", organisation: "Klinikum West", method: "Hospital account", email: "thomas.gruber@klinikum-west.at", hospitalRole: "it_admin", permissions: [] },
  { id: "petra", name: "Mag. Petra Novak", role: "hdab", roleLabel: "HDAB Staff", organisation: "Health Data Access Body", method: "ID Austria / authority account", email: "petra.novak@hdab.gv.at" },
  { id: "lena", name: "Dr. Lena Weiss", role: "interested", roleLabel: "Applicant", organisation: "University of Graz", method: "ID Austria", email: "lena.weiss@uni-graz.at" },
  { id: "visitor", name: "Public visitor", role: "visitor", roleLabel: "Visitor", organisation: "Public catalogue", method: "Browse without account" },
];
export const ROLE_PATIENTS = PATIENTS.map((p, i) => ({ ...p, id: i === 0 ? "p-4cfd3cf1" : p.id.toLowerCase(), legacyId: p.id, name: i === 0 ? "Frau M." : p.name, dataHolder: i === 0 ? "Klinikum West" : p.dataHolder, stays: i === 0 ? [{ ...ENCOUNTER }] : [] }));
export const ELGA_SECTIONS: import("./lib/letter-rules").ClinicalSection[] = [
  { key: "brieftext", title: "Letter narrative", items: [] },
  { key: "aufnahmegrund", title: "Reason for admission", required: true, items: [LETTER.course[0]].filter((i): i is LetterItem => !!i).map((i) => ({ text: i.text, source: "from KIS: progress note 20.10.2026", sourceText: NOTE_2010 })) },
  { key: "diagnosen", title: "Discharge diagnoses", required: true, items: LETTER.diagnoses.map((i) => ({ text: i.text, source: "from KIS: diagnosis 24.10.2026", sourceText: i.text })) },
  { key: "massnahmen", title: "Treatment provided", items: LETTER.course.slice(1, 3).map((i) => ({ text: i.text, source: "from KIS: treatment 20.10.2026", sourceText: i.text })) },
  { key: "medikation", title: "Recommended medication", required: true, items: LETTER.meds.map((i) => ({ text: `${i.name} · ATC ${i.atc} · ${i.dose}${i.note ? ` (${i.note})` : ""}`, status: i.change.toLowerCase(), source: "from KIS: medication 24.10.2026", sourceText: `${i.name}, ${i.atc}, ${i.dose}, ${i.change}${i.note ? ` – ${i.note}` : ""}` })) },
  { key: "weitere", title: "Follow-up and further care", required: true, items: [
    { text: `Appointments and follow-up: ${LETTER.recommendations[0]?.text ?? ""}`, source: "from KIS: progress note 24.10.2026", sourceText: NOTE_2410 },
    { text: `Condition at discharge: ${LETTER.course[4]?.text ?? ""}`, source: "from KIS: progress note 24.10.2026", sourceText: NOTE_2410 },
    { text: `Instructions for continuing care: ${LETTER.recommendations[1]?.text ?? ""}`, source: "from KIS: progress note 24.10.2026", sourceText: NOTE_2410 },
  ] },
  { key: "zusammenfassung", title: "Hospital stay summary", items: LETTER.course.map((i) => ({ text: i.text, source: "from KIS: stay 20.–24.10.2026", sourceText: i.highlight ?? i.text })) },
  { key: "allergien", title: "Allergies, intolerances and risks", recommended: true, items: LETTER.allergies.map((i) => ({ text: i.text, source: "from KIS: allergy record", sourceText: i.text })) },
  { key: "befunde", title: "Clinical findings", items: LETTER.labs.map((i) => ({ text: `${i.name}: ${i.value} ${i.unit} · ${i.date} · Reference ${i.ref}`, source: `from KIS: lab ${i.date}`, sourceText: `${i.name}, original value ${i.value} ${i.unit}, reference ${i.ref}, ${i.date}${i.flag ? `, ${i.flag}` : ""}`, ...(i.flag ? { tone: "abnormal" as const } : {}) })) },
  { key: "anamnese", title: "Medical history", items: [] },
  { key: "fruehere", title: "Previous conditions", items: [] },
  { key: "einweisung", title: "Medication on admission", items: [] },
  { key: "bemerkungen", title: "Closing remarks", items: [] },
];
export const HOSPITAL_REQUESTS = [
  { id: "R01", applicant: "Univ. Graz – Public Health", purpose: "Prevalence of type 2 diabetes", recordTypes: ["Diagnoses", "Medications", "Laboratory results"], patients: 742, hospital: "Klinikum West", approved: true, permitDate: "29.10.2026", kind: "Statistics" },
  { id: "R05", applicant: "TU Wien – AI in Medicine Lab", purpose: "Training a stroke-risk model", recordTypes: ["Diagnoses", "Medications", "Observations"], patients: 1184, hospital: "Klinikum West", approved: true, permitDate: "29.10.2026", kind: "Secure environment" },
];
export const HOSPITAL_DATASET = { ...DATASETS[0], holder: "Klinikum West", title: "Klinikum West – Inpatient & outpatient EHR extract", description: DATASETS[0]?.description ?? "", recordTypes: DATASETS[0]?.recordTypes ?? [] };
export const PUBLIC_USES = APPROVED_PROJECTS.map((p) => ({ date: "29.10.2026", organisation: p.org, purpose: p.title, type: p.kind, status: "Approved" }));
export const UNREGISTERED_FACILITIES = [
  { name: "Rehabilitation clinic", data: "Rehabilitation assessments, mobility and treatment outcomes" },
  { name: "GP network", data: "Primary care diagnoses, prescriptions and follow-up" },
  { name: "Nursing home group", data: "Care assessments, medication plans and care outcomes" },
];
export const ELIGIBILITY_PURPOSES = [
  { value: "research", label: "Scientific health research (Art. 53)" },
  { value: "public-health", label: "Public health and surveillance (Art. 53)" },
  { value: "policy", label: "Health policy and regulatory activities (Art. 53)" },
  { value: "education", label: "Health education (Art. 53)" },
  { value: "innovation", label: "Health innovation and algorithm evaluation (Art. 53)" },
  { value: "insurance", label: "Insurance premiums (prohibited, Art. 54)" },
  { value: "advertising", label: "Advertising (prohibited, Art. 54)" },
  { value: "employment", label: "Employment decisions (prohibited, Art. 54)" },
  { value: "weapons", label: "Weapons development (prohibited, Art. 54)" },
];
