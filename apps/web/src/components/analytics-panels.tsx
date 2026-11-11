"use client";

import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";
import type { MetricOut } from "@/lib/api-types";
import {
  dateOnly,
  dateTime,
  exactAmount,
  humanize,
  integer,
  money,
  ratioString,
} from "@/lib/format";
import { FLOW_MEANING, sourceName } from "@/lib/labels";
import { useApi } from "@/lib/use-api";
import { BarList, CountBars, YearColumns, YearTable } from "./charts";
import {
  AccessLine,
  Declaration,
  Disclaimers,
  MeaningBadge,
  MetricPicker,
  unitLabelFor,
} from "./finance";
import {
  Badge,
  Disclosure,
  EmptyState,
  ErrorState,
  Field,
  LoadingBlock,
  Panel,
  Tabs,
  inputClass,
} from "./ui";

export function useMetrics() {
  return useApi("metrics", (s) => api.metrics(s));
}

export function useCountries() {
  const filters = useApi("filters", (s) => api.filters(s));
  const list = [...(filters.data?.countries ?? [])].sort((a, b) =>
    a.name.localeCompare(b.name),
  );
  return { list, error: filters.error, reload: filters.reload };
}

export function CountrySelect({
  id,
  value,
  onChange,
  allowAll = true,
}: {
  id: string;
  value: string;
  onChange: (v: string) => void;
  allowAll?: boolean;
}) {
  const { list } = useCountries();
  return (
    <select
      id={id}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={inputClass}
    >
      {allowAll ? <option value="">All countries</option> : null}
      {list.map((c) => (
        <option key={c.iso3} value={c.iso3}>
          {c.name}
        </option>
      ))}
    </select>
  );
}

