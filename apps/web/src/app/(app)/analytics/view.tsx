"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { X } from "lucide-react";
import {
  ApprovedDisbursed,
  ClimateDistributions,
  CountryProfile,
  CountrySelect,
  Coverage,
  Institutions,
  MetricExplorer,
} from "@/components/analytics-panels";
import { AccessLine } from "@/components/finance";
import { Button, ErrorState, Field, LoadingBlock, Panel, Tabs, inputClass } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";

const TABS = [
  { id: "countries", label: "Countries" },
  { id: "sectors", label: "Sectors" },
  { id: "institutions", label: "Institutions" },
  { id: "approved", label: "Approved vs disbursed" },
  { id: "climate", label: "Climate labels" },
  { id: "profile", label: "Country profile" },
  { id: "coverage", label: "Coverage & freshness" },
] as const;
type Tab = (typeof TABS)[number]["id"];

function ClimateTab({ country }: { country: string }) {
  const res = useApi(`climate:${country}`, (s) => api.climateDistribution({ country: country || undefined }, s));
  if (res.error) return <ErrorState error={res.error} onRetry={res.reload} />;
  if (!res.data) return <LoadingBlock rows={8} />;
  return (
    <div className="flex flex-col gap-4">
      <Panel title="How each source labels climate" description={res.data.statement}>
        <ClimateDistributions data={res.data.distributions} />
      </Panel>
      <AccessLine access={res.data.access} />
    </div>
  );
}

export function AnalyticsView() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const tab = (TABS.some((t) => t.id === params.get("tab")) ? params.get("tab") : "countries") as Tab;
  const metric = params.get("metric") ?? "cfu_approvals_usd";
  const sectorMetric = params.get("metric") ?? "cfu_approvals_usd";
  const country = params.get("country") ?? "";
  const yearFrom = params.get("year_from") ? Number(params.get("year_from")) : undefined;
  const yearTo = params.get("year_to") ? Number(params.get("year_to")) : undefined;

  const set = (patch: Record<string, string>) => {
    const next = new URLSearchParams(params.toString());
    for (const [k, v] of Object.entries(patch)) {
      if (v) next.set(k, v);
      else next.delete(k);
    }
    router.replace(`${pathname}?${next.toString()}`, { scroll: false });
  };

  const needsCountry = tab === "institutions" || tab === "approved" || tab === "climate" || tab === "profile";
  const needsYears = tab === "countries" || tab === "sectors";

  return (
    <div className="flex flex-col gap-5">
      <Tabs label="Analytics views" value={tab} onChange={(t) => set({ tab: t })} tabs={[...TABS]} />

      {needsCountry || needsYears ? (
        <div className="flex flex-wrap items-end gap-3 rounded-2 border border-line bg-panel p-4">
          {needsCountry || tab === "countries" ? (
            <div className="w-full sm:w-64">
              <Field label={tab === "countries" ? "Trend for country" : "Country"} htmlFor="a-country">
                <CountrySelect id="a-country" value={tab === "profile" ? country || "PAK" : country} onChange={(v) => set({ country: v })} allowAll={tab !== "profile"} />
              </Field>
            </div>
          ) : null}
          {needsYears ? (
            <>
              <div className="w-28">
                <Field label="Year from" htmlFor="a-yf">
                  <input id="a-yf" type="number" min={1900} max={2100} value={yearFrom ?? ""} onChange={(e) => set({ year_from: e.target.value })} className={inputClass} />
                </Field>
              </div>
              <div className="w-28">
                <Field label="Year to" htmlFor="a-yt">
                  <input id="a-yt" type="number" min={1900} max={2100} value={yearTo ?? ""} onChange={(e) => set({ year_to: e.target.value })} className={inputClass} />
                </Field>
              </div>
            </>
          ) : null}
          {country || yearFrom || yearTo ? (
            <Button variant="ghost" onClick={() => set({ country: "", year_from: "", year_to: "" })}>
              <X aria-hidden className="size-4" /> Reset
            </Button>
          ) : null}
        </div>
      ) : null}

      <div role="tabpanel">
        {tab === "countries" ? (
          <MetricExplorer
            metricId={metric}
            onMetric={(m) => set({ metric: m })}
            dimension="country"
            country={country}
            onCountry={(iso3) => set({ country: iso3 })}
            yearFrom={yearFrom}
            yearTo={yearTo}
          />
        ) : tab === "sectors" ? (
          <MetricExplorer metricId={sectorMetric} onMetric={(m) => set({ metric: m })} dimension="sector" yearFrom={yearFrom} yearTo={yearTo} />
        ) : tab === "institutions" ? (
          <Institutions country={country} />
        ) : tab === "approved" ? (
          <ApprovedDisbursed country={country} />
        ) : tab === "climate" ? (
          <ClimateTab country={country} />
        ) : tab === "profile" ? (
          <CountryProfile iso3={country || "PAK"} />
        ) : (
          <Coverage />
        )}
      </div>
    </div>
  );
}
