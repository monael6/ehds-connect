// Service layer. Each function mirrors a FastAPI endpoint and currently returns mock data.
// To go live: replace bodies with fetch(`${API_BASE}/api/...`).
import { PATIENTS, REQUESTS, TERMS, HL7_ORU, HL7_ADT, LETTER, SOURCES, IPS_VERSION, ENCOUNTER, PRIMARY_METRICS, REFERENCE_P00421, ROLE_PATIENTS, ELGA_SECTIONS, HOSPITAL_REQUESTS, HOSPITAL_DATASET, DATASETS, PUBLIC_USES, UNREGISTERED_FACILITIES, METRICS, type Lang, type Patient, type ResearchRequest, type AccessEntry } from "@/mockData";
import type { ClinicalSection } from "@/lib/letter-rules";
import { decide, decideAccess, type RuleOutcome, type AccessInput } from "@/lib/rules";
import { obxToObservation, segmentLine } from "@/lib/hl7";
import { releasedPatient } from "@/lib/summary-rules";
import { createDemoLetterDraft } from "@/lib/letter-draft";

export const API_BASE = import.meta.env["VITE_API_BASE"] ?? "http://localhost:8000";
export interface ApiResult<T> { data: T; source: "FastAPI" | "Synthetic fallback" }
/** Demo headers identify fixtures only; the FastAPI service must independently authenticate real users. */
export async function requestApi<T>(path: string, fallback: T, init?: RequestInit): Promise<ApiResult<T>> {
  try {
    const response = await fetch(`${API_BASE}${path}`, { ...init, headers: { "Content-Type": "application/json", ...init?.headers }, signal: AbortSignal.timeout(1500) });
    if (!response.ok) {
      if (response.status === 401 || response.status === 403) throw new Error("Access refused by the data service.");
      if (init?.method && init.method !== "GET") throw new Error("The data service rejected this action. No changes were saved.");
      throw new TypeError("Data service unavailable");
    }
    return { data: await response.json() as T, source: "FastAPI" };
  } catch (error) {
    if (error instanceof Error && !(error instanceof TypeError) && error.name !== "TimeoutError" && error.name !== "AbortError") throw error;
    return { data: fallback, source: "Synthetic fallback" };
  }
}
const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

export interface Evaluation extends RuleOutcome {
  request: ResearchRequest;
}

/** POST /api/requests/evaluate */
export async function evaluateRequest(req: ResearchRequest): Promise<Evaluation> {
  return (await requestApi("/api/requests/evaluate", { ...decide(req), request: req }, { method: "POST", body: JSON.stringify(req) })).data;
}

/** GET /api/patients/:id/ips?lang= */
export async function getPatientIps(id: string, lang: Lang = "en") {
  const p = ROLE_PATIENTS.find((x) => x.id === id || x.legacyId === id) ?? PATIENTS.find((x) => x.id === id);
  if (!p) throw new Error("Patient not found");
  return (await requestApi(`/api/patients/${encodeURIComponent(id)}/ips?lang=${lang}`, { patient: p, lang, bundle: buildFhirBundle(p, lang) })).data;
}

/** GET /api/audit-log — served from in-app state in this demo */
export async function getAuditLog(local: AccessEntry[]) {
  return local;
}

/** POST /api/spe/:id/download — always blocked */
export async function downloadSpe(id: string) {
  await delay(50);
  return { blocked: true as const, spe: id, message: "Download blocked – data never leaves the secure processing environment. This attempt has been logged." };
}

export const term = (code: string, lang: Lang) => TERMS[code]?.[lang] ?? code;

