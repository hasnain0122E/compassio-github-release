/**
 * Typed client for the Compassio API (contract: docs/api/openapi.json, types: ./api-types.ts).
 *
 * - One base URL (local only; override with NEXT_PUBLIC_COMPASSIO_API_URL). No production URL.
 * - Every error becomes an ApiError with the backend's `code` and `message` (or a network code).
 * - GET responses are cached for a few minutes and in-flight GETs are shared, so the frontend
 *   never floods the single-worker local backend.
 * - All money stays as the backend's decimal strings; this module never does arithmetic on it.
 */
import { DEMO_MODE } from "./demo-mode";
import type {
  ApprovedDisbursedResponse,
  ClimateDistributionResponse,
  CompareResponse,
  ComparisonResponse,
  CountryProfileResponse,
  CoverageResponse,
  EvidenceResponse,
  FiltersResponse,
  GroupedFundingResponse,
  InstitutionsResponse,
  MethodologyResponse,
  MetricsResponse,
  ModelsResponse,
  OverviewResponse,
  PrioritizeRequest,
  PrioritizeResponse,
  ProjectDetail,
  ProjectPage,
  ScenarioRequest,
  ScenarioResponse,
  ScreeningResponse,
  SourcesResponse,
  TextScreeningRequest,
  TrendsResponse,
} from "./api-types";

export const API_BASE = (
  DEMO_MODE ? "" : process.env.NEXT_PUBLIC_COMPASSIO_API_URL ?? "http://127.0.0.1:8000"
).replace(/\/$/, "");

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly retryAfter: number | null;
  readonly fields: string[];

  constructor(
    code: string,
    message: string,
    status: number,
    retryAfter: number | null = null,
    fields: string[] = [],
  ) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.retryAfter = retryAfter;
    this.fields = fields;
  }

  /** The backend is not running or not reachable. */
  get unreachable(): boolean {
    return this.code === "api_unreachable";
  }

  /** Data or inference refused by the access policy (not a bug). */
  get forbidden(): boolean {
    return this.status === 403;
  }
}

type Query = Record<string, string | number | boolean | null | undefined>;

export function buildQuery(query?: Query): string {
  if (!query) return "";
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === null || value === undefined || value === "") continue;
    params.set(key, String(value));
  }
  const text = params.toString();
  return text ? `?${text}` : "";
}

/** Convert an HTTP error body into an ApiError (exported for unit tests). */
export function toApiError(
  status: number,
  body: unknown,
  retryAfter: string | null,
): ApiError {
  const data = (body ?? {}) as {
    code?: unknown;
    message?: unknown;
    detail?: Array<{ loc?: unknown[]; msg?: string }>;
  };
  const fields = Array.isArray(data.detail)
    ? data.detail
        .map((d) => (Array.isArray(d.loc) ? d.loc.slice(1).join(".") : ""))
        .filter(Boolean)
    : [];
  const code = typeof data.code === "string" ? data.code : `http_${status}`;
  const message =
    typeof data.message === "string"
      ? data.message
      : `The API answered with HTTP ${status}.`;
  const seconds = retryAfter !== null ? Number.parseInt(retryAfter, 10) : NaN;
  return new ApiError(
    code,
    message,
    status,
    Number.isFinite(seconds) ? seconds : null,
    fields,
  );
}

const TTL_MS = 5 * 60 * 1000;
const cache = new Map<string, { at: number; value: unknown }>();
const inflight = new Map<string, Promise<unknown>>();

/**
 * At most MAX_CONCURRENT requests in flight. The local API runs one worker and its read-only
 * SQLite engine can close connections during concurrent requests. Serialize this local-demo
 * client's requests; see docs/frontend/product_ux_redesign.md for the observed QA limitation.
 */
export const MAX_CONCURRENT = 1;
let active = 0;
const waiting: Array<() => void> = [];

async function acquire(): Promise<void> {
  if (active < MAX_CONCURRENT) {
    active += 1;
    return;
  }
  await new Promise<void>((resolve) => waiting.push(resolve));
}

function release(): void {
  const next = waiting.shift();
  // Transfer the reserved slot directly; a new caller must not overtake the queue.
  if (next) next();
  else active -= 1;
}

async function send<T>(
  method: "GET" | "POST",
  path: string,
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  await acquire();
  try {
    return await sendNow<T>(method, path, body, signal);
  } finally {
    release();
  }
}

async function sendNow<T>(
  method: "GET" | "POST",
  path: string,
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  if (DEMO_MODE) {
    if (signal?.aborted) throw new DOMException("Aborted", "AbortError");
    const { demoRequest } = await import("./demo-provider");
    return demoRequest(path, body) as T;
  }
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      signal,
      headers:
        body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError")
      throw error;
    throw new ApiError(
      "api_unreachable",
      `The Compassio API is not reachable at ${API_BASE}. Start it with scripts\\start_api.ps1 and retry.`,
      0,
    );
  }
  const text = await response.text();
  let parsed: unknown = null;
  try {
    parsed = text ? JSON.parse(text) : null;
  } catch {
    parsed = null;
  }
  if (!response.ok) {
    throw toApiError(
      response.status,
      parsed,
      response.headers.get("Retry-After"),
    );
  }
  return parsed as T;
}

