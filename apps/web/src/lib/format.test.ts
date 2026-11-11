import { describe, expect, it } from "vitest";
import { buildQuery, toApiError } from "./api";
import {
  NOT_REPORTED,
  compactAmount,
  exactAmount,
  fixed2,
  groupDigits,
  money,
  priceBasis,
  ratioString,
  sourceText,
} from "./format";

describe("money formatting never invents values", () => {
  it("shows missing amounts as not reported, never zero", () => {
    expect(exactAmount(null)).toBe(NOT_REPORTED);
    expect(compactAmount(undefined)).toBe(NOT_REPORTED);
    expect(money(null, "USD")).toBe(NOT_REPORTED);
    expect(fixed2("")).toBe(NOT_REPORTED);
    expect(ratioString(null)).toBe("Not computable");
  });

  it("groups digits of exact decimal strings without float conversion", () => {
    expect(groupDigits("102852446551.65715952412")).toBe("102,852,446,551.65715952412");
    expect(groupDigits("-1234567")).toBe("-1,234,567");
    expect(exactAmount("21549925012.94")).toBe("21,549,925,012.94");
    expect(exactAmount("316574915.44000000")).toBe("316,574,915.44");
    expect(exactAmount("1000000.00")).toBe("1,000,000");
  });

  it("truncates display decimals, never rounds them up", () => {
    expect(exactAmount("0.999", 2)).toBe("0.99");
  });

  it("keeps the budget conservation figures exact", () => {
    expect(fixed2("1000000")).toBe("1,000,000.00");
    expect(fixed2("333333.34")).toBe("333,333.34");
    expect(fixed2("0.00")).toBe("0.00");
    expect(fixed2("12.345")).toBe("12.345");
  });

  it("states the currency, or says it is not stated", () => {
    expect(money("21549925012.94", "USD")).toBe("USD 21.5 billion"); // 3 significant figures; exact value in tooltips
    expect(money("5", null)).toBe("5 (currency not stated)");
  });

  it("names price bases in words", () => {
    expect(priceBasis("constant_2021_usd")).toBe("Constant 2021 USD");
    expect(priceBasis("unspecified")).toBe("Price basis not stated");
  });

  it("decodes source HTML entities for display only", () => {
    expect(sourceText("region&apos;s &amp; people")).toBe("region's & people");
    expect(sourceText(null)).toBe("");
  });
});

describe("API helpers", () => {
  it("drops empty query values", () => {
    expect(buildQuery({ q: "flood", country: "", page: 2, x: null, y: undefined })).toBe("?q=flood&page=2");
    expect(buildQuery({})).toBe("");
  });

  it("keeps the backend error code, message and Retry-After", () => {
    const e = toApiError(429, { code: "rate_limited", message: "At most 60" }, "12");
    expect(e.code).toBe("rate_limited");
    expect(e.message).toBe("At most 60");
    expect(e.retryAfter).toBe(12);
  });

  it("maps validation errors to their fields without echoing input", () => {
    const e = toApiError(
      422,
      { code: "invalid_request", message: "body.top_k: too big", detail: [{ loc: ["body", "top_k"], msg: "too big" }] },
      null,
    );
    expect(e.status).toBe(422);
    expect(e.fields).toEqual(["top_k"]);
  });

  it("treats 403 as an access refusal, not a crash", () => {
    const e = toApiError(403, { code: "source_rights_not_cleared", message: "No source" }, null);
    expect(e.forbidden).toBe(true);
    expect(e.unreachable).toBe(false);
  });

  it("handles a non-JSON error body", () => {
    const e = toApiError(500, null, null);
    expect(e.code).toBe("http_500");
  });
});
