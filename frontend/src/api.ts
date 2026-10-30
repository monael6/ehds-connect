// Service layer. Each function calls the FastAPI backend and maps its answer to the UI's shapes (src/lib/backend-mappers.ts).
// Synthetic fixtures are used only when the service is unavailable, and are labelled as such.
import { PATIENTS, REQUESTS, TERMS, HL7_ORU, HL7_ADT, SOURCES, IPS_VERSION, ENCOUNTER, PRIMARY_METRICS, REFERENCE_P00421, ROLE_PATIENTS, ELGA_SECTIONS, HOSPITAL_REQUESTS, HOSPITAL_DATASET, DATASETS, PUBLIC_USES, UNREGISTERED_FACILITIES, METRICS, type Lang, type Patient, type ResearchRequest, type AccessEntry } from "@/mockData";
import type { ClinicalSection } from "@/lib/letter-rules";
import { decide, decideAccess, type RuleOutcome, type AccessInput, type AccessOutcome, type PrimaryDecision } from "@/lib/rules";
import { eligibility, type EligibilityInput } from "@/lib/role-rules";
import { obxToObservation, segmentLine } from "@/lib/hl7";
import { releasedPatient } from "@/lib/summary-rules";
import { createDemoLetterDraft } from "@/lib/letter-draft";
import {
  BACKEND_USERS, FOREIGN_DOCTOR_USER, FRAU_M, HOSPITAL, PATIENT_USER, currentLetter, emptyLetter, fromAccess, fromAudit, fromCatalogue, fromDecisionRow, fromEligibility, fromEvaluation,
  fromFacility, fromLetter, fromMetrics, fromPatientRow, fromPortal, fromProvision, fromRegister, fromSample, fromSummary, patientName, toAccessRequest, toBackendRequest, toConsent, toEligibility,
  type AccessDto, type AuditDto, type CatalogueDto, type DecisionRowDto, type EligibilityDto, type EligibilityOutcome, type EvaluationDto, type FacilityDto, type HospitalRequest, type LetterDto, type LetterRowDto,
  type MetricsDto, type PatientRowDto, type PortalDto, type ProvisionDto, type RegisterDto, type SampleDto, type SecondaryMetric, type SummaryDto,
} from "@/lib/backend-mappers";

export const API_BASE = import.meta.env["VITE_API_BASE"] ?? "http://localhost:8000";
export interface ApiResult<T> { data: T; source: "FastAPI" | "Synthetic fallback" }

