import type { LetterDocument } from "@/api";

/** Synthetic demonstration only: source statements are assembled locally, never sent to AI. */
export function createDemoLetterDraft(letter: LetterDocument): LetterDocument {
  if (letter.status !== "DRAFT" || letter.edit_history.length > 0 || letter.generatedAt) {
    throw new Error("Draft creation is only available for an unedited, unsigned letter.");
  }
  const texts = Object.fromEntries(letter.sections.map((section) => [
    section.key, section.items.map((item) => item.text).join("\n"),
  ]));
  texts["brieftext"] = [texts["aufnahmegrund"], texts["massnahmen"], texts["zusammenfassung"], texts["weitere"]]
    .filter((text): text is string => Boolean(text?.trim()))
    .flatMap((text) => text.split("\n"))
    .filter((text, index, lines) => lines.indexOf(text) === index).join("\n\n");
  return { ...letter, texts, version: letter.version + 1, generatedAt: new Date().toISOString(), generationSource: "Synthetic fallback" };
}