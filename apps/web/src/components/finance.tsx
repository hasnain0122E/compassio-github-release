"use client";

import { ShieldCheck } from "lucide-react";
import type { AccessNotice as AccessNoticeT, FinancialFact, MetricDeclaration, MetricOut } from "@/lib/api-types";
import { exactAmount, humanize, integer, money, priceBasis } from "@/lib/format";
import { MEANING, sourceName } from "@/lib/labels";
import { Badge, Disclosure } from "./ui";

export function MeaningBadge({ meaning, label }: { meaning: string; label?: string }) {
  const m = MEANING[meaning];
  const tone = !m ? "neutral" : m.tone === "funding" ? "canopy" : m.tone === "pledge" ? "caution" : "outline";
  return (
    <Badge tone={tone} title={label}>
      {m?.short ?? humanize(meaning)}
    </Badge>
  );
}

const ATTRIBUTION: Record<string, string> = {
  single_country_project: "Single-country project",
  whole_project_value_not_attributable_to_one_country: "Whole multi-country value (not split by country)",
  source_published_country_line: "Country line published by the source",
  no_mapped_country: "No mapped country",
};

/** Financial facts exactly as the backend states them. Missing amounts read "Not reported". */
export function FactsTable({ facts, caption }: { facts: FinancialFact[]; caption: string }) {
  if (!facts.length) return <p className="text-sm text-text-3">No financial figures are recorded for this project.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[44rem] text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead className="text-left text-xs text-text-3">
          <tr className="border-b border-line">
            <th className="py-2 pr-3 font-medium">What the figure is</th>
            <th className="py-2 pr-3 text-right font-medium">Amount</th>
            <th className="py-2 pr-3 font-medium">Basis</th>
            <th className="py-2 pr-3 font-medium">Date</th>
            <th className="py-2 font-medium">Provenance</th>
          </tr>
        </thead>
        <tbody>
          {facts.map((f) => (
            <tr key={f.fact_id} className="border-b border-line align-top last:border-0">
              <td className="py-2.5 pr-3">
                <div className="flex flex-col gap-1">
                  <MeaningBadge meaning={f.financial_meaning} label={f.meaning_label} />
                  <span className="text-xs text-text-2">{f.meaning_label}</span>
                  {f.financing_type ? <span className="text-2xs text-text-3">{f.financing_type}</span> : null}
                </div>
              </td>
              <td className="num whitespace-nowrap py-2.5 pr-3 text-right">
                {f.amount_in_units === null ? (
                  <span className="text-text-3">Not reported</span>
                ) : (
                  <span className="font-medium" title={`Exact: ${f.amount_in_units}`}>
                    {f.currency ?? ""} {exactAmount(f.amount_in_units)}
                  </span>
                )}
                {f.currency === null && f.amount_in_units !== null ? (
                  <span className="block text-2xs text-caution">currency not stated</span>
                ) : null}
              </td>
              <td className="py-2.5 pr-3 text-xs text-text-2">
                {priceBasis(f.price_basis)}
                <span className="block text-text-3">{humanize(f.level)}</span>
              </td>
              <td className="py-2.5 pr-3 text-xs text-text-2">
                {f.year ?? (f.first_year ? `${f.first_year}–${f.last_year}` : "—")}
                <span className="block text-text-3">{humanize(f.date_meaning)}</span>
              </td>
              <td className="py-2.5 text-xs text-text-2">
                <div className="flex flex-wrap gap-1">
                  <Badge tone="outline">
                    {f.fact_type === "source_reported" ? "Reported by source" : `Sum of ${f.transactions_summed ?? ""} source transactions`}
                  </Badge>
                  {f.estimated ? <Badge tone="caution">Estimated</Badge> : null}
                  {f.recommended_for_aggregates === false ? (
                    <Badge tone="caution" title="The source does not recommend this figure for totals">
                      Not for totals
                    </Badge>
                  ) : null}
                </div>
                <span className="mt-1 block text-text-3">{ATTRIBUTION[f.country_attribution] ?? f.country_attribution}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** The metric declaration: what a total includes, means and excludes. */
export function Declaration({ d }: { d: MetricDeclaration }) {
  const excluded = Object.entries(d.excluded_records ?? {}).filter(([, n]) => n > 0);
  return (
    <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
      <div>
        <dt className="text-xs text-text-3">Flow</dt>
        <dd className="mt-0.5 flex flex-wrap items-center gap-1.5">
          <Badge tone={d.is_funding ? "canopy" : "outline"}>{d.is_funding ? "Funding flow" : "Not a funding flow"}</Badge>
          <span>{humanize(d.flow_kind)}</span>
        </dd>
      </div>
      <div>
        <dt className="text-xs text-text-3">Currency and basis</dt>
        <dd className="mt-0.5">
          {d.currency ?? "Currency not stated"} · {priceBasis(d.price_basis)}
        </dd>
      </div>
      <div>
        <dt className="text-xs text-text-3">Year basis</dt>
        <dd className="mt-0.5">{humanize(d.year_basis)}</dd>
      </div>
      <div>
        <dt className="text-xs text-text-3">Source</dt>
        <dd className="mt-0.5">{sourceName(d.source_id)}</dd>
      </div>
      <div className="sm:col-span-2">
        <dt className="text-xs text-text-3">Included universe</dt>
        <dd className="mt-0.5 text-text-2">{d.universe}</dd>
      </div>
      <div className="sm:col-span-2">
        <dt className="text-xs text-text-3">Meaning</dt>
        <dd className="mt-0.5 text-text-2">{d.financial_meaning}</dd>
      </div>
      {d.known_exclusions.length || excluded.length ? (
        <div className="sm:col-span-2 lg:col-span-4">
          <dt className="text-xs text-text-3">Known exclusions</dt>
          <dd className="mt-0.5 text-text-2">
            <ul className="list-disc pl-5">
              {d.known_exclusions.map((x) => (
                <li key={x}>{x}</li>
              ))}
              {excluded.map(([reason, n]) => (
                <li key={reason}>
                  {humanize(reason)}: <span className="num">{integer(n)}</span> records left out
                </li>
              ))}
            </ul>
          </dd>
        </div>
      ) : null}
    </dl>
  );
}

export function AccessLine({ access }: { access: AccessNoticeT | undefined }) {
  if (!access) return null;
  return (
    <p className="flex items-start gap-2 text-2xs text-text-3">
      <ShieldCheck aria-hidden className="mt-px size-3.5 shrink-0" />
      {access.notice}
    </p>
  );
}

export function Disclaimers({ items, title = "How to read these numbers" }: { items: string[]; title?: string }) {
  if (!items.length) return null;
  return (
    <Disclosure summary={title}>
      <ul className="flex list-disc flex-col gap-1 pl-5 text-text-2">
        {items.map((d) => (
          <li key={d}>{d}</li>
        ))}
      </ul>
    </Disclosure>
  );
}

/** Pick ONE metric; metrics are never mixed (each has its own flow, currency and basis). */
export function MetricPicker({
  metrics,
  value,
  onChange,
  id,
}: {
  metrics: MetricOut[];
  value: string;
  onChange: (id: string) => void;
  id: string;
}) {
  return (
    <select
      id={id}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="h-10 w-full rounded-1 border border-line-strong bg-panel px-3 text-sm"
    >
      {metrics.map((m) => (
        <option key={m.metric_id} value={m.metric_id}>
          {m.label}
          {m.is_funding ? "" : " (not funding)"}
        </option>
      ))}
    </select>
  );
}

export function unitLabelFor(d: { currency: string | null; price_basis: string }): string {
  return d.currency ? `${d.currency}${d.price_basis === "constant_2021_usd" ? " (2021 prices)" : ""}` : "Amount (currency not stated)";
}

export { money };
