"use client";

import { useCallback, useSyncExternalStore } from "react";

/**
 * The research tray: projects picked for comparison and scenarios (max 10). A tiny external store
 * persisted in localStorage, read with useSyncExternalStore (empty on the server).
 */
export const MAX_SELECTION = 10;
const STORAGE_KEY = "compassio.selection.v1";

export type SelectedProject = { id: string; title: string; sourceId: string };

const EMPTY: SelectedProject[] = [];
let items: SelectedProject[] | null = null;
const listeners = new Set<() => void>();

function parse(raw: string | null): SelectedProject[] {
  try {
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(parsed)) return EMPTY;
    return parsed
      .filter(
        (p): p is SelectedProject =>
          typeof p === "object" && p !== null && typeof (p as SelectedProject).id === "string",
      )
      .slice(0, MAX_SELECTION);
  } catch {
    return EMPTY;
  }
}

function snapshot(): SelectedProject[] {
  if (items === null) {
    try {
      items = parse(window.localStorage.getItem(STORAGE_KEY));
    } catch {
      items = EMPTY;
    }
  }
  return items;
}

function write(next: SelectedProject[]): void {
  items = next;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    /* storage unavailable (private mode): the selection still works for this page view */
  }
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  const onStorage = (event: StorageEvent) => {
    if (event.key === STORAGE_KEY) {
      items = parse(event.newValue);
      listener();
    }
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", onStorage);
  };
}

export function useSelection() {
  const current = useSyncExternalStore(subscribe, snapshot, () => EMPTY);
  const has = useCallback((id: string) => current.some((p) => p.id === id), [current]);
  const toggle = useCallback((item: SelectedProject): "added" | "removed" | "full" => {
    const now = snapshot();
    if (now.some((p) => p.id === item.id)) {
      write(now.filter((p) => p.id !== item.id));
      return "removed";
    }
    if (now.length >= MAX_SELECTION) return "full";
    write([...now, item]);
    return "added";
  }, []);
  const remove = useCallback((id: string) => write(snapshot().filter((p) => p.id !== id)), []);
  const clear = useCallback(() => write(EMPTY), []);
  const replace = useCallback((next: SelectedProject[]) => write(next.slice(0, MAX_SELECTION)), []);
  return { items: current, has, toggle, remove, clear, replace };
}

/** Kept for layout compatibility: the store needs no provider. */
export function SelectionProvider({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