/** Trend + ranked groups for ONE metric. */
export function MetricExplorer({
  metricId,
  onMetric,
  dimension,
  country,
  onCountry,
  yearFrom,
  yearTo,
  compact = false,
}: {
  metricId: string;
  onMetric: (id: string) => void;
  dimension: "country" | "sector";
  country?: string;
  onCountry?: (iso3: string) => void;
  yearFrom?: number;
  yearTo?: number;
  compact?: boolean;
}) {
  const metrics = useMetrics();
  const [view, setView] = useState<"chart" | "table">("chart");
  const grouped = useApi(
    `by-${dimension}:${metricId}:${yearFrom ?? ""}:${yearTo ?? ""}`,
    (s) =>
      api.fundingBy(
        dimension,
        {
          metric: metricId,
          year_from: yearFrom,
          year_to: yearTo,
          limit: compact ? 8 : 15,
        },
        s,
      ),
  );
  const trend = useApi(
    `trend:${metricId}:${country ?? ""}:${yearFrom ?? ""}:${yearTo ?? ""}`,
    (s) =>
      api.trends(
        {
          metric: metricId,
          country: country || undefined,
          year_from: yearFrom,
          year_to: yearTo,
        },
        s,
      ),
  );
  const metric: MetricOut | undefined = metrics.data?.metrics.find(
    (m) => m.metric_id === metricId,
  );
  const unit = metric ? unitLabelFor(metric) : "";

  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-[minmax(0,1fr)] gap-3 md:grid-cols-[minmax(0,1fr)_auto]">
        <Field
          label="Explore historical funding"
          htmlFor={`metric-${dimension}`}
        >
          {metrics.data ? (
            <MetricPicker
              id={`metric-${dimension}`}
              metrics={metrics.data.metrics}
              value={metricId}
              onChange={onMetric}
            />
          ) : (
            <LoadingBlock rows={1} />
          )}
        </Field>
        {metric ? (
          <div className="flex flex-wrap items-end gap-1.5">
            <Badge tone={metric.is_funding ? "canopy" : "outline"}>
              {metric.is_funding ? "Funding flow" : "Not funding"}
            </Badge>
            <Badge tone="outline">
              {metric.currency ?? "No currency stated"}
            </Badge>
            <Badge tone="outline">{sourceName(metric.source_id)}</Badge>
          </div>
        ) : null}
      </div>
      {metrics.error ? (
        <ErrorState error={metrics.error} onRetry={metrics.reload} />
      ) : null}

      <div
        className={`grid grid-cols-[minmax(0,1fr)] gap-5 ${compact ? "lg:grid-cols-2" : ""}`}
      >
        <Panel
          title={country ? `By year in ${country}` : "By year"}
          description={
            metric
              ? `${metric.label}. Years with no reported data stay empty.`
              : undefined
          }
          actions={
            <Tabs
              label="Trend view"
              value={view}
              onChange={setView}
              tabs={[
                { id: "chart", label: "Chart" },
                { id: "table", label: "Table" },
              ]}
            />
          }
        >
          {trend.error ? (
            <ErrorState error={trend.error} onRetry={trend.reload} />
          ) : !trend.data ? (
            <LoadingBlock rows={6} />
          ) : trend.data.status === "unavailable" ? (
            <EmptyState title="No trend for this metric">
              {trend.data.unavailable_reason}
            </EmptyState>
          ) : (
            <div className="flex flex-col gap-3">
              {view === "chart" ? (
                <YearColumns
                  unitLabel={unit}
                  data={trend.data.points.map((p) => ({
                    year: p.year,
                    value: p.total,
                    status: p.status,
                    detail:
                      p.status === "available"
                        ? `${integer(p.summed_records)} records${p.missing_value_records ? `, ${integer(p.missing_value_records)} without amount` : ""}`
                        : (p.unavailable_reason ?? undefined),
                  }))}
                />
              ) : (
                <YearTable
                  unitLabel={unit}
                  data={trend.data.points.map((p) => ({
                    year: p.year,
                    value: p.total,
                    status: p.status,
                    detail: `${integer(p.summed_records)} summed · ${integer(p.missing_value_records)} missing · ${integer(p.estimated_records)} estimated`,
                  }))}
                />
              )}
              {trend.data.undated_records ? (
                <p className="text-2xs text-text-3">
                  {integer(trend.data.undated_records)} records have no year and
                  are not in this chart.
                </p>
              ) : null}
            </div>
          )}
        </Panel>

        <Panel
          title={dimension === "country" ? "Top countries" : "Top sectors"}
          description={
            grouped.data && grouped.data.status === "available"
              ? `${grouped.data.groups_shown} of ${integer(grouped.data.groups_total)} shown. ${
                  dimension === "country"
                    ? "Multi-country project values are not split across countries."
                    : ""
                }`
              : undefined
          }
        >
          {grouped.error ? (
            <ErrorState error={grouped.error} onRetry={grouped.reload} />
          ) : !grouped.data ? (
            <LoadingBlock rows={8} />
          ) : grouped.data.status === "unavailable" ? (
            <EmptyState title={`Not available by ${dimension}`}>
              {grouped.data.unavailable_reason}
            </EmptyState>
          ) : (
            <BarList
              unitLabel={unit}
              data={grouped.data.groups.map((g) => ({
                key: g.key,
                label: g.label,
                value: g.total,
                unavailableReason: g.unavailable_reason,
                note: `${integer(g.summed_records)} records${g.missing_value_records ? ` · ${integer(g.missing_value_records)} no amount` : ""}`,
                onSelect:
                  dimension === "country" && onCountry
                    ? () => onCountry(g.key)
                    : undefined,
              }))}
            />
          )}
          {dimension === "country" &&
          onCountry &&
          grouped.data?.status === "available" ? (
            <p className="mt-2 text-2xs text-text-3">
              Select a country to see its trend.
            </p>
          ) : null}
        </Panel>
      </div>

      {grouped.data ? (
        <Disclosure summary="What this metric includes and leaves out">
          <Declaration d={grouped.data.declaration} />
        </Disclosure>
      ) : null}
      {!compact && grouped.data ? (
        <Disclaimers items={grouped.data.disclaimers} />
      ) : null}
      {grouped.data ? <AccessLine access={grouped.data.access} /> : null}
    </div>
  );
}

