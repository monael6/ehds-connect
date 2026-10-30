import { describe, expect, it, vi, afterEach } from "vitest";
import { API_BASE, generateDischargeDraft, type LetterDocument } from "@/api";
import { ELGA_SECTIONS } from "@/mockData";
import { canSignLetter } from "@/lib/letter-rules";

const fixture = (sections = ELGA_SECTIONS): LetterDocument => ({ id: "p-4cfd3cf1", patient: "p-4cfd3cf1", sections, texts: {}, edit_history: [], version: 1, status: "DRAFT" });
afterEach(() => vi.unstubAllGlobals());
describe("Synthetic KIS draft creation", () => {
  it("Asks only the hospital backend for the KIS draft and otherwise assembles it locally", async () => {
    const fetch = vi.fn().mockRejectedValue(new TypeError("Network failure")); vi.stubGlobal("fetch", fetch);
    const result = await generateDischargeDraft(fixture());
    expect(fetch.mock.calls.map(([url]) => String(url))).toEqual([`${API_BASE}/api/discharge-letters`]);
    expect(result.source).toBe("Synthetic fallback");
    expect(result.data.version).toBe(2);
    expect(result.data.texts["diagnosen"]).toBe(ELGA_SECTIONS.find((s) => s.key === "diagnosen")?.items.map((i) => i.text).join("\n"));
    expect(result.data.texts["brieftext"]).toContain(result.data.texts["aufnahmegrund"]);
    expect(result.data.status).toBe("DRAFT");
  });
  it("Does not invent missing KIS data or bypass signing gates", async () => {
    const result = await generateDischargeDraft(fixture(ELGA_SECTIONS.map((s) => ({ ...s, items: [] }))));
    expect(Object.values(result.data.texts).every((text) => text === "")).toBe(true);
    expect(canSignLetter(result.data.sections, result.data.texts, true, "123456")).toBe(false);
  });
  it("Does not overwrite a signed or already generated letter", async () => {
    await expect(generateDischargeDraft({ ...fixture(), status: "SIGNED" })).rejects.toThrow("unsigned");
    await expect(generateDischargeDraft({ ...fixture(), generatedAt: "2026-10-30T00:00:00Z" })).rejects.toThrow("unedited");
  });
});