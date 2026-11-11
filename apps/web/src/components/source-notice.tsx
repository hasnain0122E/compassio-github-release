"use client";
import type { AccessNotice } from "@/lib/api-types";
import { ShieldCheck } from "lucide-react";
import { useState } from "react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";

export function SourceNotice({
  access,
  attribution,
}: {
  access?: AccessNotice;
  attribution?: string;
}) {
  const [open, setOpen] = useState(false);
  const sources = useApi(open ? "source-attributions" : null, (s) =>
    api.sources(s),
  );
  if (!access) return null;
  return (
    <details
      className="source-notice text-xs text-text-3"
      onToggle={(e) => setOpen(e.currentTarget.open)}
    >
      <summary className="flex cursor-pointer flex-wrap items-center gap-2 py-3">
        <ShieldCheck aria-hidden className="size-3.5" />
        <span>
          {access.mode === "public"
            ? "Public access"
            : access.mode === "hackathon_event"
              ? "Authorized local demo · sources not licence-cleared"
              : "Local research · sources not licence-cleared"}
        </span>
        {attribution ? <span>· {attribution}</span> : null}
        <span className="underline underline-offset-4">Source notice</span>
      </summary>
      <p className="max-w-4xl pb-4 leading-relaxed">{access.notice}</p>
      <p className="mb-3">
        AidData: Global Chinese Development Finance Dataset, Version 3.0 (ODC-By
        1.0); research annotations: Qi et al., Scientific Data 13, 277 (2026).
        GCF data: first published by the Green Climate Fund; no endorsement
        implied. Climate Funds Update: ODI / Heinrich Böll Stiftung. ADB: IATI.
        Source terms remain subject to review.
      </p>
      <ul className="space-y-3 pb-4">
        {sources.data?.sources
          .filter((s) => s.served_in_current_mode)
          .map((s) => (
            <li key={s.source_id}>
              {s.reference_url ? (
                <a
                  className="underline"
                  href={s.reference_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  {s.name}
                </a>
              ) : (
                s.name
              )}{" "}
              — {s.publisher}
              {s.license_notes ? <p>{s.license_notes}</p> : null}
            </li>
          ))}
      </ul>
    </details>
  );
}
