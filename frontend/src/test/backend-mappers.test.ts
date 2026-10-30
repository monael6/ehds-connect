import { afterEach, describe, expect, it, vi } from "vitest";
import { API_BASE, downloadSpe, endApiSession, getCatalogue, requestApi, startApiSession } from "@/api";
import { DATASETS, TERMS } from "@/mockData";
import { fromDecisionRow, fromEligibility, fromEvaluation, fromLetter, fromPortal, fromSample, fromSummary, toBackendRequest, toConsent, toEligibility, type EvaluationDto, type LetterDto } from "@/lib/backend-mappers";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => { endApiSession(); vi.unstubAllGlobals(); });

describe("Research requests to and from the backend", () => {
  it("Sends the original Track-3 request, or builds one from the form without dropping definitions", () => {
    const raw = { id: "R08", requested_as: "health data request", purpose: "BMI study", question: "Mean BMI of women?", definitions: ["Women = sex female."] };
    const sample = fromSample({ id: "R08", applicant: { name: "Dr. X", organisation: "MedUni" }, purpose: "BMI study", requested_as: "health data request", request: raw });
    expect(sample).toMatchObject({ applicant: "MedUni", type: "health data request", text: "Mean BMI of women?" });
    expect(toBackendRequest(sample)).toBe(raw);
    const form = { id: "A1", applicant: "University of Graz", purpose: "Model training", type: "health data access application" as const, text: "Records of adults with diabetes", whyNotStatistics: "Individual histories", terms: [], sql: "", definitions: ["Adult = aged 18 or older."] };
    expect(toBackendRequest(form)).toEqual({ id: "A1", purpose: "Model training", definitions: ["Adult = aged 18 or older."], applicant: { organisation: "University of Graz" }, requested_as: "health data access application", question: "Records of adults with diabetes", why_not_statistics: "Individual histories" });
  });

  it("Shows the backend's decision, protected figures, checklist and generated SQL", () => {
    const dto: EvaluationDto = {
      request_id: "R08", decision: "APPROVE_STATISTICAL", matched_step: 2, articles: [53, 69], explanation: { en: "Approved.", de: "Genehmigt." }, opted_out_excluded: 839,
      statistics: [
        { id: "women", label: "women with a BMI", kind: "count", groups: [{ group: { region: "Burgenland" }, value: "<10" }, { group: { region: "Wien" }, value: 14 }] },
        { id: "mean_bmi", label: "mean BMI", kind: "mean", groups: [{ group: { region: "Burgenland" }, value: "suppressed" }, { group: { region: "Wien" }, value: 26.6 }] },
      ],
      permit_checklist: [{ label: "Not a prohibited purpose (Art. 54)", status: "yes", reason: "None found." }, { label: "Ethics review", status: "check", reason: "Staff check." }],
      staff: { term_mapping: [{ term: "bmi", system: "LOINC", codes: ["39156-5"] }], sql: [{ metric: "women", sql: "SELECT 1" }] },
    };
    const ev = fromEvaluation(dto, { id: "R08", applicant: "MedUni", purpose: "BMI", type: "health data request", text: "", terms: [], sql: "" });
    expect(ev.articles).toEqual(["Art. 53", "Art. 69"]);
    expect(ev.table?.columns.map((c) => c.label)).toEqual(["Women with a BMI", "Mean BMI"]);
    expect(ev.table?.rows).toEqual([{ group: "Burgenland", cells: ["<10", "suppressed"] }, { group: "Wien", cells: [14, 26.6] }]);
    expect(ev.checklist?.map((c) => c.status)).toEqual(["pass", "pending"]);
    expect(ev.request.terms).toEqual([{ term: "bmi", system: "LOINC", codes: "39156-5", found: true }]);
    expect(ev.request.sql).toBe("-- women\nSELECT 1");
    expect(ev.optedOutExcluded).toBe(839);
  });

  it("Asks the backend's eligibility check with an unambiguous purpose and keeps its answer", () => {
    const a = { purpose: "research", records: true, justification: "We train a model.", qualified: true, safeguards: true, ethics: "approved" as const };
    expect(toEligibility(a, "Scientific health research (Art. 53)")).toEqual({ purpose: "Scientific health research (Art. 53)", purpose_code: "research", need: "records", why_not_statistics: "We train a model.", qualified: true, safeguards: true, ethics: true });
    expect(toEligibility({ ...a, purpose: "insurance", ethics: "pending" }, "Insurance premiums")).toMatchObject({ purpose_code: "prohibited", ethics: false });
    expect(fromEligibility({ result: "statistics", reason: "Apply for statistics." })).toEqual({ allowed: true, records: false, label: "Apply for statistics." });
    expect(fromEligibility({ result: "not_eligible", reason: "Prohibited purpose (Art. 54): insurance premiums" })).toEqual({ allowed: false, label: "Not eligible – Prohibited purpose (Art. 54): insurance premiums" });
  });

  it("Shows the HDAB's current status on the applicant's own requests and in the patient's register", () => {
    expect(fromDecisionRow({ request_id: "A1", decision: "APPROVE_SPE", articles: [53, 68], status: "more_information_requested" })).toMatchObject({ step: 3, articles: ["Art. 53", "Art. 68"], status: "The HDAB asked for more information" });
    expect(fromPortal({ patient_id: "p-4cfd3cf1", opted_out_of_secondary_use: true, approved_research: [{ date: "2026-10-30", applicant_organisation: "MedUni", purpose: "BMI", type: "statistics", status: "automatic" }] }))
      .toEqual({ patient: "p-4cfd3cf1", optedOut: true, uses: [{ date: new Date("2026-10-30").toLocaleDateString("de-AT"), organisation: "MedUni", purpose: "BMI", type: "Statistics", status: "Approved (automatic decision)" }] });
  });

  it("Names the prohibited purpose of a rejected request", () => {
    const ev = fromEvaluation({ request_id: "R02", decision: "REJECT", matched_step: 1, articles: [54], prohibited_purposes: [{ purpose: "insurance premiums" }] }, { id: "R02", applicant: "", purpose: "", type: "health data request", text: "", terms: [], sql: "" });
    expect(ev).toMatchObject({ decision: "REJECT", step: 1, articles: ["Art. 54"], prohibitedPurpose: "insurance premiums" });
    expect(ev.table).toBeUndefined();
  });
});

