export interface ClinicalSection {
  key: string; title: string; required?: boolean; recommended?: boolean;
  items: { text: string; source: string; sourceText: string; tone?: "abnormal"; status?: string }[];
}
export function missingRequired(sections: ClinicalSection[], overrides: Record<string, string>) {
  return sections.filter((s) => s.required && !(overrides[s.key] ?? s.items.map((i) => i.text).join("\n")).trim()).map((s) => s.title);
}
/** Signing needs the release permission (senior doctor or authorised doctor); the backend checks it again. */
export function canSignLetter(sections: ClinicalSection[], overrides: Record<string, string>, acknowledged: boolean, canRelease: boolean) {
  return acknowledged && canRelease && missingRequired(sections, overrides).length === 0;
}
export function canSendLetter(status: string) { return status === "SIGNED"; }