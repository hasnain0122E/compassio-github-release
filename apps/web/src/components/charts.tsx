"use client";

import { useId, useState } from "react";
import { compactAmount, exactAmount, integer } from "@/lib/format";

/* -------------------------------------------------------------------------------------------
 * Ranked bars (single series): magnitude per category. Values are the backend's exact strings;
 * Number() is used only to size the bar. An unavailable total is shown with its reason, never
 * as a zero-length bar.
 * ----------------------------------------------------------------------------------------- */
export type BarDatum = {
  key: string;
  label: string;
  value: string | null; // exact decimal string, or null when unavailable
  note?: string; // e.g. "12 records summed · 3 missing"
  unavailableReason?: string | null;
  onSelect?: () => void;
};

export function BarList({
  data,
  unitLabel,
  emptyText = "Nothing to show for this selection.",
}: {
  data: BarDatum[];
  unitLabel: string;
  emptyText?: string;
}) {
  const max = Math.max(0, ...data.map((d) => (d.value === null ? 0 : Math.abs(Number(d.value)))));
  if (!data.length) return <p className="text-sm text-text-3">{emptyText}</p>;
  return (
    <ol className="flex flex-col" aria-label={`Ranked values in ${unitLabel}`}>
      {data.map((d, i) => {
        const width = d.value === null || max === 0 ? 0 : Math.max(0.5, (Math.abs(Number(d.value)) / max) * 100);
        const Row = d.onSelect ? "button" : "div";
        return (
          <li key={d.key}>
            <Row
              {...(d.onSelect ? { type: "button" as const, onClick: d.onSelect } : {})}
              title={d.value === null ? (d.unavailableReason ?? "Unavailable") : `${unitLabel} ${exactAmount(d.value)}`}
              className={`grid w-full grid-cols-[1.5rem_minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 rounded-1 px-1 py-2 text-left text-sm sm:grid-cols-[1.5rem_minmax(0,11rem)_minmax(2rem,1fr)_auto] ${
                d.onSelect ? "hover:bg-panel-2" : ""
              }`}
            >
              <span className="num text-2xs text-text-3">{i + 1}</span>
              <span className="truncate" title={d.label}>
                {d.label}
              </span>
              <span data-chart-bar className="relative col-start-2 col-end-4 row-start-2 h-2 rounded-r-[4px] bg-grid/60 sm:col-auto sm:row-auto sm:h-3">
                {d.value !== null ? (
                  <span
                    className="absolute inset-y-0 left-0 rounded-r-[4px] bg-series-1"
                    style={{ width: `${width}%` }}
                  />
                ) : (
                  <span className="absolute inset-0 rounded-r-[4px] border border-dashed border-line-strong" />
                )}
              </span>
              <span className="num col-start-3 row-start-1 min-w-[6.5rem] text-right sm:col-auto sm:row-auto">
                {d.value === null ? (
                  <span className="text-xs text-caution">Unavailable</span>
                ) : (
                  <>
                    <span className="font-medium">
                      <span className="text-2xs font-normal text-text-3">{unitLabel} </span>
                      {compactAmount(d.value)}
                    </span>
                    {d.note ? <span className="block text-2xs text-text-3">{d.note}</span> : null}
                  </>
                )}
              </span>
            </Row>
          </li>
        );
      })}
    </ol>
  );
}

/* -------------------------------------------------------------------------------------------
 * Year columns: one bar per year that the backend returned. Missing years stay EMPTY (never
 * interpolated); unavailable years are marked with a dashed outline.
 * ----------------------------------------------------------------------------------------- */
export type YearDatum = {
  year: number;
  value: string | null;
  status: "available" | "unavailable";
  detail?: string;
};