describe("Clinical data from the backend", () => {
  it("Keeps KIS statements, edits with versions and snapshots, and the real stay", () => {
    const dto: LetterDto = {
      id: "L-1", patient_id: "p-4cfd3cf1", version: 1, status: "draft", supersedes: null, signed_by: null, signed_at: null, created_at: "2026-10-30T01:00:00+00:00",
      content: { header: { hospital: "Klinikum West", stay: { from: "2025-01-15", to: "2025-01-27" } }, sections: [
        { key: "aufnahmegrund", heading: "Aufnahmegrund", required: true, items: [{ text: "Aufnahme mit I48.2", source: "KIS: Aufenthalt" }], text: "", last_edited_by: null },
        { key: "empfehlungen", heading: "Weitere empfohlene Maßnahmen", required: true, items: [], text: "Kontrolle in 4 Wochen", last_edited_by: { name: "Dr. Anna Huber", at: "x" } },
      ] },
      edit_history: [{ id: 7, section: "empfehlungen", before: JSON.stringify({ text: "No data in the KIS – please complete", items: [] }), after: JSON.stringify({ text: "Kontrolle in 4 Wochen", items: [] }), reason: "follow-up", editor_name: "Dr. Anna Huber", ts: "2026-10-30T01:05:00+00:00" }],
    };
    const doc = fromLetter(dto);
    expect(doc.sections.map((s) => [s.key, s.title, s.required])).toEqual([["aufnahmegrund", "Reason for admission", true], ["empfehlungen", "Follow-up and further care", true]]);
    expect(doc.texts).toEqual({ empfehlungen: "Kontrolle in 4 Wochen" });
    expect(doc.version).toBe(2);
    expect(doc.edit_history[0]).toMatchObject({ version: 2, key: "empfehlungen", before: "", after: "Kontrolle in 4 Wochen", reason: "follow-up", snapshot: { aufnahmegrund: "Aufnahme mit I48.2", empfehlungen: "" } });
    expect(doc.status).toBe("DRAFT");
    expect(doc.stay).toBe(`Stay: ${new Date("2025-01-15").toLocaleDateString("de-AT")} – ${new Date("2025-01-27").toLocaleDateString("de-AT")}`);
  });

  it("Uses the backend's translated labels and emergency selection", () => {
    const p = fromSummary({
      patient: { id: "p-4cfd3cf1", sex: "female", birth_date: "1943-03-17", age: 82, region: "Vorarlberg", data_holder: "Klinikum West", opted_out_of_secondary_use: true },
      emergency: [{ type: "medication", code: "B01AF02", text: "Apixaban: anticoagulante" }],
      problems: [{ code: "I48.2", label: "Fibrillazione atriale cronica", since: "1995-06-03" }],
      medications: [{ code: "B01AF02", label: "Apixaban", dose: null }],
      allergies: { items: [] },
    }, "it", { name: "Ms M.", crossBorderOptIn: true });
    expect(TERMS["I48.2"]?.it).toBe("Fibrillazione atriale cronica");
    expect(p.medications[0]).toMatchObject({ code: "B01AF02", anticoagulant: true });
    expect(p.emergency).toEqual([{ type: "medication", code: "B01AF02", text: "Apixaban: anticoagulante" }]);
    expect(p).toMatchObject({ name: "Ms M.", sex: "F", optedOut: true, allergies: [], implants: [] });
  });

  it("Stores the portal consent with the backend's section names", () => {
    expect(toConsent({ crossBorder: true, hidden: ["measurements", "implants"] })).toEqual({ allow_cross_border: true, hidden_sections: ["results"] });
  });
});

