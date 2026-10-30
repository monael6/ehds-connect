// Minimal HL7 v2 → FHIR R4 mapping (stands in for Mirth / Open Integration Engine).

export type Segment = string[];

export const segments = (msg: string): Segment[] => msg.split(/\r?\n/).filter(Boolean).map((l) => l.split("|"));

/** "20261021070000" → "2026-10-21T07:00:00+02:00" (Vienna, CEST in October). */
export function hl7Ts(ts: string): string {
  const m = /^(\d{4})(\d{2})(\d{2})(\d{2})?(\d{2})?(\d{2})?/.exec(ts);
  if (!m) return ts;
  return `${m[1]}-${m[2]}-${m[3]}T${m[4] ?? "00"}:${m[5] ?? "00"}:${m[6] ?? "00"}+02:00`;
}

/** Field → FHIR element mapping, in display order. `tone` picks a highlight colour. */
export const FIELD_MAP = [
  { hl7: "PID-3", seg: "PID", fields: [3], fhir: "subject", tone: 1 },
  { hl7: "OBX-3", seg: "OBX", fields: [3], fhir: "code", tone: 2 },
  { hl7: "OBX-5/6", seg: "OBX", fields: [5, 6], fhir: "valueQuantity", tone: 3 },
  { hl7: "OBX-7", seg: "OBX", fields: [7], fhir: "referenceRange", tone: 4 },
  { hl7: "OBX-8", seg: "OBX", fields: [8], fhir: "interpretation", tone: 5 },
  { hl7: "OBX-14", seg: "OBX", fields: [14], fhir: "effectiveDateTime", tone: 6 },
] as const;

const INTERP: Record<string, string> = { H: "High", L: "Low", N: "Normal" };

export function obxToObservation(msg: string, setId: number, encounterId: string) {
  const segs = segments(msg);
  const pid = segs.find((s) => s[0] === "PID");
  const obx = segs.find((s) => s[0] === "OBX" && s[1] === String(setId));
  if (!pid || !obx) throw new Error(`OBX|${setId} or PID not found`);
  const [code, display] = (obx[3] ?? "").split("^");
  const unit = obx[6] ?? "";
  const interp = obx[8] ?? "";
  return {
    resourceType: "Observation",
    id: `obs-${code}`,
    status: obx[11] === "F" ? "final" : "preliminary",
    code: { coding: [{ system: "http://loinc.org", code, display }] },
    subject: { reference: `Patient/${(pid[3] ?? "").split("^")[0]}` },
    encounter: { reference: `Encounter/${encounterId}` },
    effectiveDateTime: hl7Ts(obx[14] ?? ""),
    valueQuantity: { value: Number(obx[5]), unit, system: "http://unitsofmeasure.org", code: unit },
    referenceRange: [{ text: obx[7] ?? "" }],
    interpretation: [{ coding: [{ system: "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation", code: interp, display: INTERP[interp] ?? interp }] }],
  };
}

export function segmentLine(msg: string, seg: string, setId?: number): string {
  return msg.split(/\r?\n/).find((l) => l.startsWith(`${seg}|`) && (setId === undefined || l.split("|")[1] === String(setId))) ?? "";
}
