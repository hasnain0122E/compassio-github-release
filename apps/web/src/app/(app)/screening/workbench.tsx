"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Brain, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { ScoreDial } from "@/components/charts";
import { SourceNotice } from "@/components/source-notice";
import {
  Badge,
  Button,
  Disclosure,
  EmptyState,
  ErrorState,
  Field,
  LoadingBlock,
  inputClass,
} from "@/components/ui";
import { api } from "@/lib/api";
import { DEMO_MODE } from "@/lib/demo-mode";
import type {
  ComparisonResponse,
  ModelInfo,
  ModelsResponse,
  ScreeningResponse,
  WordContribution,
} from "@/lib/api-types";
import { humanize, integer, percent } from "@/lib/format";
import { BAND, sourceName } from "@/lib/labels";
import { useAction, useApi } from "@/lib/use-api";

type ModelChoice = "default" | "ml_v1" | "ml_v2";

/** Illustrative inputs written for the demo (not records from any source). */
const EXAMPLES: Array<{ label: string; title: string; description: string }> = [
  {
    label: "Farm water example",
    title: "Drip irrigation for drought-affected farms",
    description:
      "Install drip irrigation and rainwater harvesting so smallholder farmers can keep growing food through longer dry seasons.",
  },
  {
    label: "Flood example",
    title: "River embankments and early warning for flood-prone villages",
    description:
      "Strengthen river embankments, restore wetlands and set up a community flood early-warning system.",
  },
  {
    label: "Road example",
    title: "Rural road resurfacing",
    description:
      "Resurface 40 km of rural road and rebuild two bridges to improve market access.",
  },
];

function statusText(status: ModelInfo["status"]): string {
  if (DEMO_MODE) return "Illustrative demo rules";
  return status === "development_candidate"
    ? "Development candidate"
    : "Trusted research release";
}

/** Highlight words the model used, only where the API positions match the submitted text exactly. */
function Highlighted({
  text,
  words,
  field,
}: {
  text: string;
  words: WordContribution[];
  field: "title" | "description";
}) {
  const own = words
    .filter(
      (w) =>
        w.field === field &&
        text.slice(w.start, w.end).toLowerCase() === w.word.toLowerCase(),
    )
    .sort((a, b) => a.start - b.start);
  if (!text) return null;
  const parts: React.ReactNode[] = [];
  let at = 0;
  for (const w of own) {
    if (w.start < at) continue;
    parts.push(text.slice(at, w.start));
    parts.push(
      <mark
        key={`${w.start}-${w.word}`}
        title={`${w.contribution >= 0 ? "Pushed up" : "Pushed down"} by ${Math.abs(w.contribution).toFixed(2)}`}
        className={`rounded-[2px] px-0.5 ${
          w.contribution >= 0
            ? "bg-canopy-soft text-text underline decoration-leaf decoration-2 underline-offset-2"
            : "bg-transparent text-text-3 line-through decoration-series-2"
        }`}
      >
        {text.slice(w.start, w.end)}
      </mark>,
    );
    at = w.end;
  }
  parts.push(text.slice(at));
  return <span>{parts}</span>;
}

function WordBars({ words }: { words: WordContribution[] }) {
  const max = Math.max(0.0001, ...words.map((w) => Math.abs(w.contribution)));
  return (
    <ul className="flex flex-col gap-1">
      {words.map((w) => (
        <li
          key={`${w.field}-${w.start}-${w.word}`}
          className="grid grid-cols-[minmax(0,8rem)_1fr_1fr_3.5rem] items-center gap-2 text-xs"
        >
          <span className="truncate font-medium" title={w.word}>
            {w.word}
          </span>
          <span className="flex justify-end">
            {w.contribution < 0 ? (
              <span
                className="h-2 rounded-l-[4px] bg-series-2"
                style={{ width: `${(Math.abs(w.contribution) / max) * 100}%` }}
              />
            ) : null}
          </span>
          <span className="flex border-l border-line-strong">
            {w.contribution >= 0 ? (
              <span
                className="h-2 rounded-r-[4px] bg-leaf"
                style={{ width: `${(w.contribution / max) * 100}%` }}
              />
            ) : null}
          </span>
          <span className="num text-right text-text-2">
            {w.contribution >= 0 ? "+" : "−"}
            {Math.abs(w.contribution).toFixed(2)}
          </span>
        </li>
      ))}
    </ul>
  );
}

