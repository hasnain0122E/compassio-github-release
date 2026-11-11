"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import {
  ArrowUpRight,
  ChevronLeft,
  ChevronRight,
  Search,
  SlidersHorizontal,
  X,
  Leaf,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Countries, SelectToggle } from "@/components/project-bits";
import { SourceNotice } from "@/components/source-notice";
import {
  Button,
  EmptyState,
  ErrorState,
  Field,
  LoadingBlock,
  inputClass,
} from "@/components/ui";
import { api } from "@/lib/api";
import { integer, sourceText } from "@/lib/format";
import { sourceName } from "@/lib/labels";
import { useApi } from "@/lib/use-api";

const KEYS = [
  "q",
  "country",
  "source",
  "sector",
  "year_from",
  "year_to",
  "climate_related",
  "sort",
  "page",
] as const;
type Key = (typeof KEYS)[number];
const SORTS: Record<string, string> = {
  id: "Source order",
  "-id": "Reverse source order",
  year: "Oldest first",
  "-year": "Newest first",
  title: "Title A-Z",
  "-title": "Title Z-A",
};
const EXAMPLES = [
  ["Flood protection", "flood"],
  ["Clean energy", "solar"],
  ["Water management", "water"],
  ["Climate-resilient farming", "irrigation"],
];