/** Cached, de-duplicated GET. The cache is shared by all components on the page. */
export function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  if (signal?.aborted)
    return Promise.reject(new DOMException("Aborted", "AbortError"));
  const hit = cache.get(path);
  if (hit && Date.now() - hit.at < TTL_MS)
    return Promise.resolve(hit.value as T);
  const running = inflight.get(path);
  // The shared request is not tied to one caller's signal; callers stop listening on abort.
  const request =
    (running as Promise<T> | undefined) ??
    send<T>("GET", path)
      .then((value) => {
        cache.set(path, { at: Date.now(), value });
        return value;
      })
      .finally(() => inflight.delete(path));
  inflight.set(path, request);
  if (!signal) return request;
  return new Promise<T>((resolve, reject) => {
    const abort = () => reject(new DOMException("Aborted", "AbortError"));
    signal.addEventListener("abort", abort, { once: true });
    request
      .then(resolve, reject)
      .finally(() => signal.removeEventListener("abort", abort));
  });
}

export function invalidate(prefix = ""): void {
  for (const key of cache.keys()) if (key.startsWith(prefix)) cache.delete(key);
}

export function post<T>(
  path: string,
  body: unknown,
  signal?: AbortSignal,
): Promise<T> {
  return send<T>("POST", path, body, signal);
}

const enc = encodeURIComponent;

export const api = {
  health: (s?: AbortSignal) =>
    get<{ status: string; version: string }>("/health", s),
  sources: (s?: AbortSignal) => get<SourcesResponse>("/api/v1/sources", s),
  filters: (s?: AbortSignal) => get<FiltersResponse>("/api/v1/filters", s),
  overview: (s?: AbortSignal) =>
    get<OverviewResponse>("/api/v1/analytics/overview", s),
  metrics: (s?: AbortSignal) =>
    get<MetricsResponse>("/api/v1/analytics/metrics", s),
  coverage: (s?: AbortSignal) =>
    get<CoverageResponse>("/api/v1/analytics/coverage", s),
  trends: (
    q: {
      metric: string;
      country?: string;
      year_from?: number;
      year_to?: number;
    },
    s?: AbortSignal,
  ) => get<TrendsResponse>(`/api/v1/analytics/trends${buildQuery(q)}`, s),
  fundingBy: (
    dimension: "country" | "sector",
    q: { metric: string; year_from?: number; year_to?: number; limit?: number },
    s?: AbortSignal,
  ) =>
    get<GroupedFundingResponse>(
      `/api/v1/analytics/funding-by-${dimension}${buildQuery(q)}`,
      s,
    ),
  institutions: (q: { country?: string; limit?: number }, s?: AbortSignal) =>
    get<InstitutionsResponse>(
      `/api/v1/analytics/institutions${buildQuery(q)}`,
      s,
    ),
  approvedVsDisbursed: (q: { country?: string }, s?: AbortSignal) =>
    get<ApprovedDisbursedResponse>(
      `/api/v1/analytics/approved-vs-disbursed${buildQuery(q)}`,
      s,
    ),
  climateDistribution: (q: { country?: string }, s?: AbortSignal) =>
    get<ClimateDistributionResponse>(
      `/api/v1/analytics/climate-distribution${buildQuery(q)}`,
      s,
    ),
  countryProfile: (iso3: string, s?: AbortSignal) =>
    get<CountryProfileResponse>(
      `/api/v1/analytics/country-profile/${enc(iso3)}`,
      s,
    ),
  projects: (q: Query, s?: AbortSignal) =>
    get<ProjectPage>(`/api/v1/projects${buildQuery(q)}`, s),
  project: (id: string, s?: AbortSignal) =>
    get<ProjectDetail>(`/api/v1/projects/${enc(id)}`, s),
  evidence: (id: string, s?: AbortSignal) =>
    get<EvidenceResponse>(`/api/v1/decision/evidence/${enc(id)}`, s),
  methodology: (s?: AbortSignal) =>
    get<MethodologyResponse>("/api/v1/decision/methodology", s),
  models: (s?: AbortSignal) => get<ModelsResponse>("/api/v1/models", s),
  modelComparison: (s?: AbortSignal) =>
    get<ComparisonResponse>("/api/v1/models/comparison", s),
  compare: (ids: string[], s?: AbortSignal) =>
    post<CompareResponse>("/api/v1/decision/compare", { project_ids: ids }, s),
  prioritize: (body: PrioritizeRequest, s?: AbortSignal) =>
    post<PrioritizeResponse>("/api/v1/decision/prioritize", body, s),
  scenario: (body: ScenarioRequest, s?: AbortSignal) =>
    post<ScenarioResponse>("/api/v1/decision/scenarios", body, s),
  screenText: (body: TextScreeningRequest, s?: AbortSignal) =>
    post<ScreeningResponse>("/api/v1/screening/text", body, s),
  screenProject: (
    id: string,
    body: { model?: "default" | "ml_v1" | "ml_v2"; top_k?: number },
    s?: AbortSignal,
  ) =>
    post<ScreeningResponse>(`/api/v1/screening/projects/${enc(id)}`, body, s),
};