export function buildFhirBundle(p: Patient, lang: Lang = "en") {
  const pid = `Patient/${p.id}`;
  const entry: object[] = [
    { resource: { resourceType: "Composition", status: "final", type: { coding: [{ system: "http://loinc.org", code: "60591-5", display: "Patient summary Document" }] }, subject: { reference: pid }, title: "International Patient Summary" } },
    { resource: { resourceType: "Patient", id: p.id, gender: p.sex === "F" ? "female" : "male", address: [{ city: p.city, country: "AT" }] } },
    ...p.problems.map((c) => ({ resource: { resourceType: "Condition", subject: { reference: pid }, code: { coding: [{ system: "http://hl7.org/fhir/sid/icd-10", code: c.code, display: term(c.code, lang) }] }, onsetDateTime: c.since } })),
    ...p.medications.map((m) => ({ resource: { resourceType: "MedicationStatement", status: "active", subject: { reference: pid }, medicationCodeableConcept: { coding: [{ system: "http://www.whocc.no/atc", code: m.code, display: term(m.code, lang) }] }, dosage: [{ text: m.dose[lang] }] } })),
    ...p.allergies.map((a) => ({ resource: { resourceType: "AllergyIntolerance", patient: { reference: pid }, criticality: a.severity === "high" ? "high" : "low", code: { coding: [{ system: "http://snomed.info/sct", code: a.code, display: term(a.code, lang) }] } } })),
    ...p.measurements.map((o) => ({ resource: { resourceType: "Observation", status: "final", subject: { reference: pid }, code: { coding: [{ system: "http://loinc.org", code: o.code, display: term(o.code, lang) }] }, valueQuantity: { value: o.value, unit: o.unit }, effectiveDateTime: o.date } })),
  ];
  return { resourceType: "Bundle", type: "document", timestamp: "2026-10-29T12:00:00Z", entry };
}

export const getRequests = async () => (await requestApi("/api/requests", REQUESTS)).data;

// ---------- Primary use ----------

/** GET /api/kis/sources?patient= — raw HL7 v2 messages from the legacy KIS. */
export const getKisSources = async (_pid = "P-00421") => ({ oru: HL7_ORU, adt: HL7_ADT });

/** POST /api/integration/convert — HL7 v2 OBX → FHIR R4 Observation (Python mapping module in prod). */
export async function convertWithEngine(setId = 5) {
  await delay(1200);
  return { obx: segmentLine(HL7_ORU, "OBX", setId), pid: segmentLine(HL7_ORU, "PID"), observation: obxToObservation(HL7_ORU, setId, ENCOUNTER.id) };
}

/** POST /api/discharge-letter/draft */
export async function generateDischargeDraft(letter: LetterDocument): Promise<ApiResult<LetterDocument>> {
  // No AI-service request: patient-level data must remain inside this synthetic demo.
  await delay(600);
  return { data: createDemoLetterDraft(letter), source: "Synthetic fallback" };
}
export const getSource = (id: string) => SOURCES[id];

/** POST /api/patients/:id/ips — on-demand IPS */
export async function generateIps(id: string) {
  await delay(600);
  const p = ROLE_PATIENTS.find((p) => p.id === id) ?? PATIENTS.find((p) => p.id === id);
  if (!p) throw new Error("Patient not found");
  const response = await requestApi(`/api/patients/${encodeURIComponent(id)}/ips?lang=en`, { patient: p, bundle: buildFhirBundle(p, "en") });
  return { ...response.data, source: response.source, version: IPS_VERSION };
}

/** POST /api/access/evaluate */
export const evaluateAccess = (a: AccessInput) => decideAccess(a);
export const evaluateCrossBorderAccess = (a: AccessInput & { informed?: boolean }) => requestApi("/api/access/evaluate", decideAccess({ ...a, identityChecked: !!a.identityChecked && !!a.informed }), { method: "POST", body: JSON.stringify(a) });

/** GET /api/metrics/primary */
export const getPrimaryMetrics = async () => (await requestApi("/api/metrics/primary", { metrics: PRIMARY_METRICS, reference: REFERENCE_P00421 })).data;