export function Explorer() {
  const params = useSearchParams();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const drawer = useRef<HTMLDialogElement>(null);
  const searchInput = useRef<HTMLInputElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const value = (key: Key) => params.get(key) ?? "";
  const set = (patch: Partial<Record<Key, string>>, reset = true) => {
    if ("q" in patch && timer.current) clearTimeout(timer.current);
    const next = new URLSearchParams(window.location.search);
    for (const [key, v] of Object.entries(patch)) {
      if (v) next.set(key, v);
      else next.delete(key);
    }
    if (reset && !("page" in patch)) next.delete("page");
    window.history.replaceState(
      null,
      "",
      `${pathname}${next.size ? `?${next}` : ""}`,
    );
  };
  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );
  useEffect(() => {
    const el = drawer.current;
    if (open && !el?.open) el?.showModal();
    if (!open && el?.open) el.close();
  }, [open]);
  useEffect(() => {
    if (searchInput.current) searchInput.current.value = params.get("q") ?? "";
  }, [params]);
  const filters = useApi("filters", (s) => api.filters(s));
  const query = useMemo(
    () =>
      Object.fromEntries([
        ["page_size", "12"],
        ...KEYS.filter((k) => params.get(k)).map((k) => [k, params.get(k)!]),
      ]),
    [params],
  );
  const results = useApi(`discover:${new URLSearchParams(query)}`, (s) =>
    api.projects(query, s),
  );
  const data = results.data;
  const countries = [...(filters.data?.countries ?? [])].sort((a, b) =>
    a.name.localeCompare(b.name),
  );
  const sectors = [
    ...new Set(
      (filters.data?.sectors ?? [])
        .filter((s) => !value("source") || s.source_id === value("source"))
        .map((s) => s.sector_name),
    ),
  ].sort();
  const active = KEYS.filter((k) => k !== "page" && value(k));
  const reset = () => {
    if (timer.current) clearTimeout(timer.current);
    window.history.replaceState(null, "", pathname);
  };
  const chip = (key: Key) =>
    key === "country"
      ? (countries.find((c) => c.iso3 === value(key))?.name ?? value(key))
      : key === "source"
        ? sourceName(value(key))
        : key === "climate_related"
          ? value(key) === "true"
            ? "Climate research label"
            : "No climate research label"
          : key === "sort"
            ? SORTS[value(key)]
            : key === "year_from"
              ? `From ${value(key)}`
              : key === "year_to"
                ? `Until ${value(key)}`
                : value(key);

  return (
    <div className="flex flex-col gap-8">
      <section aria-label="Find projects" className="discovery-search">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (timer.current) clearTimeout(timer.current);
            set({
              q: String(new FormData(e.currentTarget).get("q") ?? "").trim(),
            });
          }}
        >
          <label htmlFor="f-q" className="sr-only">
            Search projects by keyword
          </label>
          <div className="flex items-center gap-3 rounded-3 bg-panel p-2 pl-5 shadow-[var(--shadow-pop)] focus-within:ring-2 focus-within:ring-focus">
            <Search aria-hidden className="size-5 shrink-0 text-canopy" />
            <input
              ref={searchInput}
              id="f-q"
              name="q"
              defaultValue={value("q")}
              maxLength={200}
              placeholder="Search floods, clean energy, water, farming..."
              className="h-12 w-full min-w-0 bg-transparent text-base outline-none"
              onChange={(e) => {
                const q = e.target.value;
                if (timer.current) clearTimeout(timer.current);
                timer.current = setTimeout(() => set({ q: q.trim() }), 500);
              }}
            />
            <Button type="submit" variant="primary" className="shrink-0">
              Search
            </Button>
          </div>
        </form>
        <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-text-3">
          <span className="mr-1">Try a topic</span>
          {EXAMPLES.map(([label, q]) => (
            <button
              type="button"
              key={q}
              onClick={() => set({ q })}
              className="topic-chip"
            >
              {label}
            </button>
          ))}
        </div>
        <p className="mt-3 text-xs text-text-3">
          Keyword search across project titles and descriptions.
        </p>
      </section>
      <section aria-label="Filters" className="flex flex-col gap-4">
        <div className="grid grid-cols-2 items-end gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
          <Field label="Country" htmlFor="f-country">
            <select
              id="f-country"
              value={value("country")}
              onChange={(e) => set({ country: e.target.value })}
              className={inputClass}
            >
              <option value="">Anywhere</option>
              {countries.map((c) => (
                <option key={c.iso3} value={c.iso3}>
                  {c.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Topic / sector" htmlFor="f-sector">
            <select
              id="f-sector"
              value={value("sector")}
              onChange={(e) => set({ sector: e.target.value })}
              className={inputClass}
              disabled={!sectors.length}
            >
              <option value="">All available topics</option>
              {sectors.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </Field>
          <Button
            className="col-span-2 sm:col-span-1"
            onClick={() => setOpen(true)}
          >
            <SlidersHorizontal aria-hidden className="size-4" /> More filters
          </Button>
        </div>
        {active.length ? (
          <div className="flex flex-wrap items-center gap-2">
            {active.map((k) => (
              <button
                type="button"
                key={k}
                onClick={() => set({ [k]: "" })}
                className="flex max-w-full items-center gap-2 rounded-full bg-canopy-soft px-3 py-1.5 text-xs text-canopy"
              >
                <span className="truncate">{chip(k)}</span>
                <X
                  aria-label={`Remove ${k} filter`}
                  className="size-3 shrink-0"
                />
              </button>
            ))}
            <button
              type="button"
              onClick={reset}
              className="px-2 text-xs text-text-3 underline underline-offset-4"
            >
              Reset
            </button>
          </div>
        ) : null}
      </section>
      <dialog
        ref={drawer}
        onClose={() => setOpen(false)}
        aria-label="More filters"
        className="filter-drawer m-0 ml-auto h-dvh max-h-dvh w-[min(28rem,100vw)] bg-panel p-6 text-text backdrop:bg-ink/50"
      >
        <div className="mb-8 flex items-center justify-between">
          <h2 className="text-xl font-semibold">Refine your search</h2>
          <Button
            aria-label="Close filters"
            variant="ghost"
            onClick={() => setOpen(false)}
          >
            <X className="size-5" />
          </Button>
        </div>
        <div className="flex flex-col gap-6">
          <Field label="Source" htmlFor="f-source">
            <select
              id="f-source"
              className={inputClass}
              value={value("source")}
              onChange={(e) => set({ source: e.target.value, sector: "" })}
            >
              <option value="">All sources</option>
              {filters.data?.sources.map((s) => (
                <option key={s} value={s}>
                  {sourceName(s)}
                </option>
              ))}
            </select>
          </Field>
          <div className="grid grid-cols-2 gap-3">
            {(
              [
                ["year_from", "Year from", "f-yf"],
                ["year_to", "Year to", "f-yt"],
              ] as const
            ).map(([key, label, id]) => (
              <Field key={key} label={label} htmlFor={id}>
                <input
                  id={id}
                  type="number"
                  min={1900}
                  max={2100}
                  value={value(key)}
                  onChange={(e) => set({ [key]: e.target.value })}
                  className={inputClass}
                />
              </Field>
            ))}
          </div>
          <Field
            label="Available research climate label"
            htmlFor="f-climate"
            hint="Applies to AidData research annotations, not AI predictions."
          >
            <select
              id="f-climate"
              value={value("climate_related")}
              onChange={(e) => set({ climate_related: e.target.value })}
              className={inputClass}
            >
              <option value="">Any label</option>
              <option value="true">Climate-related</option>
              <option value="false">Not climate-related</option>
            </select>
          </Field>
          <Field label="Sort results" htmlFor="f-sort">
            <select
              id="f-sort"
              value={value("sort") || "id"}
              onChange={(e) => set({ sort: e.target.value })}
              className={inputClass}
            >
              {Object.entries(SORTS).map(([v, label]) => (
                <option key={v} value={v}>
                  {label}
                </option>
              ))}
            </select>
          </Field>
          <Button variant="primary" onClick={() => setOpen(false)}>
            Show projects
          </Button>
          <Button variant="ghost" onClick={reset}>
            Reset filters
          </Button>
        </div>
      </dialog>
      {filters.error && !results.error ? (
        <ErrorState
          error={filters.error}
          onRetry={() => {
            filters.reload();
            results.reload();
          }}
        />
      ) : null}
      <section
        aria-label="Projects"
        aria-busy={results.loading}
        className="flex flex-col gap-4"
      >
        <div className="flex items-center justify-between">
          <p className="text-sm text-text-3" aria-live="polite">
            {data
              ? `${integer(data.pagination.total_items)} results`
              : "Finding projects..."}
          </p>
          <span className="text-xs text-text-3">
            Discover. Understand. Shortlist.
          </span>
        </div>
        {results.error ? (
          <ErrorState
            error={results.error}
            onRetry={() => {
              filters.reload();
              results.reload();
            }}
          />
        ) : !data || results.loading ? (
          <LoadingBlock rows={5} label="Finding projects" />
        ) : !data.items.length ? (
          <EmptyState
            title="Let's try a broader search"
            action={<Button onClick={reset}>Reset search</Button>}
          >
            Try one keyword, such as flood or solar, or remove a filter. Some
            sources do not publish topic labels.
          </EmptyState>
        ) : (
          <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
            {data.items.map((p) => (
              <article
                key={p.id}
                className="project-card flex min-w-0 flex-col gap-4 p-6 sm:p-7"
              >
                <div className="flex items-center justify-between gap-3 text-xs text-text-3">
                  <span className="min-w-0 truncate">
                    <Countries
                      countries={p.countries}
                      multi={p.multi_country}
                    />
                  </span>
                  <span className="shrink-0">{p.year}</span>
                </div>
                <h2 className="line-clamp-2 text-lg font-semibold leading-snug">
                  <Link
                    href={`/projects/${encodeURIComponent(p.id)}`}
                    className="hover:text-canopy"
                  >
                    {sourceText(p.title)}
                  </Link>
                </h2>
                <p className="line-clamp-2 text-sm leading-relaxed text-text-2">
                  {sourceText(p.description_excerpt) ||
                    "Open this project to explore the available funding and source evidence."}
                </p>
                <div className="mt-auto flex flex-wrap items-center gap-2 text-xs text-text-3">
                  {p.sector_name ? (
                    <span className="max-w-full truncate rounded-full bg-panel-2 px-3 py-1">
                      {p.sector_name}
                    </span>
                  ) : null}
                  {p.climate_annotations.length ? (
                    <span className="flex items-center gap-1.5 text-canopy">
                      <Leaf aria-hidden className="size-3.5" />
                      {p.climate_annotations.some(
                        (a) => a.is_climate_related === true,
                      )
                        ? "Climate research label"
                        : p.climate_annotations.some(
                              (a) => a.kind !== "research_annotation",
                            )
                          ? "Source climate classification"
                          : "Research annotation available"}
                    </span>
                  ) : (
                    <span>Climate evidence not yet assessed</span>
                  )}
                </div>
                <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line/60 pt-4">
                  <Link
                    href={`/projects/${encodeURIComponent(p.id)}`}
                    className="inline-flex items-center gap-2 text-sm font-semibold text-canopy"
                  >
                    View project <ArrowUpRight aria-hidden className="size-4" />
                  </Link>
                  <SelectToggle
                    id={p.id}
                    title={p.title}
                    sourceId={p.source_id}
                  />
                </div>
                <p className="text-2xs text-text-3">
                  {sourceName(p.source_id)}
                </p>
              </article>
            ))}
          </div>
        )}
        {data && data.pagination.total_pages > 1 ? (
          <nav
            aria-label="Result pages"
            className="mt-3 flex items-center justify-between gap-3"
          >
            <p className="text-xs text-text-3">
              Page {data.pagination.page} of{" "}
              {integer(data.pagination.total_pages)}
            </p>
            <div className="flex gap-2">
              <Button
                aria-label="Previous page"
                disabled={data.pagination.page <= 1 || results.loading}
                onClick={() =>
                  set({ page: String(data.pagination.page - 1) }, false)
                }
              >
                <ChevronLeft className="size-4" />
              </Button>
              <Button
                aria-label="Next page"
                disabled={
                  data.pagination.page >= data.pagination.total_pages ||
                  results.loading
                }
                onClick={() =>
                  set({ page: String(data.pagination.page + 1) }, false)
                }
              >
                <ChevronRight className="size-4" />
              </Button>
            </div>
          </nav>
        ) : null}
      </section>
      <SourceNotice
        access={data?.access}
        attribution="AidData, Green Climate Fund, Climate Funds Update and ADB"
      />
    </div>
  );
}
