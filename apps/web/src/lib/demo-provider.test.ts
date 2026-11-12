import { describe, expect, it } from "vitest";
import { demoRequest } from "./demo-provider";
import type { ProjectPage, ScreeningResponse } from "./api-types";
describe("self-contained synthetic provider", () => {
  it("combines filters, paginates and handles no matches", () => {
    const page = demoRequest("/api/v1/projects?country=PAK&q=water&page_size=1") as ProjectPage;
    expect(page.items).toHaveLength(1);
    expect(page.items[0].id).toBe("pak-water");
    expect((demoRequest("/api/v1/projects?q=nonexistent") as ProjectPage).items).toEqual([]);
  });
  it("returns deterministic illustrative screening without model artifacts", () => {
    const result = demoRequest("/api/v1/screening/text", {description:"solar"}) as ScreeningResponse;
    expect(result).toEqual(demoRequest("/api/v1/screening/text", {description:"solar"}));
    expect(result.model.artifact_present).toBe(false);
    expect(result.prediction.score_semantics).toContain("not ML v2 inference");
  });
});