export function YearColumns({ data, unitLabel, height = 200 }: { data: YearDatum[]; unitLabel: string; height?: number }) {
  const [active, setActive] = useState<number | null>(null);
  const titleId = useId();
  if (!data.length) return <p className="text-sm text-text-3">No dated records for this selection.</p>;
  const years = data.map((d) => d.year);
  const first = Math.min(...years);
  const last = Math.max(...years);
  const span = last - first + 1;
  const byYear = new Map(data.map((d) => [d.year, d]));
  const max = Math.max(0, ...data.map((d) => (d.value === null ? 0 : Number(d.value))));
  const W = Math.max(320, span * 22);
  const H = height;
  const pad = { l: 64, r: 8, t: 10, b: 22 };
  const slot = (W - pad.l - pad.r) / span;
  const barW = Math.max(3, Math.min(18, slot - 2));
  const y = (v: number) => pad.t + (H - pad.t - pad.b) * (1 - (max ? v / max : 0));
  const ticks = [0.5, 1].map((f) => f * max);
  const shown = active !== null ? byYear.get(active) : null;
  const labelEvery = span > 24 ? 5 : span > 12 ? 2 : 1;

  return (
    <figure aria-labelledby={titleId} className="flex flex-col gap-2">
      <figcaption id={titleId} className="sr-only">
        {unitLabel} by year, {first} to {last}. Years without a bar have no reported data.
      </figcaption>
      <div className="min-h-10 text-xs" aria-live="polite">
        {shown ? (
          <p>
            <span className="font-semibold">{shown.year}</span>{" "}
            {shown.value === null ? (
              <span className="text-caution">unavailable{shown.detail ? ` · ${shown.detail}` : ""}</span>
            ) : (
              <>
                <span className="num font-semibold">
                  {unitLabel} {exactAmount(shown.value)}
                </span>
                {shown.detail ? <span className="text-text-3"> · {shown.detail}</span> : null}
              </>
            )}
          </p>
        ) : active !== null ? (
          <p>
            <span className="font-semibold">{active}</span> <span className="text-text-3">no reported data</span>
          </p>
        ) : (
          <p className="text-text-3">Hover or focus a year for the exact value.</p>
        )}
      </div>
      <div className="overflow-x-auto">
        <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} role="img" aria-hidden className="max-w-none">
          {ticks.map((t) => (
            <g key={t}>
              <line x1={pad.l} x2={W - pad.r} y1={y(t)} y2={y(t)} stroke="var(--grid)" />
              <text x={pad.l - 6} y={y(t) + 3} textAnchor="end" fontSize="10" fill="var(--text-3)">
                {compactAmount(String(t))}
              </text>
            </g>
          ))}
          <line x1={pad.l} x2={W - pad.r} y1={y(0)} y2={y(0)} stroke="var(--line-strong)" />
          {Array.from({ length: span }, (_, i) => {
            const yr = first + i;
            const d = byYear.get(yr);
            const cx = pad.l + slot * i + slot / 2;
            const v = d && d.value !== null ? Number(d.value) : 0;
            const top = y(v);
            return (
              <g
                key={yr}
                tabIndex={0}
                role="button"
                aria-label={`${yr}: ${d ? (d.value === null ? "unavailable" : `${unitLabel} ${exactAmount(d.value)}`) : "no reported data"}`}
                onMouseEnter={() => setActive(yr)}
                onFocus={() => setActive(yr)}
                onMouseLeave={() => setActive(null)}
                onBlur={() => setActive(null)}
                className="cursor-default outline-none"
              >
                <rect x={cx - slot / 2} y={pad.t} width={slot} height={H - pad.t - pad.b} fill="transparent" />
                {d && d.value !== null && v > 0 ? (
                  <path
                    d={`M${cx - barW / 2},${y(0)} V${top + 3} Q${cx - barW / 2},${top} ${cx - barW / 2 + 3},${top} H${cx + barW / 2 - 3} Q${cx + barW / 2},${top} ${cx + barW / 2},${top + 3} V${y(0)} Z`}
                    fill={active === yr ? "var(--canopy)" : "var(--series-1)"}
                  />
                ) : null}
                {d && d.value === null ? (
                  <rect
                    x={cx - barW / 2}
                    y={y(0) - 14}
                    width={barW}
                    height={14}
                    fill="none"
                    stroke="var(--caution)"
                    strokeDasharray="2 2"
                  />
                ) : null}
                {i % labelEvery === 0 || yr === last ? (
                  <text x={cx} y={H - 6} textAnchor="middle" fontSize="10" fill="var(--text-3)">
                    {yr}
                  </text>
                ) : null}
              </g>
            );
          })}
        </svg>
      </div>
    </figure>
  );
}

