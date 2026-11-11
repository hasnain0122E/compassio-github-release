"use client";

import Link from "next/link";
import { useState } from "react";
import { Disclaimers } from "@/components/finance";
import { SourceNotice } from "@/components/source-notice";
import { SelectToggle } from "@/components/project-bits";
import {
  Badge,
  Button,
  Disclosure,
  EmptyState,
  ErrorState,
  LinkButton,
  LoadingBlock,
} from "@/components/ui";
import { api } from "@/lib/api";
import type { PrioritizeRequest, PriorityItem } from "@/lib/api-types";
import { humanize } from "@/lib/format";
import { useSelection } from "@/lib/selection";
import { sourceName } from "@/lib/labels";
import { useAction } from "@/lib/use-api";

const WEIGHTS: Array<{
  key: keyof NonNullable<PrioritizeRequest["weights"]>;
  label: string;
  def: number;
}> = [
  {
    key: "climate_relevance",
    label: "Climate relevance (source labels)",
    def: 3,
  },
  { key: "evidence_completeness", label: "Evidence completeness", def: 2 },
  {
    key: "funding_completeness",
    label: "Funding information completeness",
    def: 2,
  },
  { key: "sector_match", label: "Matches my sectors", def: 1 },
  { key: "country_match", label: "Matches my countries", def: 1 },
  { key: "documentation", label: "Documentation available", def: 1 },
  { key: "review_uncertainty", label: "Needs review (uncertainty)", def: 0 },
];

