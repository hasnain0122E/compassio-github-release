"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import {
  Brain,
  CheckCircle2,
  CircleDashed,
  ExternalLink,
  ArrowLeft,
  Bookmark,
} from "lucide-react";
import { Disclaimers, FactsTable } from "@/components/finance";
import {
  ClimateBadges,
  Countries,
  SelectToggle,
} from "@/components/project-bits";
import { PageBody, PageHeader } from "@/components/shell";
import {
  Disclosure,
  ErrorState,
  LinkButton,
  LoadingBlock,
} from "@/components/ui";
import { api } from "@/lib/api";
import type { ProjectDetail as Detail, ProjectEvidence } from "@/lib/api-types";
import { exactAmount, humanize, priceBasis, sourceText } from "@/lib/format";
import { SourceNotice } from "@/components/source-notice";
import { useSelection } from "@/lib/selection";
import { useToast } from "@/lib/toast";
import { useApi } from "@/lib/use-api";

const COMPLETENESS: Record<string, string> = {
  has_description: "Description",
  has_sector: "Sector",
  has_year: "Year",
  has_mapped_country: "Mapped country",
  has_source_status: "Status from the source",
  has_institution: "Institution",
  has_reported_amount: "A reported amount",
  has_amount_with_currency: "An amount with currency",
  has_dated_amount: "A dated amount",
  has_documents: "Linked documents",
  has_verified_approval: "Verified approval (GCF API)",
};

