import { describe, expect, it } from "vitest";
import { canOpen, eligibility } from "@/lib/role-rules";
import { missingRequired, canSignLetter, canSendLetter } from "@/lib/letter-rules";
import { validPatientIdentity } from "@/lib/identity-rules";
import { ELGA_SECTIONS, ROLE_PATIENTS, HOSPITAL_REQUESTS } from "@/mockData";
import { releasedPatient } from "@/lib/summary-rules";

describe("Role boundaries", () => {
  it("Hospital can use primary care and its approved inbox only", () => {
    expect(canOpen("hospital", "/primary")).toBe(true);
    expect(canOpen("hospital", "/hospital")).toBe(true);
    expect(canOpen("hospital", "/secondary")).toBe(false);
    expect(canOpen("hospital", "/audit")).toBe(false);
  });
  it("Hospital IT admin manages accounts only and sees no patients", () => {
    expect(canOpen("it_admin", "/admin")).toBe(true);
    expect(canOpen("it_admin", "/primary")).toBe(false);
    expect(canOpen("it_admin", "/secondary")).toBe(false);
  });
  it("HDAB can use secondary tools and audit but not primary", () => {
    expect(canOpen("hdab", "/secondary/metrics")).toBe(true);
    expect(canOpen("hdab", "/audit")).toBe(true);
    expect(canOpen("hdab", "/primary")).toBe(false);
  });
  it("Interested parties cannot see staff metrics, patient rights or audit", () => {
    expect(canOpen("interested", "/secondary/catalog")).toBe(true);
    expect(canOpen("interested", "/secondary/metrics")).toBe(false);
    expect(canOpen("interested", "/secondary/rights")).toBe(false);
    expect(canOpen("interested", "/audit")).toBe(false);
  });
  it("Signed-out users have no data area access", () => expect(canOpen(undefined, "/primary")).toBe(false));
  it("Ms M. is listed first under the requested pseudonym", () => expect(ROLE_PATIENTS[0]?.id).toBe("p-4cfd3cf1"));
  it("Hospital fixture includes only approved Klinikum West requests", () => expect(HOSPITAL_REQUESTS.every((r) => r.approved && r.hospital === "Klinikum West")).toBe(true));
});
describe("Clinical safeguards", () => {
  it("Emergency release excludes full clinical records and retains critical medication", () => {
    const patient = ROLE_PATIENTS[0];
    if (!patient) throw new Error("Missing fixture");
    const release = releasedPatient(patient, true, []);
    expect(release.problems).toEqual([]);
    expect(release.measurements).toEqual([]);
    expect(release.medications.map((m) => m.code)).toEqual(["B01AF02"]);
    expect(releasedPatient(patient, false, ["medications", "allergies"]).medications).toEqual([]);
    expect(releasedPatient(patient, false, ["medications", "allergies"]).allergies).toEqual([]);
  });
  it("Empty required sections block signing", () => {
    expect(missingRequired(ELGA_SECTIONS, { aufnahmegrund: "" })).toEqual([ELGA_SECTIONS.find((section) => section.key === "aufnahmegrund")?.title]);
    expect(canSignLetter(ELGA_SECTIONS, { aufnahmegrund: "" }, true, true)).toBe(false);
  });
  it("Signing requires acknowledgement and exactly six factor digits", () => {
    expect(canSignLetter(ELGA_SECTIONS, {}, true, true)).toBe(true);
    expect(canSignLetter(ELGA_SECTIONS, {}, false, true)).toBe(false);
    expect(canSignLetter(ELGA_SECTIONS, {}, true, false)).toBe(false);
  });
  it("Only signed letters can be sent", () => {
    expect(canSendLetter("DRAFT")).toBe(false);
    expect(canSendLetter("SIGNED")).toBe(true);
  });
  it("ID Austria requires eight digits and checked matching identity plus agreement", () => {
    expect(validPatientIdentity("austria-code", "12345678", "Maria Muster", "1943-03-17", true, true)).toBe(true);
    expect(validPatientIdentity("austria-code", "1234567", "Maria Muster", "1943-03-17", true, true)).toBe(false);
    expect(validPatientIdentity("passport", "P123", "Other person", "1943-03-17", true, true)).toBe(false);
    expect(validPatientIdentity("passport", "P123", "Maria Muster", "1943-03-17", true, false)).toBe(false);
  });
});
describe("Eligibility self-check", () => {
  const input = { purpose: "research", records: false, justification: "", qualified: true, safeguards: true, ethics: "not-needed" as const };
  it("Prohibited Art. 54 purposes cannot apply", () => {
    for (const purpose of ["insurance", "advertising", "employment", "weapons"]) expect(eligibility({ ...input, purpose }).allowed).toBe(false);
  });
  it("Records require a reason why statistics are insufficient", () => {
    expect(eligibility({ ...input, records: true }).allowed).toBe(false);
    expect(eligibility({ ...input, records: true, justification: "Individual longitudinal sequences are needed" }).allowed).toBe(true);
  });
  it("Qualification, safeguards and ethics review are required", () => {
    expect(eligibility(input).allowed).toBe(true);
    expect(eligibility({ ...input, qualified: false }).allowed).toBe(false);
    expect(eligibility({ ...input, safeguards: false }).allowed).toBe(false);
    expect(eligibility({ ...input, ethics: "pending" }).allowed).toBe(false);
  });
});