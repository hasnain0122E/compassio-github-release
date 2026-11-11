"use client";

import Link from "next/link";
import { ChevronDown, CircleAlert, Info, Loader2, PlugZap, RotateCw, ShieldAlert, Timer } from "lucide-react";
import { useId } from "react";
import type { ApiError } from "@/lib/api";
import { API_BASE } from "@/lib/api";
import { buttonClass, inputClass, type ButtonVariant } from "./styles";

export { buttonClass, inputClass };
export { CompassMark } from "./brand";

export function Button({
  variant = "secondary",
  size = "md",
  loading = false,
  className = "",
  children,
  ...rest
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: "sm" | "md";
  loading?: boolean;
}) {
  return (
    <button
      type="button"
      {...rest}
      disabled={rest.disabled || loading}
      aria-busy={loading || undefined}
      className={`${buttonClass(variant, size)} ${className}`}
    >
      {loading ? <Loader2 aria-hidden className="size-4 animate-spin" /> : null}
      {children}
    </button>
  );
}

export function LinkButton({
  href,
  variant = "secondary",
  size = "md",
  className = "",
  children,
}: {
  href: string;
  variant?: ButtonVariant;
  size?: "sm" | "md";
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <Link href={href} className={`${buttonClass(variant, size)} ${className}`}>
      {children}
    </Link>
  );
}

type BadgeTone = "neutral" | "canopy" | "teal" | "caution" | "danger" | "info" | "outline";
const BADGE: Record<BadgeTone, string> = {
  neutral: "bg-panel-2 text-text-2",
  canopy: "bg-canopy-soft text-canopy",
  teal: "bg-info-soft text-info",
  caution: "bg-caution-soft text-caution",
  danger: "bg-danger-soft text-danger",
  info: "bg-info-soft text-info",
  outline: "border border-line-strong text-text-2",
};

export function Badge({
  tone = "neutral",
  children,
  title,
}: {
  tone?: BadgeTone;
  children: React.ReactNode;
  title?: string;
}) {
  return (
    <span
      title={title}
      className={`inline-flex max-w-full items-center gap-1 rounded-1 px-1.5 py-0.5 text-2xs font-medium leading-tight ${BADGE[tone]}`}
    >
      {children}
    </span>
  );
}

export function Panel({
  title,
  description,
  actions,
  children,
  className = "",
  bodyClass = "p-4 sm:p-5",
  as: Tag = "section",
}: {
  title?: React.ReactNode;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  bodyClass?: string;
  as?: "section" | "div" | "article";
}) {
  const id = useId();
  return (
    <Tag aria-labelledby={title ? id : undefined} className={`min-w-0 rounded-2 border border-line bg-panel ${className}`}>
      {title ? (
        <header className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-4 py-3 sm:px-5">
          <div className="min-w-0">
            <h2 id={id} className="text-base font-semibold">
              {title}
            </h2>
            {description ? <p className="mt-0.5 text-xs text-text-3">{description}</p> : null}
          </div>
          {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
        </header>
      ) : null}
      <div className={bodyClass}>{children}</div>
    </Tag>
  );
}

export function Stat({
  label,
  value,
  detail,
  emphasis = false,
}: {
  label: string;
  value: React.ReactNode;
  detail?: React.ReactNode;
  emphasis?: boolean;
}) {
  return (
    <div className={`flex flex-col gap-1 ${emphasis ? "" : ""}`}>
      <dt className="text-xs text-text-3">{label}</dt>
      <dd className={`num font-semibold leading-none ${emphasis ? "text-3xl" : "text-2xl"}`}>{value}</dd>
      {detail ? <dd className="text-xs text-text-3">{detail}</dd> : null}
    </div>
  );
}

export function Skeleton({ className = "h-4 w-full" }: { className?: string }) {
  return <span aria-hidden className={`skeleton block ${className}`} />;
}

export function LoadingBlock({ rows = 4, label = "Loading" }: { rows?: number; label?: string }) {
  return (
    <div role="status" aria-label={label} className="flex flex-col gap-3">
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className={`h-4 ${i % 3 === 2 ? "w-2/3" : "w-full"}`} />
      ))}
      <span className="sr-only">{label}…</span>
    </div>
  );
}

