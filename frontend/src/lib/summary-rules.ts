import type { Patient } from "@/mockData";

/** Minimise the response before it reaches the cross-border view. */
export function releasedPatient(patient: Patient, emergency: boolean, hidden: readonly string[]): Patient {
  const visible = (section: string) => emergency || !hidden.includes(section);
  return {
    ...patient,
    problems: emergency ? [] : visible("problems") ? patient.problems : [],
    medications: !visible("medications") ? [] : emergency ? patient.medications.filter((m) => m.anticoagulant || m.code.startsWith("A10A")) : patient.medications,
    allergies: !visible("allergies") ? [] : emergency ? patient.allergies.filter((a) => a.severity === "high") : patient.allergies,
    implants: visible("implants") ? patient.implants : [],
    measurements: emergency || !visible("measurements") ? [] : patient.measurements,
  };
}