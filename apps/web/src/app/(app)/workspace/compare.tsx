"use client";

import Link from "next/link";
import {
  CheckCircle2,
  CircleDashed,
  Bookmark,
  ArrowUpRight,
  TriangleAlert,
  X,
} from "lucide-react";
import { useState } from "react";
import { Disclaimers, MeaningBadge } from "@/components/finance";
import {
  Badge,
  Button,
  Disclosure,
  ErrorState,
  LinkButton,
  LoadingBlock,
  Panel,
} from "@/components/ui";
import { SourceNotice } from "@/components/source-notice";
import { api } from "@/lib/api";
import type { CompareResponse, ComparisonGroup } from "@/lib/api-types";
import { exactAmount, humanize, priceBasis } from "@/lib/format";
import { sourceName } from "@/lib/labels";
import { useSelection } from "@/lib/selection";
import { useAction } from "@/lib/use-api";

const MATRIX_LABEL: Record<string, string> = {
  has_description: "Description",
  has_sector: "Sector",
  has_year: "Year",
  has_mapped_country: "Mapped country",
  has_source_status: "Source status",
  has_institution: "Institution",
  has_reported_amount: "Reported amount",
  has_amount_with_currency: "Amount with currency",
  has_dated_amount: "Dated amount",
  has_documents: "Documents",
  has_verified_approval: "Verified approval",
};

function GroupRow({
  group,
  ids,
  titles,
}: {
  group: ComparisonGroup;
  ids: string[];
  titles: Map<string, string>;
}) {
  const cells = new Map(group.cells.map((c) => [c.project_id, c.facts]));
  return (
    <div className="flex flex-col gap-3 rounded-2 border border-line bg-panel p-4">
      <div className="flex flex-wrap items-center gap-2">
        <MeaningBadge
          meaning={group.financial_meaning}
          label={group.meaning_label}
        />
        <span className="text-sm font-medium">{group.meaning_label}</span>
        <span className="text-xs text-text-3">
          {sourceName(group.source_id)} ·{" "}
          {group.currency ?? "currency not stated"} ·{" "}
          {priceBasis(group.price_basis)} · {humanize(group.level)}
        </span>
      </div>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {ids.map((id) => {
          const facts = cells.get(id) ?? [];
          return (
            <div key={id} className="rounded-1 bg-panel-2 px-3 py-2">
              <p
                className="truncate text-2xs text-text-3"
                title={titles.get(id)}
              >
                {titles.get(id) ?? id}
              </p>
              {facts.length === 0 ? (
                <p className="text-sm text-text-3">No figure of this kind</p>
              ) : (
                facts.map((f) => (
                  <p
                    key={f.fact_id}
                    className="num text-sm font-medium"
                    title={f.amount_in_units ?? undefined}
                  >
                    {f.amount_in_units === null ? (
                      <span className="font-normal text-text-3">
                        Not reported
                      </span>
                    ) : (
                      <>
                        {f.currency ?? ""} {exactAmount(f.amount_in_units)}
                      </>
                    )}
                    {f.year ? (
                      <span className="ml-1 text-2xs font-normal text-text-3">
                        {f.year}
                      </span>
                    ) : null}
                    {f.recommended_for_aggregates === false ? (
                      <span className="ml-1 text-2xs font-normal text-caution">
                        not for totals
                      </span>
                    ) : null}
                  </p>
                ))
              )}
            </div>
          );
        })}
      </div>
      <div
        className={`rounded-1 px-3 py-2 text-sm ${group.selection_total_status === "available" ? "bg-canopy-soft" : "bg-caution-soft"}`}
      >
        {group.selection_total_status === "available" &&
        group.selection_total !== null ? (
          <p>
            <span className="font-semibold">
              Selection total: {group.currency}{" "}
              <span className="num">{exactAmount(group.selection_total)}</span>
            </span>{" "}
            <span className="text-xs text-text-2">
              ({group.selection_summed_records} records summed
              {group.selection_missing_records
                ? `, ${group.selection_missing_records} without a reported amount`
                : ""}
              ). {group.selection_total_meaning}
            </span>
          </p>
        ) : (
          <p className="flex items-start gap-2">
            <TriangleAlert
              aria-hidden
              className="mt-0.5 size-4 shrink-0 text-caution"
            />
            <span>
              <span className="font-semibold">No total: </span>
              {group.selection_total_reason}
            </span>
          </p>
        )}
      </div>
    </div>
  );
}