export function EmptyState({
  title,
  children,
  action,
}: {
  title: string;
  children?: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-start gap-2 rounded-2 border border-dashed border-line-strong px-5 py-8">
      <p className="font-semibold">{title}</p>
      {children ? <div className="max-w-prose text-sm text-text-2">{children}</div> : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}

/** Plain-language explanation of an API error, with the fix and a retry. */
export function ErrorState({ error, onRetry }: { error: ApiError; onRetry?: () => void }) {
  let Icon = CircleAlert;
  let title = "Something went wrong";
  let body: React.ReactNode = error.message;
  if (error.unreachable) {
    Icon = PlugZap;
    title = "The Compassio API is not running";
    body = (
      <>
        This page reads real data from the local API at <code className="text-xs">{API_BASE}</code>.
        Start it with <code className="text-xs">powershell -File scripts\start_api.ps1</code>, then retry.
      </>
    );
  } else if (error.code === "source_rights_not_cleared" || error.code === "event_access_local_only") {
    Icon = ShieldAlert;
    title = "This data is not available in the current access mode";
    body = (
      <>
        {error.message} Source records are served only in the authorized local demo mode. Public and
        production configurations refuse them by design.
      </>
    );
  } else if (error.code === "inference_not_authorized" || error.code === "ml_v2_demo_not_authorized") {
    Icon = ShieldAlert;
    title = "AI screening is switched off in this mode";
  } else if (error.code === "rate_limited") {
    Icon = Timer;
    title = "Too many requests";
    body = `${error.message} ${error.retryAfter ? `Try again in ${error.retryAfter} s.` : "Wait up to a minute, then try again."}`;
  } else if (error.code === "objective_not_supported") {
    title = "The data cannot support this objective";
  } else if (error.code === "candidate_set_too_large") {
    title = "Too many projects to rank at once";
  } else if (error.status === 404) {
    title = "Not found";
  } else if (error.status === 422) {
    title = "Please check the input";
    body = (
      <>
        {error.message}
        {error.fields.length ? ` (field: ${error.fields.join(", ")})` : ""}
      </>
    );
  } else if (error.status >= 500) {
    title = "The API could not complete the request";
  }
  return (
    <div role="alert" className="flex items-start gap-3 rounded-2 border border-danger/40 bg-danger-soft px-4 py-3">
      <Icon aria-hidden className="mt-0.5 size-5 shrink-0 text-danger" />
      <div className="min-w-0 flex-1">
        <p className="font-semibold text-text">{title}</p>
        <div className="mt-1 text-sm text-text-2">{body}</div>
        <p className="mt-1 text-2xs text-text-3">Code: {error.code}</p>
      </div>
      {onRetry ? (
        <Button size="sm" variant="secondary" onClick={onRetry}>
          <RotateCw aria-hidden className="size-3.5" /> Retry
        </Button>
      ) : null}
    </div>
  );
}

export function Note({
  tone = "info",
  children,
  title,
}: {
  tone?: "info" | "caution";
  children: React.ReactNode;
  title?: string;
}) {
  const cls = tone === "caution" ? "border-caution/40 bg-caution-soft" : "border-info/30 bg-info-soft";
  const Icon = tone === "caution" ? CircleAlert : Info;
  return (
    <div className={`flex gap-3 rounded-2 border px-4 py-3 text-sm ${cls}`}>
      <Icon aria-hidden className={`mt-0.5 size-4 shrink-0 ${tone === "caution" ? "text-caution" : "text-info"}`} />
      <div className="min-w-0 text-text-2">
        {title ? <p className="font-semibold text-text">{title}</p> : null}
        {children}
      </div>
    </div>
  );
}

/** Accessible disclosure built on <details>. */
export function Disclosure({
  summary,
  children,
  defaultOpen = false,
}: {
  summary: React.ReactNode;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  return (
    <details open={defaultOpen} className="group rounded-2 border border-line bg-panel">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-sm font-medium [&::-webkit-details-marker]:hidden">
        <span>{summary}</span>
        <ChevronDown aria-hidden className="size-4 shrink-0 text-text-3 transition-transform duration-[var(--dur-2)] group-open:rotate-180" />
      </summary>
      <div className="border-t border-line px-4 py-3 text-sm">{children}</div>
    </details>
  );
}

export function Field({
  label,
  hint,
  children,
  htmlFor,
}: {
  label: string;
  hint?: React.ReactNode;
  children: React.ReactNode;
  htmlFor: string;
}) {
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <label htmlFor={htmlFor} className="text-xs font-medium text-text-2">
        {label}
      </label>
      {children}
      {hint ? <p className="text-2xs text-text-3">{hint}</p> : null}
    </div>
  );
}

export function Tabs<T extends string>({
  tabs,
  value,
  onChange,
  label,
}: {
  tabs: Array<{ id: T; label: string }>;
  value: T;
  onChange: (id: T) => void;
  label: string;
}) {
  return (
    <div role="tablist" aria-label={label} className="-mb-px flex gap-1 overflow-x-auto border-b border-line">
      {tabs.map((t) => {
        const active = t.id === value;
        return (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(t.id)}
            onKeyDown={(event) => {
              const i = tabs.findIndex((x) => x.id === value);
              const next = event.key === "ArrowRight" ? (i + 1) % tabs.length
                : event.key === "ArrowLeft" ? (i - 1 + tabs.length) % tabs.length
                : event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : null;
              if (next === null) return;
              event.preventDefault();
              onChange(tabs[next].id);
              event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>('[role="tab"]')[next]?.focus();
            }}
            tabIndex={active ? 0 : -1}
            className={`whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium transition-colors ${
              active ? "border-canopy text-text" : "border-transparent text-text-3 hover:text-text"
            }`}
          >
            {t.label}
          </button>
        );
      })}
    </div>
  );
}