function Item({ item }: { item: PriorityItem }) {
  const score = Number(item.score);
  return (
    <li className="flex flex-col gap-3 rounded-2 border border-line bg-panel p-4">
      <div className="flex items-start gap-3">
        <span className="num flex size-8 shrink-0 items-center justify-center rounded-1 bg-ink text-sm font-semibold text-white">
          {item.rank}
        </span>
        <div className="min-w-0 flex-1">
          <Link
            href={`/projects/${encodeURIComponent(item.project_id)}`}
            className="line-clamp-2 font-semibold hover:text-canopy hover:underline"
          >
            {item.title}
          </Link>
          <p className="text-xs text-text-3">
            {sourceName(item.source_id)} · {item.project_id}
          </p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          <p className="num text-xl font-semibold">{item.score}</p>
          <span className="h-1.5 w-24 rounded-r-[4px] bg-grid">
            <span
              className="block h-full rounded-r-[4px] bg-series-1"
              style={{ width: `${Math.max(0, Math.min(1, score)) * 100}%` }}
            />
          </span>
        </div>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {item.distinctions.matches_search ? (
          <Badge tone="teal">Matches search</Badge>
        ) : null}
        <Badge
          tone={
            item.distinctions.has_documented_historical_funding
              ? "canopy"
              : "neutral"
          }
          title={item.distinctions.documented_funding_basis}
        >
          {item.distinctions.has_documented_historical_funding
            ? "Documented historical funding"
            : "No documented funding amount"}
        </Badge>
        <Badge tone="outline">Open to new funding: not determinable</Badge>
      </div>
      <Disclosure summary="Why this rank: score breakdown">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[36rem] text-xs">
            <caption className="sr-only">Score components</caption>
            <thead className="text-left text-text-3">
              <tr>
                <th className="py-1 pr-2 font-medium">Criterion</th>
                <th className="py-1 pr-2 text-right font-medium">Weight</th>
                <th className="py-1 pr-2 text-right font-medium">Value</th>
                <th className="py-1 pr-2 text-right font-medium">
                  Contribution
                </th>
                <th className="py-1 font-medium">Evidence</th>
              </tr>
            </thead>
            <tbody>
              {item.components.map((c) => (
                <tr
                  key={c.criterion}
                  className="border-t border-line align-top"
                >
                  <td className="py-1.5 pr-2">{humanize(c.criterion)}</td>
                  <td className="num py-1.5 pr-2 text-right">{c.weight}</td>
                  <td className="num py-1.5 pr-2 text-right">
                    {c.status === "applied" ? (
                      c.value
                    ) : (
                      <span className="text-text-3">{humanize(c.status)}</span>
                    )}
                  </td>
                  <td className="num py-1.5 pr-2 text-right">
                    {c.contribution}
                  </td>
                  <td className="py-1.5 text-text-2">{c.evidence}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-text-3">{item.interpretation}</p>
      </Disclosure>
      <div>
        <SelectToggle
          id={item.project_id}
          title={item.title}
          sourceId={item.source_id}
        />
      </div>
    </li>
  );
}

export function PrioritizeTab() {
  const { items } = useSelection();
  const [focus, setFocus] = useState("balanced");
  const [weights, setWeights] = useState<Record<string, number>>(
    Object.fromEntries(WEIGHTS.map((w) => [w.key, w.def])),
  );
  const run = useAction((body: PrioritizeRequest) => api.prioritize(body));
  if (!items.length)
    return (
      <EmptyState
        title="Start with a shortlist"
        action={
          <LinkButton href="/projects" variant="primary">
            Discover projects
          </LinkButton>
        }
      >
        Save projects from Discover, then organize them for further review.
      </EmptyState>
    );
  const rank = () =>
    void run.execute({
      filters: { project_ids: items.map((p) => p.id) },
      weights,
      page: 1,
      page_size: 10,
      missing_component_policy: "score_zero",
    });
  const allZero = Object.values(weights).every((w) => w === 0);
  return (
    <div className="flex flex-col gap-7">
      <div className="project-card p-6 sm:p-8">
        <p className="section-step">YOUR NEXT REVIEW</p>
        <h2 className="mt-3 text-2xl font-semibold">What matters most?</h2>
        <p className="mb-6 mt-3 max-w-2xl text-text-2">
          Choose what matters most, and Compassio will organize these projects
          for further review.
        </p>
        <div className="mb-6 grid gap-3 sm:grid-cols-3">
          {[
            { label: "A balanced view", key: "balanced" },
            { label: "Climate relevance", key: "climate_relevance" },
            { label: "Stronger evidence", key: "evidence_completeness" },
          ].map((p) => (
            <Button
              key={p.key}
              variant={focus === p.key ? "primary" : "secondary"}
              aria-pressed={focus === p.key}
              onClick={() => {
                setFocus(p.key);
                setWeights(
                  Object.fromEntries(
                    WEIGHTS.map((w) => [
                      w.key,
                      p.key === "balanced"
                        ? w.def
                        : w.key === p.key
                          ? 8
                          : w.def,
                    ]),
                  ),
                );
              }}
            >
              {p.label}
            </Button>
          ))}
        </div>
        <Disclosure summary="Fine-tune priorities">
          <div className="grid gap-5 sm:grid-cols-2">
            {WEIGHTS.map((w) => (
              <label key={w.key} className="flex flex-col gap-3 text-sm">
                {w.label}
                <span className="flex items-center gap-4">
                  <input
                    type="range"
                    min={0}
                    max={10}
                    step={1}
                    value={weights[w.key]}
                    onChange={(e) => {
                      setFocus("custom");
                      setWeights((prev) => ({
                        ...prev,
                        [w.key]: Number(e.target.value),
                      }));
                    }}
                    className="w-full accent-[var(--canopy)]"
                  />
                  <span className="num">{weights[w.key]}</span>
                </span>
              </label>
            ))}
          </div>
        </Disclosure>
        <div className="mt-6">
          <Button
            variant="primary"
            loading={run.loading}
            disabled={allZero}
            onClick={rank}
          >
            Prioritize my shortlist
          </Button>
        </div>
        <p className="mt-4 text-xs text-text-3">
          Only your {items.length} saved projects are included. This organizes
          review; it does not approve funding or predict returns.
        </p>
      </div>
      {run.error ? (
        <ErrorState error={run.error} />
      ) : run.loading ? (
        <LoadingBlock rows={5} label="Organizing your shortlist" />
      ) : run.data ? (
        <>
          <ol className="flex flex-col gap-4">
            {run.data.items.map((item) => (
              <Item key={item.project_id} item={item} />
            ))}
          </ol>
          <Disclosure summary="How these priorities were calculated">
            <p className="mb-3 break-all text-xs">
              Methodology {run.data.methodology_version}. Ranking fingerprint{" "}
              {run.data.ranking_fingerprint}.
            </p>
            <Disclaimers items={run.data.disclaimers} />
          </Disclosure>
          <SourceNotice access={run.data.access} />
        </>
      ) : null}
    </div>
  );
}
