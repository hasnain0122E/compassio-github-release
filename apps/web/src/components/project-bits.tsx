"use client";

import { Check, Plus } from "lucide-react";
import type { AnnotationOut, CountryOut } from "@/lib/api-types";
import { humanize } from "@/lib/format";
import { MAX_SELECTION, useSelection } from "@/lib/selection";
import { useToast } from "@/lib/toast";
import { Badge, buttonClass } from "./ui";

/** Climate information as the SOURCE states it (never a model prediction). */
export function ClimateBadges({
  annotations,
}: {
  annotations: AnnotationOut[];
}) {
  if (!annotations.length)
    return <span className="text-2xs text-text-3">No climate label</span>;
  return (
    <span className="flex flex-wrap gap-1">
      {annotations.map((a) => {
        if (a.kind === "research_annotation") {
          return a.is_climate_related ? (
            <Badge
              key={a.scheme}
              tone="canopy"
              title={`Research annotation (${a.scheme}): ${a.raw_value ?? ""}`}
            >
              Climate-related · research label
            </Badge>
          ) : (
            <Badge
              key={a.scheme}
              tone="neutral"
              title={`Research annotation (${a.scheme}): ${a.raw_value ?? ""}`}
            >
              Not climate · research label
            </Badge>
          );
        }
        return (
          <Badge
            key={a.scheme}
            tone="teal"
            title={`Source classification (${a.scheme})`}
          >
            {a.label ?? humanize(a.raw_value)} · fund theme
          </Badge>
        );
      })}
    </span>
  );
}

export function Countries({
  countries,
  multi,
}: {
  countries: CountryOut[];
  multi: boolean;
}) {
  if (!countries.length) return <span className="text-text-3">No country</span>;
  const names = countries.map((c) => c.country_name);
  const shown = names.slice(0, 2).join(", ");
  return (
    <span title={names.join(", ")}>
      {shown}
      {names.length > 2 ? (
        <span className="text-text-3"> +{names.length - 2}</span>
      ) : null}
      {multi ? (
        <span className="ml-1">
          <Badge
            tone="outline"
            title="One value covers several countries; it is never split between them"
          >
            Multi-country
          </Badge>
        </span>
      ) : null}
    </span>
  );
}

export function SelectToggle({
  id,
  title,
  sourceId,
  compact = false,
}: {
  id: string;
  title: string;
  sourceId: string;
  compact?: boolean;
}) {
  const { has, toggle, items } = useSelection();
  const toast = useToast();
  const selected = has(id);
  const onClick = () => {
    const result = toggle({ id, title, sourceId });
    if (result === "full")
      toast(
        `You can compare at most ${MAX_SELECTION} projects. Remove one first.`,
        "caution",
      );
    else if (result === "added")
      toast(`Added to shortlist (${items.length + 1} selected)`, "success");
  };
  if (compact) {
    return (
      <button
        type="button"
        role="checkbox"
        aria-checked={selected}
        aria-label={`${selected ? "Remove" : "Add"} ${title} ${selected ? "from" : "to"} shortlist`}
        onClick={onClick}
        className={`flex size-6 items-center justify-center rounded-1 border transition-colors ${
          selected
            ? "border-canopy bg-canopy text-white"
            : "border-line-strong bg-panel hover:border-canopy"
        }`}
      >
        {selected ? <Check aria-hidden className="size-4" /> : null}
      </button>
    );
  }
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      className={buttonClass(selected ? "primary" : "secondary")}
    >
      {selected ? (
        <Check aria-hidden className="size-4" />
      ) : (
        <Plus aria-hidden className="size-4" />
      )}
      {selected ? "Shortlisted" : "Add to shortlist"}
    </button>
  );
}
