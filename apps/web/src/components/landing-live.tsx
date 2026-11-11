"use client";

import Link from "next/link";
import { api } from "@/lib/api";
import { dateTime, integer, percent } from "@/lib/format";
import { RECORD_LEVEL, sourceName } from "@/lib/labels";
import { useApi } from "@/lib/use-api";
import { BarList } from "./charts";
import { Skeleton } from "./ui";

/** Live record counts for the hero. Counts are per source and never added across sources. */
export function HeroCounts() {
  const { data, error, loading } = useApi("overview", (s) => api.overview(s));
  if (loading) {
    return (
      <div className="grid grid-cols-2 gap-4">
        {Array.from({ length: 4 }, (_, i) => (
          <Skeleton key={i} className="h-12 w-full opacity-30" />
        ))}
      </div>
    );
  }
  if (error || !data) {
    return (
      <p className="text-sm text-ink-text-2">
        Start the local Compassio API to see live record counts here. Nothing on this page is invented
        while it is offline.
      </p>
    );
  }
  return (
    <dl className="grid grid-cols-2 gap-x-6 gap-y-4">
      {data.sources.map((s) => (
        <div key={s.source_id}>
          <dt className="text-2xs text-ink-text-2">{sourceName(s.source_id)}</dt>
          <dd className="num text-xl font-semibold text-white">
            {integer(s.project_rows)}
            <span className="ml-1.5 text-2xs font-normal text-ink-text-2">
              {RECORD_LEVEL[s.record_level] ?? "records"}
            </span>
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function ProblemFacts() {
  const { data } = useApi("overview", (s) => api.overview(s));
  const links = data ? Object.values(data.cross_source_links).reduce((a, b) => a + b, 0) : null;
  const sources = data?.sources.length ?? null;
  return (
    <ul className="grid gap-px overflow-hidden rounded-2 border border-line bg-line md:grid-cols-3">
      <li className="bg-panel p-6">
        <p className="num text-3xl font-semibold">{links !== null ? integer(links) : "Hundreds of"}</p>
        <p className="mt-2 font-semibold">records describe the same project in two databases</p>
        <p className="mt-2 text-sm text-text-2">
          Climate Funds Update rows point at Green Climate Fund projects. Adding both double counts the
          money. Compassio links them explicitly and never adds them.
        </p>
      </li>
      <li className="bg-panel p-6">
        <p className="text-3xl font-semibold">Approved ≠ disbursed</p>
        <p className="mt-2 font-semibold">one dollar figure can mean five different things</p>
        <p className="mt-2 text-sm text-text-2">
          Commitments, approvals, disbursements, repayments and pledges sit side by side in the raw data.
          Each figure here keeps its meaning, currency and price basis.
        </p>
      </li>
      <li className="bg-panel p-6">
        <p className="num text-3xl font-semibold">{sources !== null ? `${sources} sources` : "Several sources"}</p>
        <p className="mt-2 font-semibold">each with its own idea of “climate”</p>
        <p className="mt-2 text-sm text-text-2">
          Fund themes, research annotations and donor markers do not agree. Compassio shows which one
          applies, and adds AI screening for text that has no label at all.
        </p>
      </li>
    </ul>
  );
}

export function LiveFundingPreview() {
  const { data, error, loading } = useApi("landing-cfu", (s) =>
    api.fundingBy("country", { metric: "cfu_approvals_usd", limit: 6 }, s),
  );
  if (loading) return <Skeleton className="h-40 w-full" />;
  if (error || !data) return <p className="text-sm text-text-3">Live preview appears when the API is running.</p>;
  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs text-text-3">
        Live: {data.declaration.label}. Top {data.groups_shown} of {integer(data.groups_total)} countries,
        single-country projects only.
      </p>
      <BarList
        unitLabel={data.declaration.currency ?? ""}
        data={data.groups.map((g) => ({
          key: g.key,
          label: g.label,
          value: g.total,
          unavailableReason: g.unavailable_reason,
        }))}
      />
    </div>
  );
}

export function ModelAdvantage() {
  const { data, error } = useApi("model-comparison", (s) => api.modelComparison(s));
  if (error || !data) {
    return <p className="text-sm text-ink-text-2">Benchmark figures load from the local API.</p>;
  }
  const rows: Array<[string, string]> = [
    ["non_energy_recall", "Non-energy climate projects found"],
    ["adaptation_only_recall", "Adaptation-only projects found"],
    ["average_precision", "Ranking quality (average precision)"],
  ];
  return (
    <div className="flex flex-col gap-4">
      <table className="w-full text-sm text-ink-text">
        <caption className="sr-only">ML v1 and ML v2 on the same development-validation records</caption>
        <thead>
          <tr className="text-left text-2xs text-ink-text-2">
            <th className="pb-2 font-medium">Same {integer(data.records)} FCDO/EC records</th>
            <th className="pb-2 text-right font-medium">ML v1</th>
            <th className="pb-2 text-right font-medium">ML v2</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([key, label]) => (
            <tr key={key} className="border-t border-ink-2">
              <td className="py-2">{label}</td>
              <td className="num py-2 text-right text-ink-text-2">{percent(data.ml_v1.metrics[key])}</td>
              <td className="num py-2 text-right font-semibold text-white">{percent(data.ml_v2.metrics[key])}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-2xs text-ink-text-2">
        Measured on a donor-labelled development-validation set that was also used to choose ML v2, so
        these figures are optimistic. The labels are publisher Rio markers, not independently verified
        ground truth.{" "}
        <Link href="/screening" className="underline underline-offset-2 hover:text-white">
          See the full comparison
        </Link>
      </p>
    </div>
  );
}

export function SourceList() {
  const { data, error } = useApi("coverage", (s) => api.coverage(s));
  if (error || !data) return <p className="text-sm text-text-3">Source list loads from the local API.</p>;
  const served = data.sources.filter((s) => s.project_rows > 0 || s.financial_observation_rows > 0);
  return (
    <ul className="divide-y divide-line rounded-2 border border-line bg-panel">
      {served.map((s) => (
        <li key={s.source_id} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 px-4 py-3">
          <div className="min-w-0">
            <p className="font-medium">{s.name}</p>
            <p className="text-xs text-text-3">{s.publisher}</p>
          </div>
          <p className="num text-xs text-text-2">
            {integer(s.project_rows)} rows · {integer(s.reported_amount_rows)} reported amounts ·
            imported {dateTime(s.last_completed_import)}
          </p>
        </li>
      ))}
    </ul>
  );
}