function Result({ data, ids }: { data: CompareResponse; ids: string[] }) {
  const titles = new Map(data.projects.map((p) => [p.project_id, p.title]));
  const mainGroups = data.comparable_groups
    .filter((g) =>
      [
        "historical_commitment",
        "approval",
        "disbursement",
        "readiness_grant",
      ].includes(g.financial_meaning),
    )
    .slice(0, 3);
  const otherGroups = data.comparable_groups.filter(
    (g) => !mainGroups.includes(g),
  );

  return (
    <div className="flex flex-col gap-5">
      {data.duplicate_warnings.map((w) => (
        <div
          key={`${w.relation_type}-${w.project_ids.join()}`}
          role="alert"
          className="flex gap-3 rounded-2 border border-caution/40 bg-caution-soft px-4 py-3 text-sm"
        >
          <TriangleAlert
            aria-hidden
            className="mt-0.5 size-4 shrink-0 text-caution"
          />
          <div>
            <p className="font-semibold">
              {w.relation_type === "same_source_record_group"
                ? "Same funding package"
                : "Probably the same project in two sources"}
            </p>
            <p className="text-text-2">{w.message}</p>
            <p className="mt-1 text-xs text-text-3">
              {w.project_ids.map((id) => titles.get(id) ?? id).join("  ·  ")} (
              {humanize(w.verification_state)})
            </p>
          </div>
        </div>
      ))}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {data.projects.map((p) => (
          <article
            key={p.project_id}
            className="flex flex-col gap-1 rounded-2 border border-line bg-panel p-4"
          >
            <Link
              href={`/projects/${encodeURIComponent(p.project_id)}`}
              className="line-clamp-2 font-semibold hover:text-canopy hover:underline"
            >
              {p.title}
            </Link>
            <p className="text-xs text-text-3">
              {p.source.name} ·{" "}
              {p.countries.map((c) => c.country_name).join(", ") ||
                "no country"}{" "}
              · {p.year ?? "no year"}
            </p>
            <p className="mt-2 text-sm text-text-2">
              {p.climate_relevance.status ===
              "research_annotation_climate_related"
                ? "Source research label: climate-related"
                : p.climate_relevance.status === "listed_by_climate_fund"
                  ? "Listed by a climate fund"
                  : p.climate_relevance.status ===
                      "research_annotation_not_climate_related"
                    ? "Source research label: not climate-related"
                    : "No climate annotation available"}
            </p>
            <div className="mt-1 flex flex-wrap gap-1">
              <Badge tone="outline">
                Open to new funding: not determinable
              </Badge>
              {p.multi_country ? (
                <Badge tone="outline">Multi-country value</Badge>
              ) : null}
            </div>
          </article>
        ))}
      </div>

      <section aria-labelledby="groups" className="flex flex-col gap-3">
        <div>
          <h2 id="groups" className="text-lg font-semibold">
            Funding side by side
          </h2>
          <p className="text-sm text-text-2">
            Read each figure in context. Amounts sit together only when their
            source, meaning, currency and basis match. When they cannot safely
            be combined, we explain why.
          </p>
        </div>
        {mainGroups.length ? (
          mainGroups.map((g) => (
            <GroupRow
              key={g.comparability_key}
              group={g}
              ids={ids}
              titles={titles}
            />
          ))
        ) : (
          <p className="text-sm text-text-3">
            These records report no financial figures.
          </p>
        )}
      </section>

      {otherGroups.length ? (
        <Disclosure summary="More financial observations (including non-funding flows)">
          <div className="flex flex-col gap-4">
            {otherGroups.map((g) => (
              <GroupRow
                key={g.comparability_key}
                group={g}
                ids={ids}
                titles={titles}
              />
            ))}
          </div>
        </Disclosure>
      ) : null}
      <Disclosure summary="What information is missing?">
        <Panel
          title="Evidence available per project"
          bodyClass="overflow-x-auto p-0"
        >
          <table className="w-full min-w-[36rem] text-sm">
            <thead className="text-left text-xs text-text-3">
              <tr className="border-b border-line">
                <th className="px-4 py-2 font-medium">Evidence</th>
                {data.projects.map((p) => (
                  <th
                    key={p.project_id}
                    className="max-w-[10rem] truncate px-3 py-2 font-medium"
                    title={p.title}
                  >
                    {p.title.length > 28 ? `${p.title.slice(0, 26)}…` : p.title}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Object.entries(data.field_matrix).map(([field, row]) => (
                <tr key={field} className="border-b border-line last:border-0">
                  <td className="px-4 py-2">
                    {MATRIX_LABEL[field] ?? humanize(field)}
                  </td>
                  {data.projects.map((p) => (
                    <td key={p.project_id} className="px-3 py-2">
                      {row[p.project_id] ? (
                        <CheckCircle2
                          aria-label="present"
                          className="size-4 text-leaf"
                        />
                      ) : (
                        <CircleDashed
                          aria-label="missing"
                          className="size-4 text-text-3"
                        />
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      </Disclosure>
      <Disclaimers items={data.disclaimers} />

      <SourceNotice
        access={data.access}
        attribution={[...new Set(data.projects.map((p) => p.source.name))].join(
          ", ",
        )}
      />
    </div>
  );
}

export function CompareTab() {
  const { items, remove } = useSelection();
  const [submitted, setSubmitted] = useState("");
  const result = useAction((ids: string[]) => api.compare(ids));
  const ids = items.map((i) => i.id);
  const key = ids.join("|");
  if (!items.length)
    return (
      <section className="project-card flex flex-col items-center px-6 py-16 text-center sm:py-24">
        <div className="mb-7 flex size-20 items-center justify-center rounded-full bg-canopy-soft">
          <Bookmark aria-hidden className="size-8 text-canopy" />
        </div>
        <h2 className="text-2xl font-semibold">Your shortlist is empty.</h2>
        <p className="mb-8 mt-4 max-w-md text-text-2">
          Explore projects and save the ones you want to compare. Your next
          research question starts with a closer look.
        </p>
        <LinkButton href="/projects" variant="primary">
          Discover projects <ArrowUpRight aria-hidden className="size-4" />
        </LinkButton>
      </section>
    );
  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <p className="text-sm text-text-3">
          {items.length} of 10 projects saved
        </p>
        <LinkButton href="/projects" variant="ghost">
          Discover another project
        </LinkButton>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        {items.map((p, i) => (
          <article
            key={p.id}
            className="project-card flex min-w-0 items-start gap-4 p-6"
          >
            <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-canopy-soft text-sm font-semibold text-canopy">
              {String(i + 1).padStart(2, "0")}
            </span>
            <div className="min-w-0 flex-1">
              <Link
                href={`/projects/${encodeURIComponent(p.id)}`}
                className="line-clamp-2 font-semibold hover:text-canopy"
              >
                {p.title}
              </Link>
              <p className="mt-3 text-xs text-text-3">
                {sourceName(p.sourceId)}
              </p>
              <Link
                href={`/projects/${encodeURIComponent(p.id)}`}
                className="mt-4 inline-block text-sm font-medium text-canopy"
              >
                Review project
              </Link>
            </div>
            <Button
              variant="ghost"
              size="sm"
              aria-label={`Remove ${p.title}`}
              onClick={() => remove(p.id)}
            >
              <X aria-hidden className="size-4" />
            </Button>
          </article>
        ))}
      </div>
      <div className="flex flex-wrap gap-3">
        <Button
          variant="primary"
          disabled={items.length < 2}
          loading={result.loading}
          onClick={() => {
            setSubmitted(key);
            void result.execute(ids);
          }}
        >
          Compare selected projects
        </Button>
        <LinkButton href="/workspace?tab=prioritize">
          Prioritize my shortlist
        </LinkButton>
      </div>
      {items.length < 2 ? (
        <p className="text-sm text-text-3">
          Save one more project to compare their funding and climate evidence.
        </p>
      ) : null}
      {result.loading ? (
        <LoadingBlock rows={5} label="Comparing evidence" />
      ) : submitted === key && result.error ? (
        <ErrorState error={result.error} />
      ) : submitted === key && result.data ? (
        <Result data={result.data} ids={ids} />
      ) : null}
      <div className="rounded-2 bg-panel-2 p-6">
        <p className="mb-3 text-sm text-text-2">
          Want to explore a possible budget split? This optional tool is a
          simulation, not a funding offer.
        </p>
        <Link href="/scenarios" className="text-sm font-semibold text-canopy">
          Explore a hypothetical funding scenario
        </Link>
      </div>
    </div>
  );
}