describe("Session and live calls", () => {
  it("Signs the demo account in and sends its token with every call", async () => {
    const fetch = vi.fn().mockResolvedValueOnce(json({ token: "t-novak" })).mockResolvedValue(json([]));
    vi.stubGlobal("fetch", fetch);
    await startApiSession("petra");
    await requestApi("/api/requests", []);
    expect(JSON.parse(String(fetch.mock.calls[0]?.[1]?.body))).toEqual({ user_id: "u-novak" });
    expect(fetch.mock.calls[1]?.[0]).toBe(`${API_BASE}/api/requests`);
    expect(fetch.mock.calls[1]?.[1]?.headers).toMatchObject({ Authorization: "Bearer t-novak" });
  });

  it("Maps live answers and labels fixtures only when the service is down", async () => {
    expect(await getCatalogue()).toEqual({ data: DATASETS, source: "Synthetic fallback" });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json([{ data_holder: "Klinikum West", title: "Clinical records", description: "d", patients_rounded: 6800, time_range: { start: "2023-01-01", end: "2025-12-31" }, record_types: ["conditions"] }])));
    expect(await getCatalogue()).toEqual({ data: [{ holder: "Klinikum West", title: "Clinical records", description: "d", from: "2023-01", to: "2025-12", recordTypes: ["conditions"], patients: 6800 }], source: "FastAPI" });
  });

  it("Shows the backend's refusal when a download from the secure environment is attempted", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ detail: { blocked: true, message: "Download blocked – logged by the HDAB." } }, 403)));
    expect(await downloadSpe("SPE-R05")).toEqual({ blocked: true, spe: "SPE-R05", message: "Download blocked – logged by the HDAB." });
  });
});
