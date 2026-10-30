import { describe, expect, it } from "vitest";
import { toTables } from "@/components/secondary/request-result";

describe("toTables", () => {
  it("turns per-group answers into rows", () => {
    expect(toTables({ "Klinikum West": { patients: 281 }, "Klinikum Nord": { patients: "<10" } })).toEqual([["Result", [{ group: "Klinikum West", patients: 281 }, { group: "Klinikum Nord", patients: "<10" }]]]);
  });
  it("shows a flat answer as one row", () => {
    expect(toTables({ cohort_size: 1152 })).toEqual([["Result", [{ cohort_size: 1152 }]]]);
  });
  it("has no table for an empty answer", () => {
    expect(toTables({})).toEqual([]);
    expect(toTables(null)).toEqual([]);
  });
});