export function CountryProfile({ iso3 }: { iso3: string }) {
  const profile = useApi(`profile:${iso3}`, (s) => api.countryProfile(iso3, s));
  if (profile.error)
    return <ErrorState error={profile.error} onRetry={profile.reload} />;
  if (!profile.data)
    return <LoadingBlock rows={8} label="Loading country profile" />;
  const d = profile.data;
  return (
    <div className="flex flex-col gap-5">
      <Panel
        title="Project records"
        description="Per source; records from different sources are never added into one count"
      >
        <div className="overflow-x-auto">
          <table className="w-full min-w-[28rem] text-sm">
            <thead className="text-left text-xs text-text-3">
              <tr className="border-b border-line">
                <th className="py-2 pr-3 font-medium">Source</th>
                <th className="py-2 pr-3 text-right font-medium">
                  Single-country records
                </th>
                <th className="py-2 text-right font-medium">
                  Multi-country records including {d.country}
                </th>
              </tr>
            </thead>
            <tbody>
              {d.project_counts.map((c) => (
                <tr
                  key={c.source_id}
                  className="border-b border-line last:border-0"
                >
                  <td className="py-2 pr-3">
                    <Link
                      href={`/projects?country=${d.country}&source=${c.source_id}`}
                      className="hover:text-canopy hover:underline"
                    >
                      {sourceName(c.source_id)}
                    </Link>
                  </td>
                  <td className="num py-2 pr-3 text-right">
                    {integer(c.single_country_projects)}
                  </td>
                  <td className="num py-2 text-right">
                    {integer(c.multi_country_projects_including_country)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel
        title="Historical money, one metric per row"
        description="Each total has its own source, flow, currency and price basis. They are not comparable with each other and are never added together."
      >
        <ul className="flex flex-col divide-y divide-line">
          {d.metrics.map((m) => (
            <li
              key={m.declaration.metric_id}
              className="grid gap-2 py-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center"
            >
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-1.5">
                  <MeaningBadge
                    meaning={
                      FLOW_MEANING[m.declaration.flow_kind] ??
                      m.declaration.flow_kind
                    }
                  />
                  <span className="text-sm font-medium">
                    {m.declaration.label}
                  </span>
                </div>
                <p className="mt-0.5 text-2xs text-text-3">
                  {sourceName(m.declaration.source_id)} ·{" "}
                  {humanize(m.declaration.year_basis)}
                  {m.first_year
                    ? ` · ${m.first_year}–${m.last_year}`
                    : ""} · {integer(m.summed_records)} records summed
                </p>
              </div>
              <div className="num text-right">
                {m.status === "available" && m.all_years_total !== null ? (
                  <span
                    className="text-lg font-semibold"
                    title={m.all_years_total}
                  >
                    {money(m.all_years_total, m.declaration.currency)}
                  </span>
                ) : (
                  <span className="text-xs text-caution">
                    Unavailable: {m.unavailable_reason}
                  </span>
                )}
              </div>
            </li>
          ))}
        </ul>
      </Panel>

      <div className="grid gap-5 lg:grid-cols-2">
        <Panel
          title="Most common sectors"
          description="Sector names as published (AidData and Climate Funds Update vocabularies differ)"
        >
          {d.top_sectors.length ? (
            <CountBars
              data={d.top_sectors.map((s) => ({
                label: s.label,
                count: s.projects,
              }))}
            />
          ) : (
            <p className="text-sm text-text-3">No sector names published.</p>
          )}
        </Panel>
        <Panel title="Climate labels" description={d.climate.statement}>
          <ClimateDistributions data={d.climate.distributions} />
        </Panel>
      </div>
      <Disclaimers items={d.disclaimers} />
      <AccessLine access={d.access} />
    </div>
  );
}

export function ClimateDistributions({
  data,
}: {
  data: Array<{
    scheme: string;
    meaning: string;
    annotation_source_id: string;
    buckets: Array<{ label: string; projects: number }>;
    projects_annotated: number;
  }>;
}) {
  if (!data.length)
    return (
      <p className="text-sm text-text-3">
        No climate labels for this selection.
      </p>
    );
  return (
    <div className="flex flex-col gap-5">
      {data.map((d) => (
        <div key={d.scheme} className="flex flex-col gap-2">
          <p className="text-sm font-medium">
            {sourceName(d.annotation_source_id)} ·{" "}
            {humanize(d.scheme.split(":")[0])}
          </p>
          <p className="text-2xs text-text-3">{d.meaning}</p>
          <CountBars
            data={d.buckets.map((b) => ({ label: b.label, count: b.projects }))}
            total={d.projects_annotated}
          />
        </div>
      ))}
    </div>
  );
}

export function ApprovedDisbursed({ country }: { country: string }) {
  const res = useApi(`avd:${country}`, (s) =>
    api.approvedVsDisbursed({ country: country || undefined }, s),
  );
  if (res.error) return <ErrorState error={res.error} onRetry={res.reload} />;
  if (!res.data) return <LoadingBlock rows={6} />;
  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-4 lg:grid-cols-3">
        {res.data.sources.map((s) => {
          const ratio =
            s.disbursed_to_approved_ratio !== null
              ? Math.min(1, Number(s.disbursed_to_approved_ratio))
              : null;
          return (
            <Panel
              key={s.source_id}
              title={sourceName(s.source_id)}
              description={`${integer(s.paired_projects)} projects report both figures`}
            >
              <dl className="flex flex-col gap-3 text-sm">
                <div>
                  <dt className="text-xs text-text-3">{s.approval_meaning}</dt>
                  <dd
                    className="num text-lg font-semibold"
                    title={s.approved_total_paired ?? undefined}
                  >
                    {money(s.approved_total_paired, s.currency)}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-text-3">
                    {s.disbursement_meaning}
                  </dt>
                  <dd
                    className="num text-lg font-semibold"
                    title={s.disbursed_total_paired ?? undefined}
                  >
                    {money(s.disbursed_total_paired, s.currency)}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-text-3">
                    Disbursed as a share of approved (paired projects only)
                  </dt>
                  <dd className="flex items-center gap-3">
                    <span className="num text-lg font-semibold">
                      {ratioString(s.disbursed_to_approved_ratio)}
                    </span>
                    {ratio !== null ? (
                      <span className="h-2 flex-1 rounded-r-[4px] bg-grid">
                        <span
                          className="block h-full rounded-r-[4px] bg-series-1"
                          style={{ width: `${ratio * 100}%` }}
                        />
                      </span>
                    ) : null}
                  </dd>
                </div>
              </dl>
              <Disclosure summary="Universe and limitations">
                <p className="text-text-2">{s.universe}</p>
                <ul className="mt-2 list-disc pl-5 text-text-2">
                  {s.limitations.map((l) => (
                    <li key={l}>{l}</li>
                  ))}
                  {Object.entries(s.excluded_projects)
                    .filter(([, n]) => n > 0)
                    .map(([k, n]) => (
                      <li key={k}>
                        {humanize(k)}: {integer(n)} projects excluded
                      </li>
                    ))}
                </ul>
              </Disclosure>
            </Panel>
          );
        })}
      </div>
      <Disclaimers items={res.data.disclaimers} />
      <AccessLine access={res.data.access} />
    </div>
  );
}

export function Institutions({ country }: { country: string }) {
  const res = useApi(`inst:${country}`, (s) =>
    api.institutions({ country: country || undefined, limit: 8 }, s),
  );
  if (res.error) return <ErrorState error={res.error} onRetry={res.reload} />;
  if (!res.data) return <LoadingBlock rows={8} />;
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-text-2">
        {res.data.universe}. Counts are project records, not money.{" "}
        {res.data.note}
      </p>
      <div className="grid gap-4 lg:grid-cols-2">
        {res.data.groups.map((g) => (
          <Panel
            key={`${g.source_id}-${g.role}`}
            title={`${sourceName(g.source_id)}: ${g.role}`}
            description={`${integer(g.distinct_institutions)} distinct · ${integer(g.projects_without_institution)} records without one`}
          >
            <CountBars
              data={g.institutions.map((i) => ({
                label: i.institution,
                count: i.projects,
              }))}
            />
          </Panel>
        ))}
      </div>
      <AccessLine access={res.data.access} />
    </div>
  );
}

export function Coverage() {
  const res = useApi("coverage", (s) => api.coverage(s));
  if (res.error) return <ErrorState error={res.error} onRetry={res.reload} />;
  if (!res.data) return <LoadingBlock rows={8} />;
  return (
    <div className="flex flex-col gap-3">
      <div className="overflow-x-auto rounded-2 border border-line bg-panel">
        <table className="w-full min-w-[52rem] text-sm">
          <caption className="sr-only">Source coverage and freshness</caption>
          <thead className="bg-panel-2 text-left text-xs text-text-3">
            <tr>
              <th className="px-3 py-2 font-medium">Source</th>
              <th className="px-3 py-2 text-right font-medium">Project rows</th>
              <th className="px-3 py-2 text-right font-medium">
                Financial observations
              </th>
              <th className="px-3 py-2 text-right font-medium">
                With reported amount
              </th>
              <th className="px-3 py-2 font-medium">Years</th>
              <th className="px-3 py-2 font-medium">Last import</th>
              <th className="px-3 py-2 font-medium">Rights</th>
            </tr>
          </thead>
          <tbody>
            {res.data.sources.map((s) => (
              <tr key={s.source_id} className="border-t border-line align-top">
                <td className="px-3 py-2.5">
                  <p className="font-medium">{s.name}</p>
                  <p className="text-2xs text-text-3">{s.publisher}</p>
                </td>
                <td className="num px-3 py-2.5 text-right">
                  {integer(s.project_rows)}
                </td>
                <td className="num px-3 py-2.5 text-right">
                  {integer(s.financial_observation_rows)}
                </td>
                <td className="num px-3 py-2.5 text-right">
                  {integer(s.reported_amount_rows)}
                </td>
                <td className="num px-3 py-2.5 text-xs">
                  {s.min_year ? `${s.min_year}–${s.max_year}` : "—"}
                </td>
                <td
                  className="whitespace-nowrap px-3 py-2.5 text-xs"
                  title={dateTime(s.last_completed_import)}
                >
                  {dateOnly(s.last_completed_import)}
                </td>
                <td className="px-3 py-2.5 text-xs">
                  <Badge tone={s.served_in_current_mode ? "outline" : "danger"}>
                    {s.served_in_current_mode
                      ? humanize(s.rights_status)
                      : "Not served"}
                  </Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-2xs text-text-3">
        Data version {res.data.data_version.join(".")}. Rights status “not
        reviewed” means the licence review is pending; data is shown only in
        this local, authorized demo.
      </p>
      <AccessLine access={res.data.access} />
    </div>
  );
}

export { exactAmount };