function Completeness({ ev }: { ev: ProjectEvidence }) {
  const entries = Object.entries(COMPLETENESS);
  const present = entries.filter(
    ([k]) => ev.completeness[k as keyof typeof ev.completeness] === true,
  ).length;
  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm">
        <span className="num font-semibold">{present}</span> of {entries.length}{" "}
        evidence items present
      </p>
      <ul className="grid gap-1.5 text-sm sm:grid-cols-2">
        {entries.map(([k, label]) => {
          const ok =
            ev.completeness[k as keyof typeof ev.completeness] === true;
          return (
            <li
              key={k}
              className={`flex items-center gap-2 ${ok ? "" : "text-text-3"}`}
            >
              {ok ? (
                <CheckCircle2 aria-hidden className="size-4 text-leaf" />
              ) : (
                <CircleDashed aria-hidden className="size-4" />
              )}
              <span>{label}</span>
              <span className="sr-only">{ok ? "present" : "missing"}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function Observations({ project }: { project: Detail }) {
  const rows = project.financial_observations;
  if (!rows.length)
    return <p className="text-sm text-text-3">No raw observations.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[40rem] text-xs">
        <caption className="sr-only">
          Raw financial observations as stored
        </caption>
        <thead className="text-left text-text-3">
          <tr className="border-b border-line">
            <th className="py-1.5 pr-3 font-medium">Observation</th>
            <th className="py-1.5 pr-3 font-medium">Status</th>
            <th className="py-1.5 pr-3 text-right font-medium">Amount</th>
            <th className="py-1.5 pr-3 font-medium">Basis</th>
            <th className="py-1.5 font-medium">Date</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((o) => (
            <tr
              key={o.observation_key}
              className="border-b border-line last:border-0"
            >
              <td className="py-1.5 pr-3">
                {o.metric_label}
                {o.is_component ? (
                  <span className="text-text-3"> · component line</span>
                ) : null}
              </td>
              <td className="py-1.5 pr-3">{humanize(o.value_status)}</td>
              <td className="num py-1.5 pr-3 text-right">
                {o.amount === null ? (
                  <span className="text-text-3">
                    {o.raw_value ? `raw “${o.raw_value}”` : "Not reported"}
                  </span>
                ) : (
                  `${o.currency ?? "Currency not stated"} ${exactAmount(o.amount)} ${o.unit ?? "(unit not stated)"}`
                )}
              </td>
              <td className="py-1.5 pr-3">{priceBasis(o.price_basis)}</td>
              <td className="py-1.5">
                {o.effective_date ?? o.effective_year ?? "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ProjectDetailView() {
  const params = useParams<{ id: string }>();
  const id = decodeURIComponent(params.id);
  const detail = useApi(`project:${id}`, (s) => api.project(id, s));
  const evidence = useApi(`evidence:${id}`, (s) => api.evidence(id, s));
  const { has, toggle } = useSelection();
  const toast = useToast();
  const p = detail.data;
  const ev = evidence.data?.project;
  if (detail.error)
    return (
      <>
        <PageHeader title="Project unavailable" />
        <PageBody>
          <ErrorState error={detail.error} onRetry={detail.reload} />
          <LinkButton href="/projects">Back to Discover</LinkButton>
        </PageBody>
      </>
    );
  if (!p || detail.loading)
    return (
      <>
        <PageHeader title="Opening project" />
        <PageBody>
          <LoadingBlock rows={6} />
        </PageBody>
      </>
    );
  const compare = () => {
    if (!has(p.id)) {
      const state = toggle({
        id: p.id,
        title: p.title,
        sourceId: p.source.source_id,
      });
      if (state === "full")
        toast(
          "Your shortlist has 10 projects. Remove one before adding this project.",
          "caution",
        );
    }
  };
  const facts = (ev?.headline_facts ?? []).filter((f) => f.is_funding_flow);
  const labels: Record<string, string> = {
    historical_commitment: "Historical commitment",
    approval: "Approved funding",
    disbursement: "Reported disbursement",
    co_financing: "Reported co-financing",
    total_project_cost: "Reported project cost",
    readiness_grant: "Readiness grant",
    pledge_not_commitment: "Pledge (not a commitment)",
    repayment_not_funding: "Repayment (not funding)",
    deposit_into_fund: "Deposit into fund",
  };
  return (
    <>
      <PageHeader
        title={sourceText(p.title)}
        description={
          <span className="text-sm">
            <Countries countries={p.countries} multi={p.multi_country} />{" "}
            {p.sector_name ? ` / ${p.sector_name}` : ""}
          </span>
        }
        crumbs={[
          { href: "/projects", label: "Discover" },
          { label: "Understand this project" },
        ]}
      />
      <PageBody>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <Link
            href="/projects"
            className="inline-flex items-center gap-2 text-sm text-text-3"
          >
            <ArrowLeft aria-hidden className="size-4" />
            Back to Discover
          </Link>
          <div className="flex flex-wrap gap-3">
            <SelectToggle
              id={p.id}
              title={p.title}
              sourceId={p.source.source_id}
            />
            <Link
              href="/workspace"
              onClick={compare}
              className="inline-flex items-center gap-2 rounded-1 px-4 py-2 text-sm font-medium text-canopy"
            >
              Compare with another project
            </Link>
          </div>
        </div>
        <div className="grid items-start gap-8 xl:grid-cols-[minmax(0,1fr)_20rem]">
          <div className="flex min-w-0 flex-col gap-8">
            <section className="story-section">
              <p className="section-step">01 / THE PROJECT</p>
              <h2 className="mb-4 text-2xl font-semibold">
                What is this project?
              </h2>
              <p className="max-w-[72ch] text-base leading-relaxed text-text-2">
                {p.description
                  ? sourceText(p.description).slice(0, 650)
                  : "This source does not provide a project description. The available evidence is shown below."}
                {p.description && p.description.length > 650 ? "..." : ""}
              </p>
              {p.description && p.description.length > 650 ? (
                <div className="mt-4">
                  <Disclosure summary="Read full project description">
                    <p className="whitespace-pre-line leading-relaxed">
                      {sourceText(p.description)}
                    </p>
                  </Disclosure>
                </div>
              ) : null}
            </section>
            <section className="story-section">
              <p className="section-step">02 / CLIMATE RELEVANCE</p>
              <h2 className="mb-4 text-2xl font-semibold">
                Could it support climate goals?
              </h2>
              <ClimateBadges annotations={p.climate_annotations} />
              <p className="mt-4 text-sm leading-relaxed text-text-2">
                {ev?.climate_relevance.statement ||
                  "These source annotations are a starting point for review, not proof of environmental outcomes."}
              </p>
              {p.source.source_id === "aiddata" ? (
                <LinkButton
                  href={`/screening?project=${encodeURIComponent(p.id)}`}
                  variant="secondary"
                  className="mt-5"
                >
                  <Brain aria-hidden className="size-4" />
                  Analyze climate relevance
                </LinkButton>
              ) : (
                <p className="mt-4 text-xs text-text-3">
                  Source evidence is available here. This source is not
                  authorized for automated AI screening.
                </p>
              )}
            </section>
            <section className="story-section">
              <p className="section-step">03 / FUNDING EVIDENCE</p>
              <h2 className="mb-2 text-2xl font-semibold">
                What do we know about its funding?
              </h2>
              <p className="mb-6 text-sm text-text-3">
                Historical figures, not money available to apply for. Each keeps
                its own meaning and basis.
              </p>
              {evidence.error ? (
                <ErrorState error={evidence.error} onRetry={evidence.reload} />
              ) : !ev ? (
                <LoadingBlock rows={3} />
              ) : !facts.length ? (
                <p className="text-text-2">
                  No comparable funding amount is reported. This is missing
                  information, not zero funding.
                </p>
              ) : (
                <div className="grid gap-4 sm:grid-cols-2">
                  {facts.slice(0, 3).map((f) => (
                    <div
                      key={f.fact_id}
                      className="funding-fact rounded-2 bg-panel-2 p-5"
                    >
                      <p className="text-sm text-text-2">
                        {labels[f.financial_meaning] ?? f.meaning_label}
                      </p>
                      <p className="num my-3 break-words text-2xl font-semibold">
                        {f.amount_in_units === null
                          ? "Not reported"
                          : `${f.currency ?? "Currency not stated"} ${exactAmount(f.amount_in_units)}`}
                      </p>
                      <p className="text-xs text-text-3">
                        {priceBasis(f.price_basis)} / {humanize(f.level)}
                        {f.year ? ` / ${f.year}` : ""}
                      </p>
                      {f.multi_country ? (
                        <p className="mt-2 text-xs text-caution">
                          Whole multi-country value, not a country allocation.
                        </p>
                      ) : null}
                      {f.recommended_for_aggregates === false ? (
                        <p className="mt-2 text-xs text-caution">
                          Source does not recommend this figure for totals.
                        </p>
                      ) : null}
                    </div>
                  ))}
                </div>
              )}
              {facts.length > 3 ? (
                <p className="mt-3 text-xs text-text-3">
                  More financial observations are available in the evidence
                  below.
                </p>
              ) : null}
              {p.group ? (
                <p className="mt-5 rounded-1 bg-caution-soft p-3 text-sm text-caution">
                  Related funding package: this record belongs to a group of{" "}
                  {p.group.member_count}. Do not add related records without
                  checking the evidence.
                </p>
              ) : null}
            </section>
            <Disclosure summary="View evidence and sources">
              <div className="flex min-w-0 flex-col gap-6">
                <div>
                  <h3 className="mb-2 font-semibold">Source and provenance</h3>
                  <p>
                    {p.source.name} / {p.source.publisher}
                  </p>
                  <p className="mt-2 break-all text-xs text-text-3">
                    {p.id} / {p.source_reference}
                  </p>
                  <p className="mt-2 text-xs">
                    Rights review: {humanize(p.source.rights_status)}
                  </p>
                  {p.source.reference_url ? (
                    <a
                      href={p.source.reference_url}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-3 inline-flex items-center gap-2 text-canopy"
                    >
                      Visit source <ExternalLink className="size-3" />
                    </a>
                  ) : null}
                </div>
                {ev ? (
                  <>
                    <FactsTable
                      facts={ev.headline_facts}
                      caption="Headline financial figures"
                    />
                    {ev.breakdown_facts.length ? (
                      <Disclosure summary="Instruments and country breakdown">
                        <FactsTable
                          facts={ev.breakdown_facts}
                          caption="Breakdown lines"
                        />
                      </Disclosure>
                    ) : null}
                    <Completeness ev={ev} />
                    {ev.linked_records.length ? (
                      <div>
                        <h3 className="mb-2 font-semibold">Related records</h3>
                        {ev.linked_records.map((r) => (
                          <p key={r.project_id} className="mb-3">
                            <Link
                              href={`/projects/${encodeURIComponent(r.project_id)}`}
                              className="text-canopy underline"
                            >
                              {r.title}
                            </Link>
                            <span className="block text-xs text-text-3">
                              {r.double_counting_rule}
                            </span>
                          </p>
                        ))}
                      </div>
                    ) : null}
                    {ev.documents.length ? (
                      <div>
                        <h3 className="font-semibold">Project documents</h3>
                        {ev.documents.map((d) => (
                          <p key={d.document_id} className="mt-2">
                            {d.catalogue_url ? (
                              <a
                                href={d.catalogue_url}
                                target="_blank"
                                rel="noreferrer"
                                className="text-canopy underline"
                              >
                                {d.title}
                              </a>
                            ) : (
                              d.title
                            )}
                          </p>
                        ))}
                      </div>
                    ) : null}
                  </>
                ) : null}
                <Disclosure
                  summary={`Raw observations as stored (${p.financial_observations.length})`}
                >
                  <Observations project={p} />
                </Disclosure>
                <div>
                  <h3 className="mb-2 font-semibold">
                    Limitations to keep in mind
                  </h3>
                  <ul className="list-disc space-y-2 pl-5 text-sm text-text-2">
                    {p.data_quality_warnings.map((w) => (
                      <li key={`${w.code}-${w.field}`}>{w.message}</li>
                    ))}
                    {ev?.limitations.map((l) => (
                      <li key={l}>{l}</li>
                    ))}
                  </ul>
                </div>
                <Disclaimers
                  items={[
                    ...p.disclaimers,
                    ...(evidence.data?.disclaimers ?? []),
                  ]}
                />
              </div>
            </Disclosure>
          </div>
          <aside className="project-card p-6 xl:sticky xl:top-8">
            <Bookmark aria-hidden className="mb-5 size-6 text-canopy" />
            <h2 className="text-lg font-semibold">Worth a closer look?</h2>
            <p className="mb-6 mt-3 text-sm leading-relaxed text-text-2">
              Keep this project in your shortlist. Compare the evidence before
              deciding what to investigate next.
            </p>
            <SelectToggle
              id={p.id}
              title={p.title}
              sourceId={p.source.source_id}
            />
            <dl className="mt-7 space-y-4 border-t border-line/60 pt-5 text-sm">
              <div>
                <dt className="text-xs text-text-3">Published by</dt>
                <dd>{p.source.publisher}</dd>
              </div>
              <div>
                <dt className="text-xs text-text-3">Status at source</dt>
                <dd>{p.status ?? "Not stated"}</dd>
              </div>
              <div>
                <dt className="text-xs text-text-3">Year</dt>
                <dd>{p.year ?? "Not reported"}</dd>
              </div>
            </dl>
          </aside>
        </div>
        <SourceNotice access={p.access} attribution={p.source.name} />
      </PageBody>
    </>
  );
}