function ResultCard({
  result,
  title,
  description,
  other,
  onCompare,
  comparing,
}: {
  result: ScreeningResponse;
  title: string;
  description: string;
  other: ScreeningResponse | null;
  onCompare: (() => void) | null;
  comparing: boolean;
}) {
  const p = result.prediction;
  const words = result.explanation.top_words;
  const heading =
    p.band === "borderline"
      ? "A closer review would help"
      : p.is_climate_related
        ? "Potentially climate-related"
        : "No clear climate signal in this text";
  const shownTitle = result.source_evidence?.title ?? title;
  const shownDesc = result.source_evidence?.description ?? description;
  return (
    <div className="flex flex-col gap-6">
      <div>
        <span className="section-step">{DEMO_MODE ? "ILLUSTRATIVE SCREENING RESULTS" : "YOUR ANALYSIS"}</span>
        <h2 className="mt-3 text-2xl font-semibold">{heading}</h2>
        <p className="mt-3 text-sm leading-relaxed text-text-2">
          {BAND[p.band]?.body}
        </p>
      </div>
      <div className="rounded-2 bg-canopy-soft p-5">
        <div className="mb-3 flex items-end justify-between gap-3">
          <span className="text-sm text-text-2">Text relevance score</span>
          <span className="num text-3xl font-semibold text-canopy">
            {p.label_score.toFixed(3)}
          </span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-panel">
          <div
            className="h-full rounded-full bg-canopy"
            style={{ width: `${p.label_score * 100}%` }}
          />
        </div>
        <p className="mt-3 text-xs text-text-2">
          A screening signal, not a rating of impact or funding eligibility.
        </p>
      </div>
      {words.length ? (
        <div>
          <h3 className="mb-3 font-semibold">What influenced the result?</h3>
          <p className="text-sm leading-relaxed text-text-2">
            The model reacted to language such as{" "}
            {words
              .filter((w) => w.contribution > 0)
              .slice(0, 4)
              .map((w) => `“${w.word}”`)
              .join(", ") || "the words in your description"}
            . Read the project evidence before deciding what to review.
          </p>
        </div>
      ) : null}
      {result.source_evidence ? (
        <Link
          href={`/projects/${encodeURIComponent(result.source_evidence.project_id)}`}
          className="text-sm font-semibold text-canopy"
        >
          Return to project evidence
        </Link>
      ) : (
        <Link href="/projects" className="text-sm font-semibold text-canopy">
          Discover projects to investigate
        </Link>
      )}
      <Disclosure summary="Model details">
        <div className="flex flex-col gap-5">
          <p className="text-xs text-text-3">
            {result.model.engine_label} / {statusText(result.model.status)}
            {result.fallback_used ? " / fallback used" : ""}
          </p>
          <ScoreDial
            score={p.label_score}
            threshold={p.threshold}
            label={`Score ${p.label_score.toFixed(3)}; threshold ${p.threshold.toFixed(3)}`}
          />
          <p className="text-xs">
            Score {p.label_score.toFixed(3)} against decision threshold{" "}
            {p.threshold.toFixed(3)}. {p.is_climate_related ? "Above" : "Below"}{" "}
            {DEMO_MODE ? "the illustrative rule threshold." : "the frozen decision threshold."}
          </p>
          {result.source_evidence ? (
            <p className="break-words text-xs">
              Screened record: {result.source_evidence.project_id}.{" "}
              {sourceName(result.source_evidence.source_id)}.{" "}
              {result.source_evidence.source_reference}. Rights:{" "}
              {humanize(result.source_evidence.rights_status)}. Input
              permission: {result.source_evidence.model_input_permission}.
            </p>
          ) : null}
          <Disclosure summary="Detailed feature attributions">
            <WordBars words={words} />
            <p className="mt-3 text-xs">
              Faithfulness error:{" "}
              {result.explanation.faithfulness_abs_error.toExponential(1)}.
            </p>
            <p className="mt-4 font-medium">
              <Highlighted text={shownTitle} words={words} field="title" />
            </p>
            <p className="mt-2 whitespace-pre-line text-sm text-text-2">
              <Highlighted text={shownDesc} words={words} field="description" />
            </p>
          </Disclosure>
          {other ? (
            <div className="grid grid-cols-2 gap-3">
              {[result, other].map((r) => (
                <div key={r.model.model_key}>
                  <p className="text-xs">
                    {r.model.model_key === "ml_v2" ? "ML v2" : "ML v1"}
                  </p>
                  <p className="num mt-1 text-xl font-semibold">
                    {r.prediction.label_score.toFixed(3)}
                  </p>
                  <p className="text-xs text-text-3">
                    Threshold {r.prediction.threshold.toFixed(3)}
                  </p>
                </div>
              ))}
              <p className="col-span-2 text-xs text-text-3">
                Scores from different models are on different scales. Compare
                each with its own threshold.
              </p>
            </div>
          ) : onCompare ? (
            <Button onClick={onCompare} loading={comparing}>
              Compare with{" "}
              {result.model.model_key === "ml_v2" ? "ML v1" : "ML v2"}
            </Button>
          ) : null}
          <ul className="list-disc space-y-2 pl-5 text-xs text-text-2">
            {[...result.guidance, ...result.limitations].map((g) => (
              <li key={g}>{g}</li>
            ))}
            <li>Not predicted: {result.not_predicted.join("; ")}</li>
          </ul>
          <p className="break-all text-xs text-text-3">
            Input fingerprint {result.input_sha256}.{" "}
            {result.saved ? "Saved" : "Not stored"}.
          </p>
        </div>
      </Disclosure>
    </div>
  );
}