// ---------- Session ----------
// The preset demo account signs in to the backend as the same person, so FastAPI authorises every call by role.
let token: string | null = null;
let session: Promise<void> = Promise.resolve();
let sessionId = 0;
const actorTokens = new Map<string, Promise<string | null>>();
async function loginAs(userId: string): Promise<SessionDto | null> {
  try {
    const response = await fetch(`${API_BASE}/api/auth/login`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ user_id: userId }), signal: AbortSignal.timeout(1500) });
    return response.ok ? ((await response.json()) as SessionDto) : null;
  } catch { return null; }
}
const login = async (userId: string) => (await loginAs(userId))?.token ?? null;
export interface BackendUser { id: string; name: string; email?: string | null; role: string; hospital_role?: string | null; hospital_role_label?: string | null; organisation: string; status?: string; permissions: string[]; sign_in_method?: string | null; keys?: SecurityKey[] }
export interface SessionDto { token: string; user: BackendUser }
/** Signs a preset demo account in; resolves with the backend user (null when the service is unavailable). */
export function startApiSession(accountId: string): Promise<BackendUser | null> {
  const id = ++sessionId; token = null; actorTokens.clear();
  const user = BACKEND_USERS[accountId];
  const started = user ? loginAs(user).then((s) => { if (id === sessionId) token = s?.token ?? null; return s?.user ?? null; }) : Promise.resolve(null);
  session = started.then(() => undefined);
  return started;
}
async function authPost<T>(path: string, body: unknown): Promise<T> {
  let response: Response;
  try { response = await fetch(`${API_BASE}${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), signal: AbortSignal.timeout(5000) }); }
  catch { throw new Error("The sign-in service is not reachable. Start the backend or use a demo account."); }
  if (!response.ok) throw new Error((await reason(response)).replace(/^ \(|\)$/g, "") || "Request failed");
  return (await response.json()) as T;
}
/** Email + password sign-in; the token is kept in memory only. */
export async function loginWithPassword(email: string, password: string): Promise<BackendUser> {
  const s = await authPost<SessionDto>("/api/auth/login", { email, password });
  ++sessionId; actorTokens.clear(); token = s.token; session = Promise.resolve();
  return s.user;
}
export interface RegistrationInput { name: string; email: string; password: string; category: string; role: string; organisation: string; hospital?: string }
export type RegistrationResult = { status: "pending"; message: string } | { status: "active"; user: BackendUser };
export async function registerAccount(input: RegistrationInput): Promise<RegistrationResult> {
  const r = await authPost<{ status: string; message?: string; token?: string; user: BackendUser }>("/api/auth/register", input);
  if (r.status === "active" && r.token) { ++sessionId; actorTokens.clear(); token = r.token; session = Promise.resolve(); return { status: "active", user: r.user }; }
  return { status: "pending", message: r.message ?? "Account created. Waiting for activation." };
}
export interface RegistrationCategory { category: string; label: string; description: string; roles: { id: string; label: string }[]; needs_activation: boolean; hospitals?: string[] }
export const getRegistrationOptions = async () => (await requestApi<RegistrationCategory[]>("/api/auth/registration-options", [])).data;
export function endApiSession() {
  const ended = token; sessionId++; token = null; session = Promise.resolve(); actorTokens.clear();
  if (ended) void fetch(`${API_BASE}/api/auth/logout`, { method: "POST", headers: { Authorization: `Bearer ${ended}` } }).catch(() => undefined);
}
/** Token for a person the walkthrough acts for (patient portal, doctor abroad); the backend checks their role as well. */
function actorToken(userId: string) {
  let t = actorTokens.get(userId);
  if (!t) { t = login(userId); actorTokens.set(userId, t); void t.then((v) => { if (!v) actorTokens.delete(userId); }); }
  return t;
}
async function reason(response: Response) {
  try {
    const detail = ((await response.json()) as { detail?: unknown }).detail;
    const text = typeof detail === "string" ? detail : (detail as { message?: string } | undefined)?.message;
    return text ? ` (${text})` : "";
  } catch { return ""; }
}

/** Demo headers identify fixtures only; the FastAPI service must independently authenticate real users. */
export async function requestApi<T>(path: string, fallback: T, init?: RequestInit, as?: string): Promise<ApiResult<T>> {
  try {
    await session;
    const auth = as ? await actorToken(as) : token;
    const response = await fetch(`${API_BASE}${path}`, { ...init, headers: { "Content-Type": "application/json", ...(auth ? { Authorization: `Bearer ${auth}` } : {}), ...init?.headers }, signal: init?.signal ?? AbortSignal.timeout(1500) });
    if (!response.ok) {
      if (response.status === 401 || response.status === 403) throw new Error("Access refused by the data service.");
      if (init?.method && init.method !== "GET") throw new Error(`The data service rejected this action. No changes were saved.${await reason(response)}`);
      throw new TypeError("Data service unavailable");
    }
    return { data: await response.json() as T, source: "FastAPI" };
  } catch (error) {
    if (error instanceof Error && !(error instanceof TypeError) && error.name !== "TimeoutError" && error.name !== "AbortError") throw error;
    return { data: fallback, source: "Synthetic fallback" };
  }
}
const UNAVAILABLE = Symbol("unavailable");
/** Calls FastAPI and maps its answer; the synthetic fixture is used only when the service is unavailable. */
async function live<D, T>(path: string, map: (dto: D) => T, fallback: T, init?: RequestInit, as?: string): Promise<ApiResult<T>> {
  const res = await requestApi<D | typeof UNAVAILABLE>(path, UNAVAILABLE, init, as);
  return res.data === UNAVAILABLE ? { data: fallback, source: "Synthetic fallback" } : { data: map(res.data as D), source: "FastAPI" };
}
const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

export interface ResultTable { columns: { key: string; label: string }[]; rows: { group: string; cells: (number | string | null)[] }[] }
export interface Evaluation extends RuleOutcome {
  request: ResearchRequest;
  staffNote?: string;
  // Only in answers from FastAPI:
  explanation?: Partial<Record<Lang, string>>;
  table?: ResultTable;
  spe?: { id: string; patients: number | string; recordTypes: string[]; idsKept: boolean };
  checklist?: { label: string; status: "pass" | "fail" | "pending"; reason: string }[];
  optedOutExcluded?: number;
  status?: string;
}

/** POST /api/requests/evaluate */
export async function evaluateRequest(req: ResearchRequest): Promise<Evaluation> {
  return (await live<EvaluationDto, Evaluation>("/api/requests/evaluate", (d) => fromEvaluation(d, req), { ...decide(req), request: req }, { method: "POST", body: JSON.stringify(toBackendRequest(req)) })).data;
}

/** GET /api/patients/:id/summary?lang= — Patient Summary built on demand from the KIS */
export async function getPatientIps(id: string, lang: Lang = "en") {
  const p = ROLE_PATIENTS.find((x) => x.id === id || x.legacyId === id) ?? PATIENTS.find((x) => x.id === id);
  const base = { name: p?.name ?? patientName(id), crossBorderOptIn: p?.crossBorderOptIn ?? false };
  const res = await live<SummaryDto, Patient | null>(`/api/patients/${encodeURIComponent(id)}/summary?lang=${lang}`, (s) => fromSummary(s, lang, base), p ?? null);
  if (!res.data) throw new Error("Patient not found");
  return { patient: res.data, lang, bundle: buildFhirBundle(res.data, lang), source: res.source };
}

export interface PatientDocument { id: string; date: string; type: string; specialty: string; author_role: string; facility: string; title: string; text: string }
/** GET /api/patients/:id/documents — clinical documents of the patient's record */
export const getPatientDocuments = (id: string) =>
  live<{ documents: PatientDocument[] }, PatientDocument[]>(`/api/patients/${encodeURIComponent(id)}/documents`, (d) => d.documents, []);

/** GET /api/audit-log — served from in-app state in this demo */
export async function getAuditLog(local: AccessEntry[]) {
  return local;
}

/** POST /api/spe/:id/download — always refused (403) and logged by the backend */
export async function downloadSpe(id: string) {
  const blocked = { blocked: true as const, spe: id, message: "Download blocked – data never leaves the secure processing environment. This attempt has been logged." };
  try {
    await session;
    const response = await fetch(`${API_BASE}/api/spe/${encodeURIComponent(id)}/download`, { method: "POST", headers: token ? { Authorization: `Bearer ${token}` } : {}, signal: AbortSignal.timeout(1500) });
    const body = (await response.json().catch(() => null)) as { detail?: { message?: string } } | null;
    return { ...blocked, message: body?.detail?.message ?? blocked.message };
  } catch {
    await delay(50);
    return blocked;
  }
}
export interface SpeAnalysis { note: string; cohort_size: number | string; observations?: { code: string; patients: number | string; mean: number | string | null }[] }
/** GET /api/spe/:id/analysis — aggregate output computed inside the SPE */
export const getSpeAnalysis = (id: string) => live<SpeAnalysis, SpeAnalysis | null>(`/api/spe/${encodeURIComponent(id)}/analysis`, (d) => d, null);

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

export const getRequests = async () => (await live<SampleDto[], ResearchRequest[]>("/api/requests/samples", (d) => d.map(fromSample), REQUESTS)).data;

// ---------- Primary use ----------

/** GET /api/kis/sources?patient= — raw HL7 v2 messages from the legacy KIS. */
export const getKisSources = async (_pid = "P-00421") => ({ oru: HL7_ORU, adt: HL7_ADT });

/** POST /api/integration/convert — HL7 v2 OBX → FHIR R4 Observation (Python mapping module in prod). */
export async function convertWithEngine(setId = 5) {
  await delay(1200);
  return { obx: segmentLine(HL7_ORU, "OBX", setId), pid: segmentLine(HL7_ORU, "PID"), observation: obxToObservation(HL7_ORU, setId, ENCOUNTER.id) };
}

/** POST /api/discharge-letters — draft assembled by the backend from KIS data (no AI) */
export async function generateDischargeDraft(letter: LetterDocument): Promise<ApiResult<LetterDocument>> {
  const res = await live<LetterDto, LetterDocument | null>("/api/discharge-letters", fromLetter, null, { method: "POST", body: JSON.stringify({ patient_id: letter.patient }) });
  if (res.data) return { data: res.data, source: "FastAPI" };
  // No AI-service request: patient-level data must remain inside this synthetic demo.
  await delay(600);
  return { data: createDemoLetterDraft(letter), source: "Synthetic fallback" };
}
export const getSource = (id: string) => SOURCES[id];

/** GET /api/patients/:id/summary — on-demand IPS */
export async function generateIps(id: string) {
  const res = await getPatientIps(id, "en");
  return { ...res, version: res.source === "FastAPI" ? `Generated ${new Date().toLocaleString("de-AT")} from KIS data` : IPS_VERSION };
}

/** POST /api/cross-border/check — access decision for the doctor abroad (rules 1–5); nothing is released yet */
export const evaluateAccess = (a: AccessInput) => decideAccess(a);
export const evaluateCrossBorderAccess = (a: AccessInput & { informed?: boolean }) => live<AccessDto, AccessOutcome>("/api/cross-border/check", fromAccess, decideAccess({ ...a, identityChecked: !!a.identityChecked && !!a.informed }), { method: "POST", body: JSON.stringify(toAccessRequest(a)) }, FOREIGN_DOCTOR_USER);

/** GET /api/metrics/primary */
export const getPrimaryMetrics = async () => (await requestApi("/api/metrics/primary", { metrics: PRIMARY_METRICS, reference: REFERENCE_P00421 })).data;

export interface AuditEvent { id: string; userId: string; who: string; role: string; organisation: string; what: string; when: string; outcome: string; patient?: string; request?: string; area?: string }
// The backend writes its own audit entry for every API call; demo-session events stay in the browser session.
export const writeAudit = async (event: AuditEvent): Promise<ApiResult<AuditEvent>> => ({ data: event, source: "Synthetic fallback" });
/** GET /api/audit (HDAB staff) or /api/audit/mine (own activity) */
export const readAudit = (fallback: AuditEvent[], userId?: string) => live<AuditDto[], AuditEvent[]>(userId ? "/api/audit/mine" : "/api/audit", (d) => d.map(fromAudit), fallback);
/** GET /api/patients — the hospital's own patients */
export const getRolePatients = () => live<PatientRowDto[], typeof ROLE_PATIENTS>("/api/patients", (rows) => rows.map(fromPatientRow), ROLE_PATIENTS);
export interface LetterEdit { id: string; version: number; who: string; role: string; when: string; section: string; key: string; before: string; after: string; reason: string; snapshot: Record<string, string> }
export interface LetterDocument { id: string; patient: string; sections: ClinicalSection[]; texts: Record<string, string>; edit_history: LetterEdit[]; version: number; status: "DRAFT" | "SIGNED"; signedAt?: string | undefined; signedBy?: string | undefined; supersedes?: number; generatedAt?: string; generationSource?: ApiResult<unknown>["source"]; stay?: string }
/** GET /api/discharge-letters?patient_id= — the current version, or an empty letter until a draft is created from the KIS */
export async function getClinicalLetter(patient: string): Promise<ApiResult<LetterDocument>> {
  const fallback: LetterDocument = { id: patient, patient, sections: patient === FRAU_M ? ELGA_SECTIONS : ELGA_SECTIONS.map((s) => ({ ...s, items: [] })), texts: {}, edit_history: [], version: 1, status: "DRAFT" };
  const rows = await live<LetterRowDto[], LetterRowDto[] | null>(`/api/discharge-letters?patient_id=${encodeURIComponent(patient)}`, (r) => r, null);
  if (!rows.data) return { data: fallback, source: "Synthetic fallback" };
  const current = currentLetter(rows.data);
  return current ? live<LetterDto, LetterDocument>(`/api/discharge-letters/${encodeURIComponent(current.id)}`, fromLetter, fallback) : { data: emptyLetter(patient), source: "FastAPI" };
}
/** PUT /api/discharge-letters/:id/sections/:key — the backend stores the edit with its reason */
export async function saveClinicalSection(id: string, key: string, texts: string, editor: { name: string; role: string }, reason: string, fallback: LetterDocument) {
  let letterId = id;
  if (id.startsWith("new:")) {
    const draft = await generateDischargeDraft(fallback);
    if (draft.source !== "FastAPI") return { data: fallback, source: draft.source };
    letterId = draft.data.id;
  }
  return live<LetterDto, LetterDocument>(`/api/discharge-letters/${encodeURIComponent(letterId)}/sections/${encodeURIComponent(key)}`, fromLetter, fallback, { method: "PUT", body: JSON.stringify({ text: texts, reason: reason || null }) });
}
/** POST /api/discharge-letters/:id/sign — confirmation and second factor are checked again by the backend */
export interface SignatureProof { key_id: string; challenge: string; signature?: string; assertion?: unknown }
export const signClinicalLetter = (letter: LetterDocument, proof: SignatureProof) => live<LetterDto, LetterDocument>(`/api/discharge-letters/${encodeURIComponent(letter.id)}/sign`, fromLetter, letter, { method: "POST", body: JSON.stringify({ confirmed: true, ...proof }) });
/** POST /api/discharge-letters/:id/correct — new draft version; the signed one is kept as superseded */
export const correctClinicalLetter = (letter: LetterDocument) => live<LetterDto, LetterDocument>(`/api/discharge-letters/${encodeURIComponent(letter.id)}/correct`, fromLetter, letter, { method: "POST" });
/** POST /api/discharge-letters/:id/send — only signed letters; ELGA and the GP are simulated */
export const sendClinicalLetter = (letter: LetterDocument) => live<unknown, { sent: boolean }>(`/api/discharge-letters/${encodeURIComponent(letter.id)}/send`, () => ({ sent: true }), { sent: true }, { method: "POST" });
/** GET /api/provisions — approved requests this hospital has to provide data for */
export const getHospitalRequests = () => live<ProvisionDto[], HospitalRequest[]>("/api/provisions", (rows) => rows.map(fromProvision), HOSPITAL_REQUESTS);
export const provideHospitalData = (id: string, date: string) => live<{ provided_at: string }, { providedAt: string }>(`/api/provisions/${encodeURIComponent(id)}/provide`, (d) => ({ providedAt: new Date(d.provided_at).toLocaleString("de-AT") }), { providedAt: date }, { method: "POST" });
/** GET /api/catalogue — this hospital's entry; PUT /api/catalogue/:data_holder updates its description */
export const getHospitalDataset = () => live<CatalogueDto[], typeof HOSPITAL_DATASET>("/api/catalogue", (d) => { const own = d.find((c) => c.data_holder === HOSPITAL); return own ? { ...HOSPITAL_DATASET, ...fromCatalogue(own) } : HOSPITAL_DATASET; }, HOSPITAL_DATASET);
export const updateHospitalDataset = (description: string) => live<CatalogueDto, typeof HOSPITAL_DATASET>(`/api/catalogue/${encodeURIComponent(HOSPITAL)}`, (c) => ({ ...HOSPITAL_DATASET, ...fromCatalogue(c) }), { ...HOSPITAL_DATASET, description }, { method: "PUT", body: JSON.stringify({ description }) });
export const getCatalogue = () => live<CatalogueDto[], typeof DATASETS>("/api/catalogue", (d) => d.map(fromCatalogue), DATASETS);
export const getPublicUses = () => live<RegisterDto[], typeof PUBLIC_USES>("/api/register", (d) => d.map(fromRegister), PUBLIC_USES);
export const getUnregisteredFacilities = () => live<FacilityDto[], typeof UNREGISTERED_FACILITIES>("/api/facilities-not-in-catalogue", (d) => d.map(fromFacility), UNREGISTERED_FACILITIES);
/** GET /api/metrics — the five Track-3 metrics measured on the 10 official requests (computed on first call) */
export const getSecondaryMetrics = () => live<MetricsDto, SecondaryMetric[]>("/api/metrics", fromMetrics, METRICS, { signal: AbortSignal.timeout(30000) });
/** POST /api/requests/:id/confirm or /ask-info — HDAB staff action on an automatic decision */
export const recordPermitAction = (id: string, action: string, criteria: unknown) => requestApi(`/api/requests/${encodeURIComponent(id)}/${action === "confirm" ? "confirm" : "ask-info"}`, { status: action }, { method: "POST", body: JSON.stringify({ note: JSON.stringify(criteria) }) });
/** HDAB staff decision on an applicant's request: approve, reject (reason required) or ask for more information */
export async function decideRequest(id: string, action: "confirm" | "reject" | "ask-info", note: string) {
  await strict(`/api/requests/${encodeURIComponent(id)}/${action}`, { method: "POST", body: JSON.stringify({ note: note || null }) });
}
export interface InboxRow { request_id: string; submitted_by: string | null; applicant: { name?: string; organisation?: string } | string | null; purpose: string | null; requested_as: string | null; decision: "REJECT" | "APPROVE_STATISTICAL" | "APPROVE_SPE"; articles: (string | number)[]; status: string; staff_note: string | null; created_at: string }
export const getRequestInbox = () => strict<InboxRow[]>("/api/requests");
export interface RequestDetail { request_id: string; decision: InboxRow["decision"]; articles: (string | number)[]; article_titles?: Record<string, string>; explanation?: Partial<Record<Lang, string>>; answer?: unknown; statistics?: { id?: string; label?: string; rows?: unknown[] }[]; spe?: { id: string; patient_count: number }; status: string; staff_note: string | null; results_released?: boolean; question?: string }
export const getRequestDetail = (id: string) => strict<RequestDetail>(`/api/requests/${encodeURIComponent(id)}`);
/** The applicant's guided request in the Track-3 request format; HDAB staff review it before results are released. */
export interface TrackRequest { id: string; applicant: { name: string; organisation: string; country: string }; requested_as: string; requested_format: string; purpose: string; question: string; definitions: string[]; why_not_statistics?: string; purpose_category?: string }
export const submitTrackRequest = (r: TrackRequest) => strict<RequestDetail>("/api/requests/evaluate", { method: "POST", body: JSON.stringify(r), signal: AbortSignal.timeout(30000) });

/** Calls FastAPI without a synthetic fallback: account, permission and signature actions must never be simulated. */
export async function strict<T>(path: string, init?: RequestInit): Promise<T> {
  await session;
  let response: Response;
  try { response = await fetch(`${API_BASE}${path}`, { ...init, headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...init?.headers }, signal: init?.signal ?? AbortSignal.timeout(5000) }); }
  catch { throw new Error("The backend is not reachable. Start it with: uvicorn app.main:app --port 8000"); }
  if (!response.ok) {
    let detail: unknown = null; try { detail = ((await response.json()) as { detail?: unknown }).detail; } catch { /* no body */ }
    const message = typeof detail === "string" ? detail : (detail as { message?: string } | null)?.message ?? `Request failed (${response.status})`;
    throw Object.assign(new Error(message), { status: response.status, detail });
  }
  return (await response.json()) as T;
}

// ---------- Hospital staff, permissions and security keys ----------
export interface SecurityKey { id: string; kind: "webauthn" | "software"; label: string; credential_id: string; status: "active" | "lost"; created_at: string; status_changed_at?: string | null }
export const getHospitalStaff = () => strict<BackendUser[]>("/api/hospital/staff");
export const activateAccount = (id: string) => strict<BackendUser>(`/api/admin/users/${encodeURIComponent(id)}/activate`, { method: "POST" });
export const setHospitalRole = (id: string, role: string) => strict<BackendUser>(`/api/admin/users/${encodeURIComponent(id)}/role`, { method: "PUT", body: JSON.stringify({ hospital_role: role }) });
export const grantRelease = (id: string) => strict<BackendUser>(`/api/hospital/staff/${encodeURIComponent(id)}/release-permission`, { method: "POST" });
export const revokeRelease = (id: string) => strict<BackendUser>(`/api/hospital/staff/${encodeURIComponent(id)}/release-permission`, { method: "DELETE" });
export const markKeyLostFor = (userId: string, keyId: string) => strict<SecurityKey>(`/api/admin/users/${encodeURIComponent(userId)}/keys/${encodeURIComponent(keyId)}/lost`, { method: "POST" });
export const issueRecoveryCode = (id: string) => strict<{ code: string; expires_at: string; note: string }>(`/api/admin/users/${encodeURIComponent(id)}/recovery-code`, { method: "POST", body: JSON.stringify({ identity_checked: true }) });
export const getMyKeys = () => strict<SecurityKey[]>("/api/security-keys");
export const getMe = () => strict<{ user: BackendUser }>("/api/me");
export const keyRegistrationOptions = (recoveryCode?: string) => strict<{ challenge: string; mode: string; webauthn: Record<string, unknown> }>("/api/security-keys/register/options", { method: "POST", body: JSON.stringify({ recovery_code: recoveryCode || null }) });
export const registerKey = (body: Record<string, unknown>) => strict<SecurityKey>("/api/security-keys", { method: "POST", body: JSON.stringify(body) });
export const reportKeyLost = (id: string) => strict<SecurityKey>(`/api/security-keys/${encodeURIComponent(id)}/lost`, { method: "POST" });
export const signChallenge = (letterId: string) => strict<{ challenge: string; keys: SecurityKey[]; webauthn: Record<string, unknown> | null }>(`/api/discharge-letters/${encodeURIComponent(letterId)}/sign/challenge`, { method: "POST" });
/** GET /api/requests — an applicant sees only their own requests */
export const getOwnRequests = (userId: string) => live<DecisionRowDto[], Evaluation[]>("/api/requests", (rows) => rows.map(fromDecisionRow), [] as Evaluation[]);
/** POST /api/eligibility — the backend's preliminary check; the local rules answer only when it is unavailable */
export const checkEligibility = (a: EligibilityInput, label: string) => live<EligibilityDto, EligibilityOutcome>("/api/eligibility", fromEligibility, { ...eligibility(a), records: a.records }, { method: "POST", body: JSON.stringify(toEligibility(a, label)) });
/** GET /api/portal/me — as Frau M.: her opt-out status from the KIS and the public register */
export const getPortal = () => live<PortalDto, ReturnType<typeof fromPortal>>("/api/portal/me", fromPortal, { patient: FRAU_M, optedOut: true, uses: PUBLIC_USES }, undefined, PATIENT_USER);
/** PUT /api/portal/consent — as Frau M. in her patient portal */
export const saveCrossBorderConsent = (consent: { crossBorder: boolean; hidden: string[] }, date: string) => live<unknown, { crossBorder: boolean; hidden: string[]; since: string }>("/api/portal/consent", () => ({ ...consent, since: date }), { ...consent, since: date }, { method: "PUT", body: JSON.stringify(toConsent(consent)) }, PATIENT_USER);

/** POST /api/cross-border/patient-summary — as the doctor in Italy; the backend decides again and releases only allowed sections */
export async function getCrossBorderSummary(input: AccessInput & { informed?: boolean }, lang: Lang, hidden: string[]) {
  const patient = ROLE_PATIENTS.find((p) => p.id === FRAU_M);
  if (!patient) throw new Error("Patient not found");
  const sections = (emergency: boolean, all = ["problems", "medications", "allergies", "measurements"]) => emergency ? ["emergency section"] : all.filter((s) => !hidden.includes(s));
  const res = await live<{ decision: PrimaryDecision; summary: SummaryDto | null }, { decision: PrimaryDecision; patient: Patient | null } | null>("/api/cross-border/patient-summary",
    (d) => ({ decision: d.decision, patient: d.summary ? fromSummary(d.summary, lang, { name: patient.name, crossBorderOptIn: true }) : null }), null,
    { method: "POST", body: JSON.stringify(toAccessRequest(input, lang)) }, FOREIGN_DOCTOR_USER);
  if (res.data) {
    const emergency = res.data.decision === "ALLOW_EMERGENCY";
    return res.data.patient ? { patient: releasedPatient(res.data.patient, emergency, hidden), source: res.source, sections: sections(emergency) } : null;
  }
  const result = decideAccess({ ...input, identityChecked: !!input.identityChecked && !!input.informed });
  if (result.decision === "DENY") return null;
  const emergency = result.decision === "ALLOW_EMERGENCY";
  return { patient: releasedPatient(patient, emergency, hidden), source: res.source, sections: sections(emergency, ["problems", "medications", "allergies", "implants", "measurements"]) };
}
