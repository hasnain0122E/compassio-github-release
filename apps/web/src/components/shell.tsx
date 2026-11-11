"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  BarChart3,
  Brain,
  Calculator,
  ChevronRight,
  Command,
  FlaskConical,
  LayoutDashboard,
  Menu,
  Moon,
  Scale,
  Search,
  Sun,
  TableProperties,
  X,
} from "lucide-react";
import {
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import { api } from "@/lib/api";
import { NAV, type NavItem } from "@/lib/nav";
import { useSelection } from "@/lib/selection";
import { useApi } from "@/lib/use-api";
import { CompassMark, buttonClass } from "./ui";

const ICONS: Record<
  NavItem["icon"],
  React.ComponentType<{ className?: string; "aria-hidden"?: boolean }>
> = {
  dashboard: LayoutDashboard,
  projects: TableProperties,
  screening: Brain,
  analytics: BarChart3,
  workspace: Scale,
  scenarios: Calculator,
  challenges: FlaskConical,
};

function MoreTools({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <details className="mt-8 text-sm text-ink-text-2">
      <summary className="cursor-pointer px-3 py-2 text-xs">More tools</summary>
      <div className="mt-2 flex flex-col gap-1">
        <Link
          href="/analytics"
          onClick={onNavigate}
          className="rounded-1 px-3 py-2 hover:bg-ink-2"
        >
          Advanced insights
        </Link>
        <Link
          href="/scenarios"
          onClick={onNavigate}
          className="rounded-1 px-3 py-2 hover:bg-ink-2"
        >
          Hypothetical scenarios
        </Link>
      </div>
    </details>
  );
}

function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

/** Links without the active state: the prerendered fallback while the pathname streams in. */
function NavListPlain() {
  return (
    <ul className="flex flex-col gap-0.5">
      {NAV.map((item) => {
        const Icon = ICONS[item.icon];
        return (
          <li key={item.href}>
            <Link
              href={item.href}
              className="flex items-center gap-3 rounded-1 px-3 py-2 text-sm text-ink-text-2 hover:bg-ink-2/60 hover:text-white"
            >
              <Icon aria-hidden className="size-4 shrink-0" />
              {item.label}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

function NavList({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <Suspense fallback={<NavListPlain />}>
      <NavListActive onNavigate={onNavigate} />
    </Suspense>
  );
}

function NavListActive({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <ul className="flex flex-col gap-0.5">
      {NAV.map((item) => {
        const Icon = ICONS[item.icon];
        const active = isActive(pathname, item.href);
        return (
          <li key={item.href}>
            <Link
              href={item.href}
              onClick={onNavigate}
              aria-current={active ? "page" : undefined}
              className={`flex items-center gap-3 rounded-1 px-3 py-2 text-sm transition-colors ${
                active
                  ? "bg-ink-2 font-semibold text-white"
                  : "text-ink-text-2 hover:bg-ink-2/60 hover:text-white"
              }`}
            >
              <Icon aria-hidden className="size-4 shrink-0" />
              {item.label}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

const themeListeners = new Set<() => void>();

function effectiveTheme(): string {
  const set = document.documentElement.dataset.theme;
  if (set === "dark" || set === "light") return set;
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

function subscribeTheme(listener: () => void): () => void {
  themeListeners.add(listener);
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  media.addEventListener("change", listener);
  return () => {
    themeListeners.delete(listener);
    media.removeEventListener("change", listener);
  };
}

function useTheme(): [string, () => void] {
  const theme = useSyncExternalStore(
    subscribeTheme,
    effectiveTheme,
    () => "light",
  );
  const toggle = useCallback(() => {
    const next = effectiveTheme() === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try {
      window.localStorage.setItem("compassio.theme", next);
    } catch {
      /* ignore: the choice still applies to this page view */
    }
    themeListeners.forEach((l) => l());
  }, []);
  return [theme, toggle];
}

/** Live status from the API: data-access mode and the AI engine mode. */
function StatusBlock() {
  const models = useApi("models", (s) => api.models(s));
  const sources = useApi("sources", (s) => api.sources(s));
  const mode = sources.data?.access.mode;
  const op = models.data?.operational;
  const unreachable = models.error?.unreachable || sources.error?.unreachable;
  const modeText: Record<string, string> = {
    hackathon_event: "Event demo · this machine only",
    local_development: "Local research mode",
    public: "Public mode · source data off",
  };
  const engine =
    op?.mode === "authorized_local_demo"
      ? "ML v2 active · v1 fallback"
      : op?.mode === "standard_local_research"
        ? "ML v1 active"
        : op
          ? "AI screening off"
          : "…";
  return (
    <div className="rounded-2 border border-ink-2 px-3 py-2.5 text-2xs leading-relaxed text-ink-text-2">
      {unreachable ? (
        <p className="flex items-center gap-2 text-[#f3b6ae]">
          <span aria-hidden className="size-2 rounded-full bg-[#f08a80]" /> API
          not reachable
        </p>
      ) : (
        <>
          <p className="flex items-center gap-2 text-ink-text">
            <span
              aria-hidden
              className={`size-2 rounded-full ${mode && mode !== "public" ? "bg-[#7fd1a3]" : "bg-ink-text-2"}`}
            />
            {mode ? modeText[mode] : "Connecting…"}
          </p>
          <p className="mt-0.5 pl-4">{engine}</p>
        </>
      )}
    </div>
  );
}

function CommandPalette({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [index, setIndex] = useState(0);
  const dialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const el = dialog.current;
    if (!el) return;
    if (open && !el.open) {
      el.showModal();
      setQuery("");
      setIndex(0);
    }
    if (!open && el.open) el.close();
  }, [open]);

  const options = useMemo(() => {
    const q = query.trim().toLowerCase();
    const routes = NAV.filter(
      (n) => !q || `${n.label} ${n.description}`.toLowerCase().includes(q),
    ).map((n) => ({
      key: n.href,
      label: n.label,
      hint: n.description,
      go: () => router.push(n.href),
    }));
    if (q) {
      routes.unshift({
        key: "search",
        label: `Search projects for “${query.trim()}”`,
        hint: "Full-text search across titles and descriptions",
        go: () =>
          router.push(`/projects?q=${encodeURIComponent(query.trim())}`),
      });
      if (/^[a-z_]+:\S+$/i.test(query.trim())) {
        routes.unshift({
          key: "open",
          label: `Open project ${query.trim()}`,
          hint: "Project id (source:record)",
          go: () =>
            router.push(`/projects/${encodeURIComponent(query.trim())}`),
        });
      }
    }
    return routes;
  }, [query, router]);

  const choose = (i: number) => {
    const opt = options[i];
    if (!opt) return;
    opt.go();
    onClose();
  };

  return (
    <dialog
      ref={dialog}
      onClose={onClose}
      onClick={(e) => {
        if (e.target === dialog.current) onClose();
      }}
      aria-label="Command menu"
      className="m-auto mt-[12vh] w-[min(36rem,calc(100vw-2rem))] rounded-2 border border-line bg-panel p-0 text-text shadow-[var(--shadow-pop)] backdrop:bg-ink/50"
    >
      <div className="flex items-center gap-2 border-b border-line px-4">
        <Search aria-hidden className="size-4 text-text-3" />
        <input
          autoFocus
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setIndex(0);
          }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setIndex((i) => Math.min(i + 1, options.length - 1));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setIndex((i) => Math.max(i - 1, 0));
            } else if (e.key === "Enter") {
              e.preventDefault();
              choose(index);
            }
          }}
          placeholder="Go to a page, search projects, or paste a project id"
          aria-label="Command"
          className="h-12 flex-1 bg-transparent text-sm outline-none"
        />
      </div>
      <ul
        role="listbox"
        aria-label="Results"
        className="max-h-80 overflow-y-auto p-2"
      >
        {options.map((opt, i) => (
          <li key={opt.key} role="option" aria-selected={i === index}>
            <button
              type="button"
              onMouseEnter={() => setIndex(i)}
              onClick={() => choose(i)}
              className={`flex w-full flex-col items-start rounded-1 px-3 py-2 text-left ${
                i === index ? "bg-canopy-soft" : ""
              }`}
            >
              <span className="text-sm font-medium">{opt.label}</span>
              <span className="text-2xs text-text-3">{opt.hint}</span>
            </button>
          </li>
        ))}
      </ul>
    </dialog>
  );
}

function SelectionTray() {
  const { items, clear } = useSelection();
  const pathname = usePathname();
  if (
    !items.length ||
    pathname.startsWith("/workspace") ||
    pathname.startsWith("/scenarios")
  )
    return null;
  return (
    <div className="sticky bottom-0 z-30 border-t border-line bg-panel/95 px-4 py-3 backdrop-blur sm:px-8">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3">
        <p className="text-sm">
          <span className="num font-semibold">{items.length}</span> projects in
          your shortlist
          {items.length < 2 ? (
            <span className="text-text-3"> · select at least 2 to compare</span>
          ) : null}
        </p>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={clear}
            className={buttonClass("ghost", "sm")}
          >
            Clear
          </button>
          <Link
            href="/workspace"
            className={`${buttonClass("primary", "sm")} `}
          >
            View shortlist
          </Link>
        </div>
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [theme, toggleTheme] = useTheme();
  const menu = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    const el = menu.current;
    if (!el) return;
    if (menuOpen && !el.open) el.showModal();
    if (!menuOpen && el.open) el.close();
  }, [menuOpen]);

  const brand = (
    <Link href="/" className="flex items-center gap-2.5 text-white">
      <CompassMark className="size-7 text-white" />
      <span className="text-lg font-bold tracking-tight">Compassio</span>
    </Link>
  );

  return (
    <div className="product-app flex min-h-dvh">
      <a
        href="#main"
        className="sr-only z-50 rounded-1 bg-panel px-3 py-2 focus:not-sr-only focus:fixed focus:left-3 focus:top-3"
      >
        Skip to content
      </a>
      <aside className="sticky top-0 hidden h-dvh w-64 shrink-0 flex-col gap-6 bg-ink px-4 py-5 lg:flex">
        {brand}
        <button
          type="button"
          onClick={() => setPaletteOpen(true)}
          className="flex items-center justify-between rounded-1 border border-ink-2 px-3 py-2 text-xs text-ink-text-2 hover:text-white"
        >
          <span className="flex items-center gap-2">
            <Search aria-hidden className="size-3.5" /> Jump to…
          </span>
          <kbd className="flex items-center gap-0.5 text-2xs">
            <Command aria-hidden className="size-3" />K
          </kbd>
        </button>
        <nav aria-label="Main" className="flex-1">
          <NavList />
          <MoreTools />
        </nav>
        <details className="text-xs text-ink-text-2">
          <summary className="cursor-pointer py-2">
            Local demo · connection details
          </summary>
          <StatusBlock />
        </details>
        <button
          type="button"
          onClick={toggleTheme}
          className="flex items-center gap-2 text-xs text-ink-text-2 hover:text-white"
          aria-label="Switch colour theme"
        >
          {theme === "dark" ? (
            <Sun aria-hidden className="size-3.5" />
          ) : (
            <Moon aria-hidden className="size-3.5" />
          )}
          {theme === "dark" ? "Light theme" : "Dark theme"}
        </button>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex items-center justify-between gap-3 bg-ink px-4 py-3 lg:hidden">
          {brand}
          <div className="flex items-center gap-1">
            <button
              type="button"
              aria-label="Search"
              onClick={() => setPaletteOpen(true)}
              className="rounded-1 p-2 text-ink-text-2 hover:text-white"
            >
              <Search aria-hidden className="size-5" />
            </button>
            <button
              type="button"
              aria-label="Open menu"
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen(true)}
              className="rounded-1 p-2 text-ink-text-2 hover:text-white"
            >
              <Menu aria-hidden className="size-5" />
            </button>
          </div>
        </header>
        <dialog
          ref={menu}
          onClose={() => setMenuOpen(false)}
          aria-label="Menu"
          className="m-0 ml-auto h-dvh max-h-dvh w-[min(20rem,85vw)] bg-ink p-0 text-white backdrop:bg-ink/60"
        >
          <div className="flex h-full flex-col gap-6 px-4 py-4">
            <div className="flex items-center justify-between">
              {brand}
              <button
                type="button"
                aria-label="Close menu"
                onClick={() => setMenuOpen(false)}
                className="rounded-1 p-2 text-ink-text-2 hover:text-white"
              >
                <X aria-hidden className="size-5" />
              </button>
            </div>
            <nav aria-label="Main" className="flex-1">
              <NavList onNavigate={() => setMenuOpen(false)} />
              <MoreTools onNavigate={() => setMenuOpen(false)} />
            </nav>
            <details className="text-xs text-ink-text-2">
              <summary className="cursor-pointer py-2">
                Local demo · connection details
              </summary>
              <StatusBlock />
            </details>
            <button
              type="button"
              onClick={toggleTheme}
              className="text-left text-xs text-ink-text-2"
            >
              {theme === "dark" ? "Light theme" : "Dark theme"}
            </button>
          </div>
        </dialog>
        <main id="main" className="flex-1">
          {children}
        </main>
        <Suspense fallback={null}>
          <SelectionTray />
        </Suspense>
      </div>
      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
      />
    </div>
  );
}

export function PageHeader({
  title,
  description,
  crumbs = [],
  actions,
}: {
  title: React.ReactNode;
  description?: React.ReactNode;
  crumbs?: Array<{ href?: string; label: string }>;
  actions?: React.ReactNode;
}) {
  return (
    <div className="border-b border-line bg-panel">
      <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-6 sm:px-8 sm:py-8">
        {crumbs.length ? (
          <nav aria-label="Breadcrumb">
            <ol className="flex flex-wrap items-center gap-1 text-xs text-text-3">
              {crumbs.map((c, i) => (
                <li key={`${c.label}-${i}`} className="flex items-center gap-1">
                  {c.href ? (
                    <Link
                      href={c.href}
                      className="hover:text-text hover:underline"
                    >
                      {c.label}
                    </Link>
                  ) : (
                    <span aria-current="page" className="max-w-[40ch] truncate">
                      {c.label}
                    </span>
                  )}
                  {i < crumbs.length - 1 ? (
                    <ChevronRight aria-hidden className="size-3" />
                  ) : null}
                </li>
              ))}
            </ol>
          </nav>
        ) : null}
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="min-w-0 max-w-3xl">
            <h1
              className={`font-bold ${typeof title === "string" && title.length > 90 ? "text-xl sm:text-2xl" : "text-2xl sm:text-3xl"}`}
            >
              {title}
            </h1>
            {description ? (
              <p className="mt-2 text-text-2">{description}</p>
            ) : null}
          </div>
          {actions ? (
            <div className="flex flex-wrap gap-2">{actions}</div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export function PageBody({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`mx-auto flex max-w-7xl flex-col gap-6 px-4 py-6 sm:px-8 sm:py-8 ${className}`}
    >
      {children}
    </div>
  );
}
