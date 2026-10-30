import { describe, it, expect } from "vitest";
import { decide, formatCount, formatValue } from "@/lib/rules";
import { REQUESTS } from "@/mockData";

describe("small-cell rule", () => {
  it("counts below 10 show as <10", () => {
    expect(formatCount(9)).toBe("<10");
    expect(formatCount(0)).toBe("<10");
    expect(formatCount(10)).toBe("10");
  });
  it("values based on fewer than 10 patients are suppressed", () => {
    expect(formatValue(9, 55.5)).toBeNull();
    expect(formatValue(10, 52.38)).toBe("52.4");
  });
});

describe("decision order", () => {
  it("insurance purpose is rejected under Art. 54", () => {
    const o = decide({ type: "health data request", purpose: "set insurance premiums" });
    expect(o.decision).toBe("REJECT");
    expect(o.articles).toEqual(["Art. 54"]);
  });
  it("health data request gets statistics", () => {
    expect(decide({ type: "health data request", purpose: "prevalence" }).step).toBe(2);
  });
  it("justified access application gets SPE", () => {
    expect(decide({ type: "health data access application", purpose: "ML", whyNotStatistics: "need rows" }).decision).toBe("APPROVE_SPE");
  });
  it("unjustified access application falls back to statistics (step 4)", () => {
    const o = decide({ type: "health data access application", purpose: "describe" });
    expect([o.decision, o.step]).toEqual(["APPROVE_STATISTICAL", 4]);
  });
  it("R03 rejected and R05 is SPE", () => {
    const by = (id: string) => decide(REQUESTS.find((r) => r.id === id)!);
    expect(by("R03").decision).toBe("REJECT");
    expect(by("R05").decision).toBe("APPROVE_SPE");
  });
});