export function YearTable({ data, unitLabel }: { data: YearDatum[]; unitLabel: string }) {
  return (
    <div className="max-h-72 overflow-auto">
      <table className="w-full text-sm">
        <caption className="sr-only">{unitLabel} by year</caption>
        <thead className="sticky top-0 bg-panel text-left text-xs text-text-3">
          <tr>
            <th className="py-1.5 pr-4 font-medium">Year</th>
            <th className="py-1.5 pr-4 text-right font-medium">{unitLabel}</th>
            <th className="py-1.5 font-medium">Detail</th>
          </tr>
        </thead>
        <tbody>
          {data.map((d) => (
            <tr key={d.year} className="border-t border-line">
              <td className="num py-1.5 pr-4">{d.year}</td>
              <td className="num py-1.5 pr-4 text-right">
                {d.value === null ? <span className="text-caution">Unavailable</span> : exactAmount(d.value)}
              </td>
              <td className="py-1.5 text-xs text-text-3">{d.detail}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* -------------------------------------------------------------------------------------------
 * Score dial: the compass motif. The needle bearing is the model score (0 = left, 1 = right);
 * the threshold is drawn as the decision bearing. It never shows a value the API did not return.
 * ----------------------------------------------------------------------------------------- */
export function ScoreDial({ score, threshold, label }: { score: number; threshold: number; label: string }) {
  const angle = (v: number) => -90 + Math.max(0, Math.min(1, v)) * 180; // degrees from north
  const point = (deg: number, r: number) => {
    const rad = (deg * Math.PI) / 180;
    return [100 + r * Math.sin(rad), 100 - r * Math.cos(rad)];
  };
  const [tx1, ty1] = point(angle(threshold), 62);
  const [tx2, ty2] = point(angle(threshold), 86);
  const arc = (from: number, to: number, r: number) => {
    const [x1, y1] = point(angle(from), r);
    const [x2, y2] = point(angle(to), r);
    return `M${x1},${y1} A${r},${r} 0 0 1 ${x2},${y2}`;
  };
  return (
    <svg viewBox="0 -16 200 132" role="img" aria-label={label} className="w-full max-w-xs">
      <path d={arc(0, threshold, 76)} fill="none" stroke="var(--grid)" strokeWidth="10" strokeLinecap="butt" />
      <path d={arc(threshold, 1, 76)} fill="none" stroke="var(--canopy-soft)" strokeWidth="10" />
      <line x1={tx1} y1={ty1} x2={tx2} y2={ty2} stroke="var(--text-2)" strokeWidth="2" />
      <text x={point(angle(threshold), 98)[0]} y={point(angle(threshold), 98)[1]} fontSize="9" textAnchor="middle" fill="var(--text-3)">
        threshold
      </text>
      <text x="22" y="112" fontSize="9" fill="var(--text-3)">
        0
      </text>
      <text x="172" y="112" fontSize="9" fill="var(--text-3)">
        1
      </text>
      <g style={{ ["--needle-from" as string]: "-90deg", ["--needle-to" as string]: `${angle(score)}deg`, transformOrigin: "100px 100px" }} className="needle-settle">
        <path d="M100 30 L106 100 L100 106 L94 100 Z" fill="var(--canopy)" />
        <path d="M100 30 L106 100 L100 100 Z" fill="var(--leaf)" />
      </g>
      <circle cx="100" cy="100" r="5" fill="var(--panel)" stroke="var(--canopy)" strokeWidth="2" />
    </svg>
  );
}

/* -------------------------------------------------------------------------------------------
 * Allocation strip: one single-hue segment per project with 2 px gaps, numbered; identity is
 * carried by the number and the table beside it (never colour alone).
 * ----------------------------------------------------------------------------------------- */
export function AllocationStrip({
  parts,
  unallocatedShare,
}: {
  parts: Array<{ key: string; n: number; share: number; label: string }>;
  unallocatedShare: number;
}) {
  return (
    <div className="flex h-9 w-full gap-[2px] overflow-hidden rounded-1" role="img" aria-label="Budget split by project">
      {parts.map((p) =>
        p.share > 0 ? (
          <div
            key={p.key}
            title={`${p.n}. ${p.label}: ${(p.share * 100).toFixed(2)}%`}
            className="flex min-w-0 items-center justify-center bg-series-1 text-2xs font-semibold text-white"
            style={{ flexGrow: p.share, flexBasis: 0 }}
          >
            {p.share > 0.04 ? p.n : ""}
          </div>
        ) : null,
      )}
      {unallocatedShare > 0 ? (
        <div
          title={`Unallocated: ${(unallocatedShare * 100).toFixed(2)}%`}
          className="flex min-w-0 items-center justify-center border border-dashed border-line-strong text-2xs text-text-3"
          style={{ flexGrow: unallocatedShare, flexBasis: 0 }}
        >
          {unallocatedShare > 0.08 ? "Unallocated" : ""}
        </div>
      ) : null}
    </div>
  );
}

export function CountBars({ data, total }: { data: Array<{ label: string; count: number }>; total?: number }) {
  const max = Math.max(1, ...data.map((d) => d.count));
  return (
    <ul className="flex flex-col gap-1.5">
      {data.map((d) => (
        <li key={d.label} className="grid grid-cols-[minmax(0,12rem)_1fr_auto] items-center gap-3 text-sm">
          <span className="truncate" title={d.label}>
            {d.label}
          </span>
          <span className="h-2.5 rounded-r-[4px] bg-grid/60">
            <span className="block h-full rounded-r-[4px] bg-series-1" style={{ width: `${(d.count / max) * 100}%` }} />
          </span>
          <span className="num text-right text-xs text-text-2">
            {integer(d.count)}
            {total ? <span className="text-text-3"> ({((d.count / total) * 100).toFixed(1)}%)</span> : null}
          </span>
        </li>
      ))}
    </ul>
  );
}
