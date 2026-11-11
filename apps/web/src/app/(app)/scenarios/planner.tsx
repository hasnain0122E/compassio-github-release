"use client";

import Link from "next/link";
import { Calculator, Equal, Plus, TriangleAlert, X } from "lucide-react";
import { useMemo, useState } from "react";
import { AllocationStrip } from "@/components/charts";
import { SourceNotice } from "@/components/source-notice";
import {
  Badge,
  Button,
  Disclosure,
  EmptyState,
  ErrorState,
  Field,
  LinkButton,
  LoadingBlock,
  Note,
  Panel,
  inputClass,
} from "@/components/ui";
import { api } from "@/lib/api";
import type { ScenarioRequest, ScenarioResponse } from "@/lib/api-types";
import { exactAmount, fixed2, humanize } from "@/lib/format";
import { sourceName } from "@/lib/labels";
import { MAX_SELECTION, useSelection } from "@/lib/selection";
import { useToast } from "@/lib/toast";
import { useAction, useApi } from "@/lib/use-api";

type Method = NonNullable<ScenarioRequest["method"]>;

const METHOD_LABEL: Record<Method, string> = {
  equal: "Equal split",
  sector_priority: "By sector priority",
  priority_score: "By priority score",
};

function pctToDecimal(value: string): string | null {
  const n = Number(value);
  if (!value.trim() || !Number.isFinite(n)) return null;
  return String(n / 100);
}

