"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, invalidate } from "./api";

export type ApiState<T> = {
  data: T | null;
  error: ApiError | null;
  loading: boolean;
  reload: () => void;
};

export function asApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;
  return new ApiError("client_error", error instanceof Error ? error.message : String(error), 0);
}

type Settled<T> = { id: string | null; data: T | null; error: ApiError | null };

/**
 * Load data for a component. `key` identifies the request (null = do not load yet). The previous
 * request is aborted when the key changes or the component unmounts, so fast filter changes do
 * not pile up on the single-worker backend. Previous data stays visible while a new key loads.
 */
export function useApi<T>(key: string | null, load: (signal: AbortSignal) => Promise<T>): ApiState<T> {
  const [nonce, setNonce] = useState(0);
  const [settled, setSettled] = useState<Settled<T>>({ id: null, data: null, error: null });
  const loader = useRef(load);
  useEffect(() => {
    loader.current = load;
  });

  const id = key === null ? null : `${key}#${nonce}`;

  useEffect(() => {
    if (id === null) return;
    const controller = new AbortController();
    loader
      .current(controller.signal)
      .then((value) => {
        if (!controller.signal.aborted) setSettled({ id, data: value, error: null });
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        if (err instanceof DOMException && err.name === "AbortError") return;
        setSettled((prev) => ({ id, data: prev.data, error: asApiError(err) }));
      });
    return () => controller.abort();
  }, [id]);

  const reload = useCallback(() => {
    invalidate();
    setNonce((n) => n + 1);
  }, []);
  return {
    data: settled.data,
    error: settled.id === id ? settled.error : null,
    loading: id !== null && settled.id !== id,
    reload,
  };
}

/** Run a request (usually a POST) on demand. */
export function useAction<A extends unknown[], T>(run: (...args: A) => Promise<T>) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(false);
  const runner = useRef(run);
  useEffect(() => {
    runner.current = run;
  });
  const execute = useCallback(async (...args: A): Promise<T | null> => {
    setLoading(true);
    setError(null);
    try {
      const value = await runner.current(...args);
      setData(value);
      return value;
    } catch (err) {
      setError(asApiError(err));
      return null;
    } finally {
      setLoading(false);
    }
  }, []);
  const reset = useCallback(() => {
    setData(null);
    setError(null);
  }, []);
  return { data, error, loading, execute, reset };
}
