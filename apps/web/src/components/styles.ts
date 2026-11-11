/** Server-safe class helpers (no React hooks), shared by server and client components. */

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

const BUTTON: Record<ButtonVariant, string> = {
  primary: "bg-canopy text-on-canopy hover:bg-canopy-hover disabled:opacity-50",
  secondary: "border border-line-strong bg-panel text-text hover:bg-panel-2 disabled:opacity-50",
  ghost: "text-text-2 hover:bg-panel-2 hover:text-text disabled:opacity-50",
  danger: "border border-danger text-danger hover:bg-danger-soft",
};

export function buttonClass(variant: ButtonVariant = "secondary", size: "sm" | "md" = "md"): string {
  const pad = size === "sm" ? "h-8 px-3 text-xs" : "h-10 px-4 text-sm";
  return `inline-flex items-center justify-center gap-2 rounded-1 font-medium whitespace-nowrap transition-colors duration-[var(--dur-1)] disabled:cursor-not-allowed ${pad} ${BUTTON[variant]}`;
}


export const inputClass =
  "h-10 w-full min-w-0 rounded-1 border border-line-strong bg-panel px-3 text-sm text-text placeholder:text-text-3 focus-visible:border-focus";
