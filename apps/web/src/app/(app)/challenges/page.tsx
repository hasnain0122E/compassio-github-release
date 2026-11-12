import type { Metadata } from "next";
import { ShieldCheck } from "lucide-react";
import { PageBody, PageHeader } from "@/components/shell";
import { Badge } from "@/components/ui";
import { InputDemo } from "./input-demo";

export const metadata: Metadata = { title: "Trust & Resilience" };

function Pair({ label, before, after, total }: {
  label: string; before: number; after: number; total: number;
}) {
  return <div className="space-y-2 rounded-xl bg-surface-2 p-4">
    <p className="text-sm font-medium">{label}</p>
    {[{ name: "Before", value: before }, { name: "After", value: after }].map(r =>
      <div key={r.name} className="grid grid-cols-[3.5rem_1fr_5rem] items-center gap-3 text-xs">
        <span>{r.name}</span>
        <meter className="h-3 w-full accent-emerald-600" min={0} max={total} value={r.value}
          aria-label={`${label}, ${r.name}: ${r.value} of ${total}`} />
        <span className="text-right tabular-nums">{r.value} / {total}</span>
      </div>)}
  </div>;
}

export default function ChallengesPage() {
  return <>
    <PageHeader title="Compassio Trust & Resilience"
      description="Three safeguards, tested with reproducible evidence. Explore the limits as well as the improvements."
      crumbs={[{ href: "/projects", label: "Compassio" }, { label: "Trust & Resilience" }]} />
    <PageBody>
      <p className="text-sm text-text-2">These comparisons are recorded results from prior local evaluations.
        Live challenge execution requires the separate local research environment. Screening supports human review;
        it does not predict funding approval, returns or environmental impact.</p>
      <div className="flex flex-col gap-6">
        <article className="project-card space-y-5 p-5 sm:p-8">
          <div className="flex flex-wrap items-center gap-3"><ShieldCheck aria-hidden className="size-6 text-canopy" />
            <h2 className="text-xl font-semibold">C05 · Data Integrity Shield</h2><Badge tone="teal">Recorded evidence</Badge></div>
          <p className="text-text-2">Problem: corrupted donor labels can teach the AI the wrong lesson.</p>
          <p>We identify suspicious labels before the AI learns from them.</p>
          <Pair label="Targeted poisoned labels caught: original A → candidate B" before={56} after={187} total={666} />
          <div className="overflow-x-auto"><table className="w-full text-left text-sm">
            <caption className="pb-3 text-left text-text-3">Real 13,317-record development batch; 666 labels flipped.</caption>
            <thead><tr><th scope="col">Detection measure</th><th scope="col">Policy A</th><th scope="col">Candidate B</th></tr></thead>
            <tbody>
              <tr><th scope="row">Uniform: precision / recall</th><td>40.5% / 36.8%</td><td>48.4% / 24.6%</td></tr>
              <tr><th scope="row">Uniform: false quarantine</th><td>2.85%</td><td>1.38%</td></tr>
              <tr><th scope="row">Targeted: precision / recall</th><td>12.2% / 8.4%</td><td>54.0% / 28.1%</td></tr>
              <tr><th scope="row">Targeted: clean positives quarantined</th><td>370</td><td>79</td></tr>
            </tbody>
          </table></div>
          <p className="text-sm text-text-2">Trade-off: B accepts 81 more poisoned labels under uniform attack and needs more review.
            Against targeted attacks, B still passes 479 of 666 poisoned labels. Adaptation recall is
            0.624 after B versus 0.647 with naive poisoned training. Neither policy establishes protection
            against targeted poisoning. The registered model is never retrained by this demonstration.</p>
          <a className="text-sm underline" href="/evidence/c05_scorecard.md">Read measured C05 scorecard and full trade-offs</a>
          <details className="text-sm"><summary className="cursor-pointer font-medium">Demonstrate C05 locally</summary>
            <p className="my-3 text-text-2">Run from the repository root. This executes attack, detector and quarantine on a verified cached development batch. It fits only disposable detection models.</p>
            <pre className="overflow-x-auto rounded-xl bg-surface-2 p-4 text-xs">{`uv run python -m compassio_ml.challenges.c05.cli verify
uv run python -m compassio_ml.challenges.c05.cli live --sample 3000
uv run python -m compassio_ml.challenges.c05.cli live --sample 3000 --attack targeted_non_energy_positive --policy hardened`}</pre>
            <p className="mt-3 text-text-3">Requires ignored data/ml_v2/challenges/c05 base and addendum runs. They are verified by hash and are not shipped in the website.</p>
          </details>
          <details className="text-sm"><summary className="cursor-pointer">Technical methodology & provenance</summary>
            <p className="mt-3 text-text-2">Policy A combines out-of-fold text disagreement and 15 nearest neighbours. Candidate B adds independent donor purpose-code evidence and protects ambiguous positives. Labels never change silently. The oracle scores decisions afterwards. Seed 20261112; runs c05_acbd465eef5a and addendum_80ef1619158b. Development-validation results are not independent scientific validation.</p>
          </details>
        </article>
        <article className="project-card space-y-5 p-5 sm:p-8">
          <div className="flex flex-wrap items-center gap-3"><ShieldCheck aria-hidden className="size-6 text-canopy" />
            <h2 className="text-xl font-semibold">C09 · Input Protection</h2><Badge tone="teal">Development-record evaluation</Badge></div>
          <p className="text-text-2">Problem: small text edits can manipulate a screening result.</p>
          <p>We reduce the effect of small text changes that try to manipulate the AI&apos;s results.</p>
          <Pair label="Fixed attacks: label flips, raw → guarded" before={5} after={2} total={1280} />
          <p className="text-sm text-text-2">Transferred search: 8 → 2 flips / 512. Adaptive search: 6 → 5 / 512.
            Clean inputs unchanged: 256 / 256. Adaptive attacks still succeed; review flags do not count as prevented flips.</p>
          <a className="text-sm underline" href="/evidence/c09_scorecard.md">Read measured C09 scorecard</a>
          <InputDemo />
          <details className="text-sm"><summary className="cursor-pointer">Technical methodology & provenance</summary>
            <p className="mt-3 text-text-2">Frozen ML v2 weights and threshold, wrapped by c09-input-guard-v1. Narrow Unicode sanitation preserves numeric spelling, negation boundaries and meaningful joiners. Raw and normalized predictions remain separate; explanation offsets refer to their respective inputs. Evidence: docs/challenges/c09_benchmark_aggregates.json, split-bound development assessment. This is not a sealed final test or evidence about unseen publishers.</p>
          </details>
        </article>
        <article className="project-card space-y-5 p-5 sm:p-8">
          <div className="flex flex-wrap items-center gap-3"><ShieldCheck aria-hidden className="size-6 text-canopy" />
            <h2 className="text-xl font-semibold">C11 · Availability Shield</h2><Badge tone="teal">Fixture-backed local test</Badge></div>
          <p className="text-text-2">Problem: abusive traffic can crowd out normal users.</p>
          <p>We limit abusive traffic so other users can continue accessing Compassio.</p>
          <Pair label="Abusive traffic rejected: baseline → shield" before={0} after={5953} total={6400} />
          <p className="text-sm text-text-2">Approximately 200 abusive requests per second, measured locally.
            5,953 / 6,400 returned HTTP 429; 96 / 96 independent legitimate requests succeeded.
            Shared-IP success: 50%. Users sharing an address can share the traffic budget.</p>
          <p className="text-sm text-text-2">These capacity results use fixture-backed local endpoints.
            They do not establish the canonical database and models can sustain 200 requests per second.</p>
          <a className="text-sm underline" href="/evidence/c11_scorecard.md">Read measured C11 scorecard</a>
          <details className="text-sm"><summary className="cursor-pointer font-medium">Demonstrate C11 locally</summary>
            <p className="my-3 text-text-2">Use a separate controlled process, outside the judge&apos;s browsing session. This probe runs real canonical requests at a modest rate and records its own results.</p>
            <pre className="overflow-x-auto rounded-xl bg-surface-2 p-4 text-xs">uv run python scripts/task012_probe.py</pre>
          </details>
          <details className="text-sm"><summary className="cursor-pointer">Technical methodology & provenance</summary>
            <p className="mt-3 text-text-2">Opt-in peer and global token buckets, separate read and screening budgets, bounded state, idle cleanup, typed 429 and Retry-After. CORS preflights bypass admission. Peer identity ignores untrusted forwarding headers. One worker only. Evidence: docs/challenges/c11_metrics.json and c11_scorecard.md. Production access stays fail-closed.</p>
          </details>
        </article>
      </div>
    </PageBody>
  </>;
}