function Result({ data }: { data: ScenarioResponse }) {
  const budget = data.budget;
  const unit = budget.unit && budget.unit !== "units" ? ` ${budget.unit}` : "";
  const total = Number(budget.amount);
  const parts = data.allocations.map((a, i) => ({
    key: a.project_id,
    n: i + 1,
    label: a.title,
    share: Number(a.share_of_budget),
  }));
  const unallocatedShare = total > 0 ? Number(data.unallocated) / total : 0;
  // A warning shown on every row is stated once above the table instead.
  const commonWarnings = new Set(
    (data.allocations[0]?.warnings ?? []).filter((w) =>
      data.allocations.every((a) => a.warnings.includes(w)),
    ),
  );
  const statusTone =
    data.status === "allocated"
      ? "canopy"
      : data.status === "partially_allocated"
        ? "caution"
        : "danger";
  return (
    <div className="flex flex-col gap-5">
      <div className="rounded-2 bg-ink p-5 text-ink-text">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={statusTone}>{humanize(data.status)}</Badge>
          <span className="text-xs text-ink-text-2">
            Hypothetical scenario
            {data.scenario_label ? `: ${data.scenario_label}` : ""}
          </span>
        </div>
        <div className="mt-4 grid items-center gap-3 text-center sm:grid-cols-[1fr_auto_1fr_auto_1fr]">
          <div>
            <p className="text-xs text-ink-text-2">Allocated</p>
            <p className="num text-2xl font-semibold text-white">
              {budget.currency} {fixed2(data.allocated_total)}
              {unit}
            </p>
          </div>
          <Plus aria-label="plus" className="mx-auto size-5 text-ink-text-2" />
          <div>
            <p className="text-xs text-ink-text-2">Unallocated</p>
            <p className="num text-2xl font-semibold text-white">
              {budget.currency} {fixed2(data.unallocated)}
              {unit}
            </p>
          </div>
          <Equal
            aria-label="equals"
            className="mx-auto size-5 text-ink-text-2"
          />
          <div>
            <p className="text-xs text-ink-text-2">Total budget</p>
            <p className="num text-2xl font-semibold text-[#7fd1a3]">
              {budget.currency} {fixed2(budget.amount)}
              {unit}
            </p>
          </div>
        </div>
        <p className="mt-4 text-center text-2xs text-ink-text-2">
          Server check: {data.conservation_check}
        </p>
      </div>

      <AllocationStrip parts={parts} unallocatedShare={unallocatedShare} />
      {commonWarnings.size ? (
        <ul className="flex list-disc flex-col gap-1 pl-5 text-xs text-text-2">
          {[...commonWarnings].map((w) => (
            <li key={w}>{w} (applies to every project)</li>
          ))}
        </ul>
      ) : null}

      <div className="overflow-x-auto rounded-2 border border-line bg-panel">
        <table className="w-full min-w-[46rem] text-sm">
          <caption className="sr-only">
            Hypothetical allocation per project
          </caption>
          <thead className="bg-panel-2 text-left text-xs text-text-3">
            <tr>
              <th className="px-3 py-2 font-medium">#</th>
              <th className="px-3 py-2 font-medium">Project</th>
              <th className="px-3 py-2 font-medium">Group</th>
              <th className="px-3 py-2 text-right font-medium">Weight</th>
              <th className="px-3 py-2 text-right font-medium">Allocation</th>
              <th className="px-3 py-2 text-right font-medium">Share</th>
              <th className="px-3 py-2 font-medium">Notes</th>
            </tr>
          </thead>
          <tbody>
            {data.allocations.map((a, i) => (
              <tr key={a.project_id} className="border-t border-line align-top">
                <td className="num px-3 py-2.5">{i + 1}</td>
                <td className="px-3 py-2.5">
                  <Link
                    href={`/projects/${encodeURIComponent(a.project_id)}`}
                    className="line-clamp-2 font-medium hover:text-canopy hover:underline"
                  >
                    {a.title}
                  </Link>
                  <span className="text-2xs text-text-3">
                    {sourceName(a.source_id)}
                  </span>
                </td>
                <td className="px-3 py-2.5 text-xs">
                  {a.sector ?? <span className="text-text-3">No sector</span>}
                  <span className="block text-text-3">{a.country_group}</span>
                </td>
                <td
                  className="num px-3 py-2.5 text-right text-xs"
                  title={a.weight_basis}
                >
                  {a.weight}
                </td>
                <td className="num whitespace-nowrap px-3 py-2.5 text-right font-medium">
                  {budget.currency} {fixed2(a.allocation)}
                </td>
                <td className="num px-3 py-2.5 text-right text-xs">
                  {(Number(a.share_of_budget) * 100).toFixed(2)}%
                </td>
                <td className="px-3 py-2.5 text-xs text-text-2">
                  {a.binding_constraints.map((c) => (
                    <Badge key={c} tone="caution">
                      {humanize(c)}
                    </Badge>
                  ))}
                  {a.warnings
                    .filter((w) => !commonWarnings.has(w))
                    .map((w) => (
                      <p key={w}>{w}</p>
                    ))}
                  <span className="block text-text-3">{a.weight_basis}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data.feasibility_warnings.length ? (
        <Note tone="caution" title="Feasibility warnings">
          <ul className="list-disc pl-5">
            {data.feasibility_warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </Note>
      ) : null}

      <Disclosure summary="Exact arithmetic, step by step">
        <ol className="num flex list-decimal flex-col gap-1 pl-5 text-xs text-text-2">
          {data.arithmetic.map((line, i) => (
            <li key={`${i}-${line}`}>{line}</li>
          ))}
        </ol>
      </Disclosure>
      <Disclosure summary="Assumptions and disclosures">
        <ul className="flex list-disc flex-col gap-1 pl-5 text-text-2">
          {[...data.assumptions, ...data.disclosures].map((x) => (
            <li key={x}>{x}</li>
          ))}
        </ul>
      </Disclosure>
      <p className="text-2xs text-text-3">
        Methodology {data.methodology_version} · request{" "}
        {data.request_sha256.slice(0, 12)} · result{" "}
        {data.result_sha256.slice(0, 12)} · data version{" "}
        {data.data_version.join(".")}. The same request always returns the same
        result.
      </p>
      <SourceNotice access={data.access} />
    </div>
  );
}

export function Planner() {
  const { items, remove, toggle } = useSelection();
  const toast = useToast();
  const methodology = useApi("methodology", (s) => api.methodology(s));
  const [amount, setAmount] = useState("1000000");
  const [currency, setCurrency] = useState("USD");
  const [unit, setUnit] = useState<"units" | "thousands" | "millions">("units");
  const [method, setMethod] = useState<Method>("equal");
  const [objective, setObjective] = useState("allocate_by_weights");
  const [label, setLabel] = useState("");
  const [minPer, setMinPer] = useState("");
  const [maxPer, setMaxPer] = useState("");
  const [maxSector, setMaxSector] = useState("");
  const [maxCountry, setMaxCountry] = useState("");
  const [sectorWeights, setSectorWeights] = useState<Record<string, string>>(
    {},
  );
  const [unlisted, setUnlisted] = useState("0");
  const [manual, setManual] = useState("");
  const ids = items.map((i) => i.id);

  // Sectors of the selected projects (for sector priorities), from their evidence.
  const sectorsKey =
    method === "sector_priority" && ids.length
      ? `sectors:${ids.join("|")}`
      : null;
  const sectors = useApi(sectorsKey, async (s) => {
    const evidence = await Promise.all(ids.map((id) => api.evidence(id, s)));
    return [
      ...new Set(
        evidence
          .map((e) => e.project.sector?.name)
          .filter((x): x is string => Boolean(x)),
      ),
    ].sort();
  });

  const run = useAction((body: ScenarioRequest) => api.scenario(body));
  const amountValid =
    /^\d+(\.\d{1,6})?$/.test(amount.trim()) && Number(amount) > 0;
  const currencyValid = /^[A-Z]{3}$/.test(currency);
  const constraintsValid =
    [minPer, maxPer].every(
      (v) => !v.trim() || /^\d+(\.\d{1,6})?$/.test(v.trim()),
    ) &&
    [maxSector, maxCountry].every(
      (v) => !v.trim() || (/^\d+(\.\d+)?$/.test(v.trim()) && Number(v) <= 100),
    );

  const body = useMemo<ScenarioRequest>(() => {
    const req: ScenarioRequest = {
      budget: { amount: amount.trim(), currency, unit },
      project_ids: ids,
      method,
      objective,
      constraints: {
        min_per_project: minPer.trim() || null,
        max_per_project: maxPer.trim() || null,
        max_share_per_sector: pctToDecimal(maxSector),
        max_share_per_country: pctToDecimal(maxCountry),
      },
      scenario_label: label.trim() || null,
    };
    if (method === "sector_priority") {
      req.sector_priorities = Object.fromEntries(
        Object.entries(sectorWeights)
          .filter(([, v]) => v.trim() !== "")
          .map(([k, v]) => [k, v]),
      );
      req.unlisted_sector_weight = unlisted || "0";
    }
    return req;
  }, [
    amount,
    currency,
    unit,
    ids,
    method,
    objective,
    minPer,
    maxPer,
    maxSector,
    maxCountry,
    label,
    sectorWeights,
    unlisted,
  ]);

  const addManual = async () => {
    const id = manual.trim();
    if (!id) return;
    try {
      const p = await api.project(id);
      if (
        toggle({ id: p.id, title: p.title, sourceId: p.source.source_id }) ===
        "full"
      ) {
        toast(`At most ${MAX_SELECTION} projects can be selected.`, "caution");
      }
      setManual("");
    } catch {
      toast(`No accessible project with id “${id}”.`, "danger");
    }
  };

  const objectives = [
    ...(methodology.data?.supported_objectives ?? ["allocate_by_weights"]).map(
      (o) => ({ id: o, supported: true, reason: "" }),
    ),
    ...Object.entries(methodology.data?.unsupported_objectives ?? {}).map(
      ([id, reason]) => ({ id, supported: false, reason }),
    ),
  ];
  const chosenObjective = objectives.find((o) => o.id === objective);

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-6 xl:grid-cols-[24rem_minmax(0,1fr)]">
      <form
        aria-label="Scenario inputs"
        onSubmit={(e) => {
          e.preventDefault();
          if (
            !ids.length ||
            !amountValid ||
            !currencyValid ||
            !constraintsValid
          )
            return;
          void run.execute(body);
        }}
        className="flex min-w-0 flex-col gap-4 self-start rounded-2 border border-line bg-panel p-4"
      >
        <p className="text-sm font-semibold">Budget</p>
        <div className="grid grid-cols-[1fr_5rem] gap-3">
          <Field
            label="Amount"
            htmlFor="b-amount"
            hint={
              amountValid ? undefined : "A positive number, up to 6 decimals"
            }
          >
            <input
              id="b-amount"
              inputMode="decimal"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              aria-invalid={!amountValid}
              className={inputClass}
            />
          </Field>
          <Field label="Currency" htmlFor="b-cur">
            <input
              id="b-cur"
              value={currency}
              maxLength={3}
              onChange={(e) => setCurrency(e.target.value.toUpperCase())}
              aria-invalid={!currencyValid}
              className={inputClass}
            />
          </Field>
        </div>
        <Field label="Unit" htmlFor="b-unit">
          <select
            id="b-unit"
            value={unit}
            onChange={(e) => setUnit(e.target.value as typeof unit)}
            className={inputClass}
          >
            <option value="units">Units</option>
            <option value="thousands">Thousands</option>
            <option value="millions">Millions</option>
          </select>
        </Field>

        <p className="mt-2 text-sm font-semibold">Projects ({items.length})</p>
        {items.length ? (
          <ul className="flex flex-col gap-1">
            {items.map((i) => (
              <li
                key={i.id}
                className="flex items-center justify-between gap-2 rounded-1 bg-panel-2 px-2.5 py-1.5 text-xs"
              >
                <span className="truncate" title={i.title}>
                  {i.title}
                </span>
                <button
                  type="button"
                  aria-label={`Remove ${i.title}`}
                  onClick={() => remove(i.id)}
                  className="rounded-1 p-1 text-text-3 hover:text-text"
                >
                  <X aria-hidden className="size-3.5" />
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-text-3">
            Choose projects in Discover to begin. Your shortlist will appear
            here.
          </p>
        )}
        <LinkButton href="/projects" size="sm" variant="ghost">
          Choose projects from Discover
        </LinkButton>
        <Disclosure summary="Add by source reference (advanced)">
          <div className="flex gap-2">
            <label htmlFor="sc-add" className="sr-only">
              Add a project by id
            </label>
            <input
              id="sc-add"
              value={manual}
              onChange={(e) => setManual(e.target.value)}
              placeholder="Add by id"
              className={inputClass}
            />
            <Button onClick={() => void addManual()}>Add</Button>
          </div>
        </Disclosure>
        <fieldset className="mt-2 flex flex-col gap-2">
          <legend className="mb-1 text-sm font-semibold">Method</legend>
          {(Object.keys(METHOD_LABEL) as Method[]).map((m) => (
            <label
              key={m}
              className={`flex cursor-pointer gap-2 rounded-1 border px-3 py-2 text-sm ${method === m ? "border-canopy bg-canopy-soft" : "border-line"}`}
            >
              <input
                type="radio"
                name="method"
                checked={method === m}
                onChange={() => setMethod(m)}
                className="mt-1"
              />
              <span>
                <span className="font-medium">{METHOD_LABEL[m]}</span>
                {methodology.data?.scenario_methods[m] ? (
                  <span className="block text-2xs text-text-3">
                    {methodology.data.scenario_methods[m]}
                  </span>
                ) : null}
              </span>
            </label>
          ))}
        </fieldset>

        {method === "sector_priority" ? (
          <div className="flex flex-col gap-2 rounded-1 border border-line p-3">
            <p className="text-xs font-medium">
              Sector priorities (relative weights)
            </p>
            {sectors.loading ? (
              <LoadingBlock rows={2} />
            ) : sectors.data && sectors.data.length ? (
              sectors.data.map((s) => (
                <div
                  key={s}
                  className="grid grid-cols-[1fr_5rem] items-center gap-2"
                >
                  <label
                    htmlFor={`sw-${s}`}
                    className="truncate text-xs"
                    title={s}
                  >
                    {s}
                  </label>
                  <input
                    id={`sw-${s}`}
                    inputMode="decimal"
                    value={sectorWeights[s] ?? ""}
                    onChange={(e) =>
                      setSectorWeights((p) => ({ ...p, [s]: e.target.value }))
                    }
                    className={inputClass}
                  />
                </div>
              ))
            ) : (
              <p className="text-xs text-text-3">
                The selected projects publish no sector names; use another
                method.
              </p>
            )}
            <Field
              label="Weight for projects without a listed sector"
              htmlFor="sw-unlisted"
            >
              <input
                id="sw-unlisted"
                inputMode="decimal"
                value={unlisted}
                onChange={(e) => setUnlisted(e.target.value)}
                className={inputClass}
              />
            </Field>
          </div>
        ) : null}

        <Disclosure summary="Constraints (optional)">
          <div className="grid grid-cols-2 gap-3">
            <Field label={`Min per project (${currency})`} htmlFor="c-min">
              <input
                id="c-min"
                inputMode="decimal"
                value={minPer}
                onChange={(e) => setMinPer(e.target.value)}
                className={inputClass}
              />
            </Field>
            <Field label={`Max per project (${currency})`} htmlFor="c-max">
              <input
                id="c-max"
                inputMode="decimal"
                value={maxPer}
                onChange={(e) => setMaxPer(e.target.value)}
                className={inputClass}
              />
            </Field>
            <Field label="Max share per sector (%)" htmlFor="c-sec">
              <input
                id="c-sec"
                inputMode="decimal"
                value={maxSector}
                onChange={(e) => setMaxSector(e.target.value)}
                className={inputClass}
              />
            </Field>
            <Field label="Max share per country (%)" htmlFor="c-cty">
              <input
                id="c-cty"
                inputMode="decimal"
                value={maxCountry}
                onChange={(e) => setMaxCountry(e.target.value)}
                className={inputClass}
              />
            </Field>
          </div>
        </Disclosure>

        <Disclosure summary="Advanced planning options">
          <Field
            label="Objective"
            htmlFor="b-obj"
            hint={
              chosenObjective && !chosenObjective.supported
                ? "Not supported by the data: the server will refuse it and say why."
                : undefined
            }
          >
            <select
              id="b-obj"
              value={objective}
              onChange={(e) => setObjective(e.target.value)}
              className={inputClass}
            >
              {objectives.map((o) => (
                <option key={o.id} value={o.id}>
                  {humanize(o.id)}
                  {o.supported ? "" : " (not supported)"}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Scenario name (optional)" htmlFor="b-label">
            <input
              id="b-label"
              value={label}
              maxLength={120}
              onChange={(e) => setLabel(e.target.value)}
              className={inputClass}
            />
          </Field>
        </Disclosure>
        {!constraintsValid ? (
          <p role="alert" className="text-xs text-danger">
            Use nonnegative amounts with up to six decimals and percentage caps
            between 0 and 100.
          </p>
        ) : null}
        <Button
          type="submit"
          variant="primary"
          loading={run.loading}
          disabled={
            !ids.length || !amountValid || !currencyValid || !constraintsValid
          }
        >
          <Calculator aria-hidden className="size-4" /> Run hypothetical
          scenario
        </Button>
      </form>

      <div className="flex min-w-0 flex-col gap-4" aria-live="polite">
        <Note tone="caution" title="Hypothetical planning only">
          A scenario shows how a budget you choose could be split under rules
          you choose. It is not approved, available, promised or executed
          funding, and it says nothing about returns or impact.
        </Note>
        {run.error ? (
          <ErrorState error={run.error} />
        ) : run.loading && !run.data ? (
          <LoadingBlock rows={8} label="Calculating" />
        ) : run.data ? (
          <Result data={run.data} />
        ) : !items.length ? (
          <EmptyState
            title="Choose projects to plan for"
            action={
              <LinkButton href="/projects" variant="primary">
                Open the explorer
              </LinkButton>
            }
          >
            Select up to 10 projects, set a budget and a method, then run. Every
            cent of the split is shown.
          </EmptyState>
        ) : (
          <Panel title="Ready to calculate">
            <p className="text-sm text-text-2">
              {items.length} projects selected · {METHOD_LABEL[method]} ·{" "}
              {currency} {amountValid ? exactAmount(amount) : "?"}
              {unit !== "units" ? ` ${unit}` : ""}.
            </p>
          </Panel>
        )}
        {methodology.data ? (
          <Disclosure summary="Objectives the data cannot support">
            <ul className="flex flex-col gap-1.5 text-text-2">
              {Object.entries(methodology.data.unsupported_objectives).map(
                ([id, reason]) => (
                  <li key={id} className="flex gap-2">
                    <TriangleAlert
                      aria-hidden
                      className="mt-0.5 size-3.5 shrink-0 text-caution"
                    />
                    <span>
                      <span className="font-medium text-text">
                        {humanize(id)}:
                      </span>{" "}
                      {reason}
                    </span>
                  </li>
                ),
              )}
            </ul>
          </Disclosure>
        ) : null}
      </div>
    </div>
  );
}
