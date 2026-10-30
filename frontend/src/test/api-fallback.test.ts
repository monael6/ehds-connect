import { afterEach, describe, expect, it, vi } from "vitest";
import { requestApi } from "@/api";

afterEach(() => vi.unstubAllGlobals());
describe("FastAPI adapter demo fallbacks", () => {
  it("Labels simulated actions when the service is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Network failure")));
    expect(await requestApi("/test", { version: 2 }, { method: "PUT" })).toEqual({ data: { version: 2 }, source: "Synthetic fallback" });
  });
  it("Never converts an authorization refusal into synthetic success", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 403 })));
    await expect(requestApi("/test", { saved: true }, { method: "PUT" })).rejects.toThrow("Access refused");
  });
  it("Never converts a rejected live write into synthetic success", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 500 })));
    await expect(requestApi("/test", { saved: true }, { method: "PUT" })).rejects.toThrow("No changes were saved");
  });
});