function ComparisonView({ data }: { data: ComparisonResponse }) {
  const rows: Array<[string, string]> = [
    ["average_precision", "Ranking quality (average precision)"],
    ["recall", "Climate projects found (recall)"],
    ["precision", "Flags that were right (precision)"],
    ["non_energy_recall", "Non-energy climate projects found"],
    ["adaptation_only_recall", "Adaptation-only projects found"],
    ["f1", "F1"],
  ];
  const ci = (key: string) => {
    const iv = data.ml_v2.intervals_95[key];
    return iv && iv[0] !== null && iv[1] !== null
      ? `${percent(iv[0])}–${percent(iv[1])}`
      : "";
  };
  const fp = data.false_positive_tradeoff;
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-text-2">{data.population_description}</p>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[32rem] text-sm">
          <caption className="sr-only">
            ML v1 versus ML v2 on the same validation records
          </caption>
          <thead className="text-left text-xs text-text-3">
            <tr className="border-b border-line">
              <th className="py-2 pr-3 font-medium">
                Same {integer(data.records)} records
              </th>
              <th className="py-2 pr-3 text-right font-medium">ML v1</th>
              <th className="py-2 pr-3 text-right font-medium">ML v2</th>
              <th className="py-2 text-right font-medium">
                ML v2 95% interval
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([key, label]) => (
              <tr key={key} className="border-b border-line last:border-0">
                <td className="py-2 pr-3">{label}</td>
                <td className="num py-2 pr-3 text-right text-text-2">
                  {percent(data.ml_v1.metrics[key])}
                </td>
                <td className="num py-2 pr-3 text-right font-semibold">
                  {percent(data.ml_v2.metrics[key])}
                </td>
                <td className="num py-2 text-right text-xs text-text-3">
                  {ci(key)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-sm">
        ML v2 finds{" "}
        <span className="num font-semibold">
          {integer(fp.additional_true_positives)}
        </span>{" "}
        more donor-marked climate projects than ML v1, and raises{" "}
        <span className="num font-semibold">
          {integer(fp.additional_false_positives)}
        </span>{" "}
        more false alarms (
        <span className="num">{integer(fp.ml_v2_false_positives)}</span> vs{" "}
        <span className="num">{integer(fp.ml_v1_false_positives)}</span>). Every
        flag still needs a person.
      </p>
      <ul className="flex list-disc flex-col gap-1 pl-5 text-xs text-text-3">
        {data.caveats.map((c) => (
          <li key={c}>{c}</li>
        ))}
      </ul>
      <p className="text-2xs text-text-3">Benchmark run {data.source_run_id}</p>
    </div>
  );
}

function ModelDetails({ models }: { models: ModelsResponse }) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {models.models.map((m) => (
        <dl
          key={m.model_key}
          className="flex flex-col gap-2 rounded-1 border border-line p-3 text-xs"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <dt className="sr-only">Model</dt>
            <dd className="text-sm font-semibold">{m.engine_label}</dd>
            <dd>
              <Badge
                tone={m.status === "development_candidate" ? "teal" : "outline"}
              >
                {statusText(m.status)}
              </Badge>
            </dd>
          </div>
          <div>
            <dt className="text-text-3">Version</dt>
            <dd className="break-all">{m.model_version}</dd>
          </div>
          <div>
            <dt className="text-text-3">How it reads text</dt>
            <dd>{m.representation}</dd>
          </div>
          <div>
            <dt className="text-text-3">Learned from</dt>
            <dd>{m.training_data}</dd>
          </div>
          <div>
            <dt className="text-text-3">Evaluated on</dt>
            <dd>
              {m.evaluation.population}
              {m.evaluation.independent_generalization_evidence
                ? " (one-shot held-out test)"
                : " (development validation used to select it; not independent)"}
            </dd>
          </div>
          <div>
            <dt className="text-text-3">Intended use</dt>
            <dd>{m.intended_use}</dd>
          </div>
          <div>
            <dt className="text-text-3">Artifact SHA-256</dt>
            <dd className="break-all text-text-3">{m.artifact_sha256}</dd>
          </div>
          <div>
            <dt className="text-text-3">Available now</dt>
            <dd>
              {m.selectable_now ? "Yes" : "No (not authorized in this mode)"}
            </dd>
          </div>
        </dl>
      ))}
    </div>
  );
}

