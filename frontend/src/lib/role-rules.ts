export type DemoRole = "hospital" | "hdab" | "interested" | "visitor";

/** Presentation boundaries for synthetic demo accounts; real authorisation belongs to FastAPI. */
export function canOpen(role: DemoRole | undefined, path: string): boolean {
  if (path === "/") return true;
  if (!role) return false;
  if (path === "/activity") return true;
  if (role === "hospital") return path === "/primary" || path === "/hospital";
  if (role === "hdab") return path.startsWith("/secondary") || path === "/audit";
  return path === "/secondary" || path === "/secondary/catalog" || path === "/secondary/register" || path === "/secondary/eligibility" || path === "/secondary/facilities";
}

export interface EligibilityInput {
  purpose: string; records: boolean; justification: string; qualified: boolean;
  safeguards: boolean; ethics: "approved" | "not-needed" | "pending";
}
export const PROHIBITED_PURPOSES = ["insurance", "advertising", "employment", "weapons"];
export function eligibility(a: EligibilityInput) {
  if (PROHIBITED_PURPOSES.includes(a.purpose)) return { allowed: false, label: "Not eligible – this purpose is not allowed (Art. 54)." };
  if (!a.purpose) return { allowed: false, label: "Not eligible – select a permitted purpose." };
  if (!a.qualified) return { allowed: false, label: "Not eligible – applicant qualification must be documented." };
  if (!a.safeguards) return { allowed: false, label: "Not eligible – safeguards must be documented." };
  if (a.ethics === "pending") return { allowed: false, label: "Not eligible yet – ethics review is pending." };
  if (a.records && !a.justification.trim()) return { allowed: false, label: "Not eligible – explain why anonymous statistics are not enough." };
  return { allowed: true, label: a.records ? "You can apply for a secure environment." : "You can apply for statistics." };
}