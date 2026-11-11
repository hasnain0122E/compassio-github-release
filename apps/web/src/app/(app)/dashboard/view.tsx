"use client";

import Link from "next/link";
import { useState } from "react";
import { Brain, Calculator, Scale, TableProperties } from "lucide-react";
import { ApprovedDisbursed, Coverage, MetricExplorer } from "@/components/analytics-panels";
import { AccessLine, Disclaimers } from "@/components/finance";
import { Disclosure, ErrorState, LoadingBlock, Panel } from "@/components/ui";
import { api } from "@/lib/api";
import { humanize, integer } from "@/lib/format";
import { RECORD_LEVEL, sourceName } from "@/lib/labels";
import { useApi } from "@/lib/use-api";

function SourceCounts() {
  const overview = useApi("overview", (s) => api.overview(s));
  if (overview.error) return <ErrorState error={overview.error} onRetry={overview.reload} />;
  if (!overview.data) return <LoadingBlock rows={4} label="Loading record counts" />;
  const o = overview.data;
  return (
    <div className="flex flex-col gap-3">
      <dl className="grid gap-px overflow-hidden rounded-2 border border-line bg-line sm:grid-cols-2 lg:grid-cols-5">
        {o.sources.map((s) => (
          <div key={s.source_id} className="flex flex-col gap-1 bg-panel p-4">
            <dt className="text-xs text-text-3">{sourceName(s.source_id)}</dt>
            <dd className="num text-2xl font-semibold leading-tight">{integer(s.project_rows)}</dd>
            <dd className="text-2xs text-text-3">{RECORD_LEVEL[s.record_level] ?? humanize(s.record_level)}</dd>
            <dd className="mt-1 text-xs text-text-2">
              <Link href={`/projects?source=${s.source_id}&country=PAK`} className="hover:text-canopy hover:underline">
                <span className="num font-medium">{integer(s.pakistan_rows)}</span> in Pakistan
              </Link>
              {s.min_year ? (
                <span className="num text-text-3">
                  {" "}
                  · {s.min_year}–{s.max_year}
                </span>
              ) : null}
            </dd>
          </div>
        ))}
      </dl>
      <p className="text-2xs text-text-3">
        {o.counting_rules[0]} {Object.values(o.cross_source_links).reduce((a, b) => a + b, 0)} records are explicitly linked across sources.
      </p>
    </div>
  );
}

function Definitions() {
  const m = useApi("methodology", (s) => api.methodology(s));
  const o = useApi("overview", (s) => api.overview(s));
  if (!m.data) return null;
  return (
    <Disclosure summary="Definitions: what each kind of money means">
      <dl className="grid gap-3 sm:grid-cols-2">
        {Object.entries(m.data.financial_meanings).map(([k, v]) => (
          <div key={k}>
            <dt className="font-medium">{humanize(k)}</dt>
            <dd className="text-text-2">{v}</dd>
          </div>
        ))}
      </dl>
      {o.data ? (
        <ul className="mt-4 list-disc pl-5 text-text-2">
          {o.data.counting_rules.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      ) : null}
    </Disclosure>
  );
}

const ACTIONS = [
  { href: "/projects?country=PAK", title: "Explore Pakistan projects", body: "Filter by sector, source and year", Icon: TableProperties },
  { href: "/screening", title: "Screen a project with AI", body: "Compassio Climate Intelligence — ML v2", Icon: Brain },
  { href: "/workspace", title: "Compare and prioritize", body: "Evidence side by side, transparent ranking", Icon: Scale },
  { href: "/scenarios", title: "Plan a hypothetical budget", body: "Allocated + unallocated = budget", Icon: Calculator },
];

export function DashboardView() {
  const [metric, setMetric] = useState("cfu_approvals_usd");
  const [country, setCountry] = useState("");
  const overview = useApi("overview", (s) => api.overview(s));
  return (
    <div className="flex flex-col gap-8">
      <section aria-labelledby="records" className="flex flex-col gap-3">
        <h2 id="records" className="text-lg font-semibold">Project records by source</h2>
        <SourceCounts />
      </section>

      <nav aria-label="Quick actions" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {ACTIONS.map(({ href, title, body, Icon }) => (
          <Link key={href} href={href} className="group flex items-start gap-3 rounded-2 border border-line bg-panel p-4 hover:border-canopy">
            <Icon aria-hidden className="mt-0.5 size-5 shrink-0 text-canopy" />
            <span>
              <span className="block font-semibold group-hover:text-canopy">{title}</span>
              <span className="text-xs text-text-3">{body}</span>
            </span>
          </Link>
        ))}
      </nav>

      <section aria-labelledby="funding" className="flex flex-col gap-3">
        <div>
          <h2 id="funding" className="text-lg font-semibold">Historical funding at a glance</h2>
          <p className="text-sm text-text-2">
            Pick one metric. Its totals come from the server&apos;s exact decimal arithmetic and cover only figures with the
            same meaning, currency and price basis.
            {country ? (
              <>
                {" "}
                Trend shown for <span className="font-medium">{country}</span>.{" "}
                <button type="button" onClick={() => setCountry("")} className="text-canopy hover:underline">
                  Show all countries
                </button>
              </>
            ) : null}
          </p>
        </div>
        <MetricExplorer compact metricId={metric} onMetric={setMetric} dimension="country" country={country} onCountry={setCountry} />
      </section>

      <section aria-labelledby="pak" className="flex flex-col gap-3">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <div>
            <h2 id="pak" className="text-lg font-semibold">Pakistan: approved versus disbursed</h2>
            <p className="text-sm text-text-2">Only projects that report both figures are compared. Each source keeps its own meaning.</p>
          </div>
          <Link href="/analytics?tab=profile&country=PAK" className="text-sm font-semibold text-canopy hover:underline">
            Full Pakistan profile
          </Link>
        </div>
        <ApprovedDisbursed country="PAK" />
      </section>

      <section aria-labelledby="freshness" className="flex flex-col gap-3">
        <h2 id="freshness" className="text-lg font-semibold">Sources, coverage and freshness</h2>
        <Coverage />
      </section>

      <Panel title="Reading these numbers" bodyClass="flex flex-col gap-3 p-4">
        <Definitions />
        {overview.data ? <Disclaimers items={overview.data.disclaimers} title="Caveats that apply to every figure" /> : null}
        {overview.data ? <AccessLine access={overview.data.access} /> : null}
      </Panel>
    </div>
  );
}
