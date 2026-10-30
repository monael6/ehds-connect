import type { Decision, RequestType } from "@/mockData";

export const SMALL_CELL = 10;

/** Small-cell rule: counts < 10 shown as "<10". */
export function formatCount(n: number): string {
  return n < SMALL_CELL ? "<10" : n.toLocaleString("en-US");
}

/** Percentages/means based on < 10 patients are suppressed; others rounded to one decimal. */
export function formatValue(n: number, value: number | undefined): string | null {
  if (n < SMALL_CELL || value === undefined) return null;
  return (Math.round(value * 10) / 10).toFixed(1);
}

const PROHIBITED = [
  { re: /insurance|premium/i, label: "setting insurance premiums" },
  { re: /advertis|marketing/i, label: "advertising or marketing to patients" },
  { re: /hiring|employment|job applicant/i, label: "decisions on employment" },
  { re: /weapon/i, label: "developing weapons" },
];

export interface RuleInput {
  type: RequestType;
  purpose: string;
  text?: string;
  whyNotStatistics?: string;
}

export interface RuleOutcome {
  decision: Decision;
  step: 1 | 2 | 3 | 4;
  articles: string[];
  prohibitedPurpose?: string;
}

/** EHDS decision order: prohibited → request → justified application → other application. */
export function decide(r: RuleInput): RuleOutcome {
  const hay = `${r.purpose} ${r.text ?? ""}`;
  const hit = PROHIBITED.find((p) => p.re.test(hay));
  if (hit) return { decision: "REJECT", step: 1, articles: ["Art. 54"], prohibitedPurpose: hit.label };
  if (r.type === "health data request") return { decision: "APPROVE_STATISTICAL", step: 2, articles: ["Art. 53", "Art. 69"] };
  if (r.whyNotStatistics && r.whyNotStatistics.trim().length > 0)
    return { decision: "APPROVE_SPE", step: 3, articles: ["Art. 53", "Art. 66", "Art. 68", "Art. 73"] };
  return { decision: "APPROVE_STATISTICAL", step: 4, articles: ["Art. 53", "Art. 66", "Art. 69"] };
}

// ---------- Primary use: access decision rules ----------

export interface AccessInput {
  authorised: boolean;
  crossBorder: boolean;
  treatmentRelationship?: boolean;
  identityChecked?: boolean;
  crossBorderOptIn?: boolean;
  emergency?: boolean;
  reason?: string;
}

export type PrimaryDecision = "DENY" | "ALLOW" | "ALLOW_CROSS_BORDER" | "ALLOW_EMERGENCY";

export interface AccessOutcome { decision: PrimaryDecision; rule: 1 | 2 | 3 | 4 | 5; explanation: string }

export const ACCESS_RULES = [
  { n: 1, text: "Requester is not an authorised health professional", result: "DENY" },
  { n: 2, text: "National request with treatment relationship", result: "ALLOW" },
  { n: 3, text: "Cross-border request, identity checked AND cross-border opt-in", result: "ALLOW_CROSS_BORDER" },
  { n: 4, text: "Cross-border without opt-in but emergency with reason", result: "ALLOW_EMERGENCY (emergency section only, logged, patient notified)" },
  { n: 5, text: "Anything else", result: "DENY with reason" },
] as const;

/** Primary-use access decision, evaluated strictly in rule order 1 → 5. */
export function decideAccess(a: AccessInput): AccessOutcome {
  if (!a.authorised) return { decision: "DENY", rule: 1, explanation: "Not an authorised health professional." };
  if (!a.crossBorder && a.treatmentRelationship) return { decision: "ALLOW", rule: 2, explanation: "National treatment relationship." };
  if (a.crossBorder && a.identityChecked && a.crossBorderOptIn) return { decision: "ALLOW_CROSS_BORDER", rule: 3, explanation: "Identity checked and patient opted in to cross-border access." };
  if (a.crossBorder && a.emergency && (a.reason ?? "").trim().length > 0) return { decision: "ALLOW_EMERGENCY", rule: 4, explanation: "Emergency with documented reason – emergency section only, patient notified." };
  const why = !a.crossBorder ? "no treatment relationship" : !a.identityChecked ? "identity not checked" : !a.crossBorderOptIn ? "patient has not opted in to cross-border access" : "emergency reason missing";
  return { decision: "DENY", rule: 5, explanation: `Denied: ${why}.` };
}
