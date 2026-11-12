"use client";
import { DEMO_MODE } from "@/lib/demo-mode";
import { useState } from "react";
import type { GuardResponse } from "@/lib/api-types";
import { ApiError, post } from "@/lib/api";
import { Button, ErrorState } from "@/components/ui";

export function InputDemo() {
  const [text, setText] = useState("");
  const [result, setResult] = useState<GuardResponse | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);
  async function run() {
    setBusy(true); setError(null); setResult(null);
    try {
      setResult(await post<GuardResponse>("/api/v1/challenges/c09/screen", { description: text }));
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError("demo_failed", "The live demonstration could not complete.", 0));
    } finally { setBusy(false); }
  }
  if (DEMO_MODE) return <p className="text-sm text-text-2">C09 results are from prior local evaluations. Live challenge execution is unavailable in this demo.</p>;
  return <div className="space-y-3 rounded-xl border border-line p-4">
    <h3 className="font-semibold">Try Input Protection live</h3>
    <p className="text-sm text-text-2">Paste a description you are permitted to evaluate. Nothing is saved.
      Start the backend with the C09 local demo option.</p>
    <label className="block text-sm" htmlFor="guard-description">Project description</label>
    <textarea id="guard-description" value={text} maxLength={20000} rows={3}
      onChange={e => { setText(e.target.value); setResult(null); setError(null); }}
      className="w-full rounded-lg border border-line bg-surface p-3 text-sm" />
    <Button onClick={run} loading={busy} disabled={!text.trim()}>Run live input protection</Button>
    {error && <ErrorState error={error} />}
    {result && <div role="status" className="space-y-2 text-sm">
      <p>Live model label scores: raw {result.raw.prediction.label_score.toFixed(6)} → guarded {result.guarded.prediction.label_score.toFixed(6)}.</p>
      <p>{result.requires_review ? "Review required" : "No instability detected"}. {result.reasons.join(", ") || "Input unchanged"}.</p>
      <p className="text-text-3">{result.raw.model.model_version} · {result.guard_version} · threshold {result.raw.prediction.threshold}</p>
      <p className="text-text-3">{result.notice}</p>
    </div>}
  </div>;
}
