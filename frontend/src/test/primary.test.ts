import { describe, it, expect } from "vitest";
import { decideAccess } from "@/lib/rules";
import { obxToObservation } from "@/lib/hl7";
import { ACCESS_SCENARIOS, HL7_ORU, PATIENTS } from "@/mockData";

const by = (id: string) => decideAccess(ACCESS_SCENARIOS.find((s) => s.id === id)!);

describe("primary-use access rules", () => {
  it("rule 1: non-authorised user is denied", () => expect([by("s5").decision, by("s5").rule]).toEqual(["DENY", 1]));
  it("rule 2: national doctor with treatment relationship is allowed", () => expect([by("s1").decision, by("s1").rule]).toEqual(["ALLOW", 2]));
  it("rule 3: Italian doctor with identity check and opt-in", () => expect([by("s2").decision, by("s2").rule]).toEqual(["ALLOW_CROSS_BORDER", 3]));
  it("rule 4: emergency with reason, no opt-in", () => expect([by("s4").decision, by("s4").rule]).toEqual(["ALLOW_EMERGENCY", 4]));
  it("rule 5: cross-border without opt-in and no emergency is denied", () => expect([by("s3").decision, by("s3").rule]).toEqual(["DENY", 5]));
  it("emergency without a reason is denied", () => {
    expect(decideAccess({ authorised: true, crossBorder: true, emergency: true, reason: " " }).decision).toBe("DENY");
  });
});

describe("HL7 v2 OBX-5 → FHIR Observation", () => {
  const o = obxToObservation(HL7_ORU, 5, "ENC-7731");
  it("maps code, value, range, flag, subject and encounter", () => {
    expect(o.code.coding[0]!.code).toBe("33762-6");
    expect(o.valueQuantity).toMatchObject({ value: 870, unit: "pg/mL" });
    expect(o.referenceRange[0]!.text).toBe("<300");
    expect(o.interpretation[0]!.coding[0]!.code).toBe("H");
    expect(o.subject.reference).toBe("Patient/P-00421");
    expect(o.encounter.reference).toBe("Encounter/ENC-7731");
    expect(o.effectiveDateTime).toBe("2026-10-21T07:00:00+02:00");
  });
});

describe("Frau M. profile", () => {
  const m = PATIENTS.find((p) => p.id === "P-00421")!;
  it("is Maria Muster, opted out of research but in for cross-border", () => {
    expect([m.name, m.born, m.optedOut, m.crossBorderOptIn]).toEqual(["Maria Muster", "1958-03-12", true, true]);
  });
});
