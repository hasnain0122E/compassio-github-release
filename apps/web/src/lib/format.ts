/**
 * Display formatting. Money arrives as exact decimal STRINGS from the backend and is never
 * summed, converted or rounded for anything but display here. A missing value is never zero.
 */

export const NOT_REPORTED = "Not reported";

/** Group the integer digits of an exact decimal string without converting it to a float. */
export function groupDigits(amount: string): string {
  const negative = amount.startsWith("-");
  const body = negative ? amount.slice(1) : amount;
  const [intPart, frac] = body.split(".");
  const grouped = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `${negative ? "-" : ""}${grouped}${frac ? `.${frac}` : ""}`;
}

/** Exact value, with at most `decimals` fractional digits shown (truncated, never rounded up). */
export function exactAmount(amount: string | null | undefined, decimals = 2): string {
  if (amount === null || amount === undefined || amount === "") return NOT_REPORTED;
  const [intPart, frac = ""] = amount.split(".");
  const kept = frac.slice(0, decimals).replace(/0+$/, "");
  return groupDigits(kept ? `${intPart}.${kept}` : intPart);
}

const SCALES: Array<[number, string]> = [
  [1e12, "trillion"],
  [1e9, "billion"],
  [1e6, "million"],
  [1e3, "thousand"],
];

/** Compact display ("21.55 billion"). Uses a float ONLY to choose display digits. */
export function compactAmount(amount: string | null | undefined): string {
  if (amount === null || amount === undefined || amount === "") return NOT_REPORTED;
  const value = Number(amount);
  if (!Number.isFinite(value)) return amount;
  const abs = Math.abs(value);
  for (const [scale, word] of SCALES) {
    if (abs >= scale) {
      const scaled = value / scale;
      const digits = Math.abs(scaled) >= 100 ? 0 : Math.abs(scaled) >= 10 ? 1 : 2;
      return `${scaled.toFixed(digits)} ${word}`;
    }
  }
  return exactAmount(amount);
}

/** "USD 21.55 billion", "Amount in units, currency not stated" etc. */
export function money(
  amount: string | null | undefined,
  currency: string | null | undefined,
  opts: { compact?: boolean } = {},
): string {
  if (amount === null || amount === undefined || amount === "") return NOT_REPORTED;
  const shown = opts.compact === false ? exactAmount(amount) : compactAmount(amount);
  return currency ? `${currency} ${shown}` : `${shown} (currency not stated)`;
}

export function integer(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return value.toLocaleString("en-US");
}

export function percent(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

/** Ratio given as a decimal string (backend), e.g. "0.3479" -> "34.8%". */
export function ratioString(value: string | null | undefined): string {
  if (value === null || value === undefined) return "Not computable";
  return percent(Number(value));
}

export function humanize(code: string | null | undefined): string {
  if (!code) return "";
  const text = code.replace(/[_|]+/g, " ").trim();
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function priceBasis(basis: string): string {
  if (basis === "constant_2021_usd") return "Constant 2021 USD";
  if (basis === "nominal") return "Nominal";
  if (basis === "unspecified") return "Price basis not stated";
  return humanize(basis);
}

export function dateOnly(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString("en-GB", { dateStyle: "medium" });
}

/** Two fixed decimals for budget arithmetic display (exact string, no float). */
export function fixed2(amount: string | null | undefined): string {
  if (amount === null || amount === undefined || amount === "") return NOT_REPORTED;
  const [intPart, frac = ""] = amount.split(".");
  // Never hide significant digits: keep any non-zero digits beyond the second decimal.
  const kept = /[1-9]/.test(frac.slice(2)) ? frac.replace(/0+$/, "") : (frac + "00").slice(0, 2);
  return groupDigits(`${intPart}.${kept}`);
}

/** Decode the HTML entities some sources leave in text (display only; data is unchanged). */
export function sourceText(text: string | null | undefined): string {
  if (!text) return "";
  return text
    .replace(/&apos;|&#39;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&");
}

export function dateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });
}

export function plural(count: number, one: string, many = `${one}s`): string {
  return `${integer(count)} ${count === 1 ? one : many}`;
}