export function ScreeningWorkspace() {
  const params = useSearchParams();
  const preset = params.get("project");
  const sources = useApi(preset ? "screening-source-access" : null, s => api.sources(s));
  const models = useApi("models", (s) => api.models(s));
  const [showDetails, setShowDetails] = useState(false);
  const comparison = useApi(showDetails ? "model-comparison" : null, (s) =>
    api.modelComparison(s),
  );
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [submitted, setSubmitted] = useState({ title: "", description: "" });
  const run = useAction(() =>
    preset
      ? api.screenProject(preset, { model: "default", top_k: 12 })
      : api.screenText({
          title: title.trim() || null,
          description: description.trim() || null,
          model: "default",
          top_k: 12,
        }),
  );
  const compare = useAction((choice: ModelChoice) =>
    run.data?.source_evidence
      ? api.screenProject(run.data.source_evidence.project_id, {
          model: choice,
          top_k: 12,
        })
      : api.screenText({
          title: submitted.title || null,
          description: submitted.description || null,
          model: choice,
          top_k: 12,
        }),
  );
  const ranPreset = useRef<string | null>(null);
  useEffect(() => {
    if (
      preset &&
      ranPreset.current !== preset &&
      models.data?.operational.inference_authorized
    ) {
      ranPreset.current = preset;
      void run.execute();
    }
  }, [preset, models.data, run]);
  const op = models.data?.operational;
  const otherKey: ModelChoice | null = run.data
    ? run.data.model.model_key === "ml_v2"
      ? "ml_v1"
      : models.data?.models.some(
            (m) => m.model_key === "ml_v2" && m.selectable_now,
          )
        ? "ml_v2"
        : null
    : null;
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!preset && !title.trim() && !description.trim()) return;
    compare.reset();
    setSubmitted({ title, description });
    await run.execute();
  };
  return (
    <div className="flex flex-col gap-8">
      <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="project-card p-6 sm:p-8">
          <p className="section-step">01 / DESCRIBE</p>
          <h2 className="mb-3 mt-2 text-xl font-semibold">
            Start with the project.
          </h2>
          <p className="mb-6 text-sm leading-relaxed text-text-2">
            Explore whether its description contains a climate-related signal. A
            person makes the final assessment.
          </p>
          {models.error ? (
            <ErrorState error={models.error} onRetry={models.reload} />
          ) : !op ? (
            <LoadingBlock rows={4} />
          ) : !op.inference_authorized ? (
            <EmptyState title="Analysis is unavailable in this mode">
              {op.notice}
            </EmptyState>
          ) : (
            <form onSubmit={submit} className="flex flex-col gap-5">
              {preset ? (
                <>
                  <p className="rounded-1 bg-canopy-soft p-4 text-sm">
                    Analyzing a project from Discover. The result stays
                    connected to its source evidence.
                  </p>
                  <Link
                    href={`/projects/${encodeURIComponent(preset)}`}
                    className="text-sm text-canopy"
                  >
                    Back to project
                  </Link>
                </>
              ) : (
                <>
                  <Field label="Project title" htmlFor="s-title">
                    <input
                      id="s-title"
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                      maxLength={1000}
                      placeholder="Give your project a name"
                      className={inputClass}
                    />
                  </Field>
                  <Field label="Project description" htmlFor="s-desc">
                    <textarea
                      id="s-desc"
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      maxLength={20000}
                      rows={8}
                      placeholder="What will the project do, where, and why?"
                      className={`${inputClass} h-auto py-3`}
                    />
                  </Field>
                  <div className="flex flex-wrap gap-2 text-xs text-text-3">
                    <span className="w-full">Try an illustrative example</span>
                    {EXAMPLES.map((ex) => (
                      <button
                        type="button"
                        key={ex.label}
                        className="topic-chip"
                        onClick={() => {
                          setTitle(ex.title);
                          setDescription(ex.description);
                        }}
                      >
                        {ex.label}
                      </button>
                    ))}
                  </div>
                </>
              )}
              <Button
                type="submit"
                variant="primary"
                loading={run.loading}
                disabled={
                  compare.loading ||
                  (!preset && !title.trim() && !description.trim())
                }
              >
                <Sparkles aria-hidden className="size-4" />
                Analyze project
              </Button>
              <p className="text-xs text-text-3">
                {DEMO_MODE ? "Illustrative keyword screening (no ML inference)" : op.default_model === "ml_v2"
                  ? "Powered by ML v2"
                  : "Powered by ML v1"}{" "}
                / local research screening. Your text is not stored.
              </p>
            </form>
          )}
        </div>
        <div className="project-card min-w-0 p-6 sm:p-8" aria-live="polite">
          {run.loading ? (
            <LoadingBlock rows={6} label="Analyzing project" />
          ) : run.error ? (
            <ErrorState error={run.error} />
          ) : run.data ? (
            <ResultCard
              result={run.data}
              title={submitted.title}
              description={submitted.description}
              other={compare.data}
              comparing={compare.loading}
              onCompare={
                otherKey
                  ? () => {
                      void compare.execute(otherKey);
                    }
                  : null
              }
            />
          ) : (
            <div className="flex min-h-80 flex-col items-start justify-center">
              <div className="mb-6 flex size-16 items-center justify-center rounded-full bg-canopy-soft">
                <Brain aria-hidden className="size-7 text-canopy" />
              </div>
              <p className="section-step">02 / UNDERSTAND</p>
              <h2 className="mt-3 text-2xl font-semibold">
                A useful signal.
                <br />A better next question.
              </h2>
              <p className="mt-4 max-w-sm text-sm leading-relaxed text-text-2">
                Your analysis will appear here, with a short explanation to help
                you decide what deserves a closer look.
              </p>
            </div>
          )}
          {compare.error ? (
            <div className="mt-4">
              <ErrorState error={compare.error} />
            </div>
          ) : null}
        </div>
      </div>
      {preset ? <SourceNotice access={sources.data?.access} attribution={run.data?.source_evidence ? sourceName(run.data.source_evidence.source_id) : undefined} /> : null}
      {!DEMO_MODE && <details
        className="text-sm"
        onToggle={(e) => setShowDetails(e.currentTarget.open)}
      >
        <summary className="cursor-pointer py-3 text-text-3">
          How it works / model information and evaluation
        </summary>
        <div className="mt-4 flex flex-col gap-5">
          <p className="text-sm text-text-2">
            This is research screening of text, not funding approval or verified
            climate impact. ML v2 is a development candidate selected on
            donor-labelled development validation. These labels are not
            independently human-verified ground truth.
          </p>
          {op ? <p className="text-xs text-text-3">{op.notice}</p> : null}
          {models.data ? <ModelDetails models={models.data} /> : null}
          <Disclosure summary="ML v1 and ML v2 benchmark comparison">
            {comparison.error ? (
              <ErrorState
                error={comparison.error}
                onRetry={comparison.reload}
              />
            ) : comparison.data ? (
              <ComparisonView data={comparison.data} />
            ) : (
              <LoadingBlock rows={3} />
            )}
          </Disclosure>
        </div>
      </details>}
    </div>
  );
}