export interface AuditEvent { id: string; userId: string; who: string; role: string; organisation: string; what: string; when: string; outcome: string; patient?: string; request?: string; area?: string }
export const writeAudit = async (event: AuditEvent) => { try { return await requestApi("/api/audit", event, { method: "POST", body: JSON.stringify(event) }); } catch { return { data: event, source: "Synthetic fallback" as const }; } };
export const readAudit = (fallback: AuditEvent[], userId?: string) => requestApi(`/api/audit${userId ? `?user_id=${encodeURIComponent(userId)}` : ""}`, fallback);
export const getRolePatients = () => requestApi("/api/patients", ROLE_PATIENTS);
export interface LetterEdit { id: string; version: number; who: string; role: string; when: string; section: string; key: string; before: string; after: string; reason: string; snapshot: Record<string, string> }
export interface LetterDocument { id: string; patient: string; sections: ClinicalSection[]; texts: Record<string, string>; edit_history: LetterEdit[]; version: number; status: "DRAFT" | "SIGNED"; signedAt?: string | undefined; signedBy?: string | undefined; supersedes?: number; generatedAt?: string; generationSource?: "Synthetic fallback" }
export const getClinicalLetter = (patient: string) => requestApi(`/api/discharge-letters/${encodeURIComponent(patient)}`, { id: patient, patient, sections: patient === "p-4cfd3cf1" ? ELGA_SECTIONS : ELGA_SECTIONS.map((s) => ({ ...s, items: [] })), texts: {}, edit_history: [], version: 1, status: "DRAFT" } as LetterDocument);
export const saveClinicalSection = (id: string, key: string, texts: string, editor: { name: string; role: string }, reason: string, fallback: LetterDocument) => requestApi(`/api/discharge-letters/${encodeURIComponent(id)}/sections/${encodeURIComponent(key)}`, fallback, { method: "PUT", body: JSON.stringify({ texts, editor, reason }) });
export const signClinicalLetter = (letter: LetterDocument, editor: { name: string; role: string }, code: string) => requestApi(`/api/discharge-letters/${encodeURIComponent(letter.id)}/sign`, letter, { method: "POST", body: JSON.stringify({ editor, second_factor: code, reviewed: true }) });
export const correctClinicalLetter = (letter: LetterDocument) => requestApi(`/api/discharge-letters/${encodeURIComponent(letter.id)}/corrections`, letter, { method: "POST", body: JSON.stringify({ version: letter.version }) });
export const sendClinicalLetter = (letter: LetterDocument) => requestApi(`/api/discharge-letters/${encodeURIComponent(letter.id)}/send`, { sent: true }, { method: "POST", body: JSON.stringify({ version: letter.version, destinations: ["ELGA", "GP"] }) });
export const getHospitalRequests = () => requestApi("/api/hospitals/klinikum-west/requests", HOSPITAL_REQUESTS);
export const provideHospitalData = (id: string, date: string) => requestApi(`/api/hospitals/klinikum-west/requests/${encodeURIComponent(id)}/provide`, { providedAt: date }, { method: "POST" });
export const getHospitalDataset = () => requestApi("/api/hospitals/klinikum-west/dataset", HOSPITAL_DATASET);
export const updateHospitalDataset = (description: string) => requestApi("/api/hospitals/klinikum-west/dataset", { ...HOSPITAL_DATASET, description }, { method: "PUT", body: JSON.stringify({ description }) });
export const getCatalogue = () => requestApi("/api/catalog", DATASETS);
export const getPublicUses = () => requestApi("/api/requests/public-register", PUBLIC_USES);
export const getUnregisteredFacilities = () => requestApi("/api/catalog/unregistered-facilities", UNREGISTERED_FACILITIES);
export const getSecondaryMetrics = () => requestApi("/api/metrics/secondary", METRICS);
export const recordPermitAction = (id: string, action: string, criteria: unknown) => requestApi(`/api/requests/${encodeURIComponent(id)}/decision`, { status: action }, { method: "POST", body: JSON.stringify({ action, criteria }) });
export const getOwnRequests = (userId: string) => requestApi(`/api/requests/mine?demo_user=${encodeURIComponent(userId)}`, [] as Evaluation[]);
export const saveCrossBorderConsent = (consent: { crossBorder: boolean; hidden: string[] }, date: string) => requestApi("/api/patients/p-4cfd3cf1/cross-border-consent", { ...consent, since: date }, { method: "PUT", body: JSON.stringify(consent) });

export async function getCrossBorderSummary(input: AccessInput & { informed?: boolean }, lang: Lang, hidden: string[]) {
  const result = await evaluateCrossBorderAccess(input);
  if (result.data.decision === "DENY") return null;
  const patient = ROLE_PATIENTS.find((p) => p.id === "p-4cfd3cf1");
  if (!patient) throw new Error("Patient not found");
  const emergency = result.data.decision === "ALLOW_EMERGENCY";
  const response = await requestApi("/api/patients/p-4cfd3cf1/cross-border-summary", { patient: releasedPatient(patient, emergency, hidden) }, { method: "POST", body: JSON.stringify({ ...input, lang, hidden, emergency }) });
  return { patient: releasedPatient(response.data.patient, emergency, hidden), source: response.source, sections: emergency ? ["emergency section"] : ["problems", "medications", "allergies", "implants", "measurements"].filter((s) => !hidden.includes(s)) };
}
