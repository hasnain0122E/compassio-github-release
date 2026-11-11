import Link from "next/link";
import { Brain, Database, FileSearch, Landmark, Scale, ShieldCheck } from "lucide-react";
import { CompassHero } from "@/components/compass-hero";
import { HeroCounts, LiveFundingPreview, ModelAdvantage, ProblemFacts, SourceList } from "@/components/landing-live";
import { CompassMark } from "@/components/brand";
import { buttonClass } from "@/components/styles";

const STEPS: Array<{ title: string; body: string; href: string; action: string }> = [
  {
    title: "Find",
    body: "Search 26 thousand project records by country, sector, source and year. Pakistan is covered by every source.",
    href: "/projects?country=PAK",
    action: "Explore Pakistan projects",
  },
  {
    title: "Understand",
    body: "Open a project to see each funding figure with its meaning, currency, price basis and source reference.",
    href: "/projects/gcf_projects:FP085",
    action: "Open an example project",
  },
  {
    title: "Compare",
    body: "Put up to ten projects side by side. Totals appear only when the figures can honestly be added.",
    href: "/workspace",
    action: "Open the workspace",
  },
  {
    title: "Plan",
    body: "Try a hypothetical budget split under your own rules, with every cent of arithmetic shown.",
    href: "/scenarios",
    action: "Plan a budget",
  },
];

export default function Home() {
  return (
    <div className="flex min-h-dvh flex-col">
      <a href="#content" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-1 focus:bg-panel focus:px-3 focus:py-2">
        Skip to content
      </a>
      <header className="bg-ink text-ink-text">
        <nav aria-label="Site" className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-4 sm:px-8">
          <Link href="/" className="flex items-center gap-2.5 text-white">
            <CompassMark className="size-7" />
            <span className="text-lg font-bold tracking-tight">Compassio</span>
          </Link>
          <ul className="hidden items-center gap-6 text-sm text-ink-text-2 md:flex">
            <li>
              <a href="#how" className="hover:text-white">How it works</a>
            </li>
            <li>
              <a href="#ai" className="hover:text-white">AI screening</a>
            </li>
            <li>
              <a href="#data" className="hover:text-white">Data</a>
            </li>
          </ul>
          <Link href="/dashboard" className="rounded-1 bg-white px-3.5 py-2 text-sm font-semibold text-ink hover:bg-ink-text">
            Open the app
          </Link>
        </nav>

        <div id="content" className="mx-auto grid max-w-7xl items-center gap-10 px-4 pb-16 pt-8 sm:px-8 lg:grid-cols-[1.1fr_1fr] lg:pb-24 lg:pt-12">
          <div className="flex flex-col gap-6">
            <p className="text-sm font-semibold text-[#7fd1a3]">Compassio · climate finance intelligence</p>
            <h1 className="text-4xl font-bold leading-[1.05] text-white sm:text-5xl">Give Funding a Better Direction.</h1>
            <p className="max-w-xl text-lg text-ink-text-2">
              A platform that helps people find climate-related projects, understand their funding, and
              compare evidence before making decisions.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link href="/projects" className="rounded-1 bg-[#7fd1a3] px-5 py-3 text-sm font-semibold text-ink hover:bg-white">
                Explore projects
              </Link>
              <Link href="/screening" className="rounded-1 border border-[#3c6a59] px-5 py-3 text-sm font-semibold text-white hover:border-ink-text-2">
                Try AI screening
              </Link>
            </div>
            <div className="mt-4 border-t border-ink-2 pt-6">
              <p className="mb-4 text-2xs text-ink-text-2">Records in the verified local database, per source (never added across sources)</p>
              <HeroCounts />
            </div>
          </div>
          <div className="flex justify-center lg:justify-end">
            <CompassHero />
          </div>
        </div>
      </header>

      <main className="flex-1">
        <section aria-labelledby="problem" className="mx-auto max-w-7xl px-4 py-16 sm:px-8 sm:py-20">
          <div className="max-w-2xl">
            <h2 id="problem" className="text-2xl font-bold sm:text-3xl">Climate finance data is easy to misread</h2>
            <p className="mt-3 text-text-2">
              The information exists, spread across fund portals, research datasets and development bank
              files. Put together carelessly, it overstates money and hides the projects that matter.
            </p>
          </div>
          <div className="mt-8">
            <ProblemFacts />
          </div>
        </section>

        <section id="how" aria-labelledby="how-title" className="border-y border-line bg-panel">
          <div className="mx-auto max-w-7xl px-4 py-16 sm:px-8 sm:py-20">
            <h2 id="how-title" className="text-2xl font-bold sm:text-3xl">How Compassio works</h2>
            <ol className="mt-8 grid gap-8 md:grid-cols-2 lg:grid-cols-4">
              {STEPS.map((step, i) => (
                <li key={step.title} className="flex flex-col gap-3 border-t-2 border-canopy pt-4">
                  <p className="num text-sm font-semibold text-canopy">Step {i + 1}</p>
                  <h3 className="text-xl font-bold">{step.title}</h3>
                  <p className="text-sm text-text-2">{step.body}</p>
                  <Link href={step.href} className="mt-auto text-sm font-semibold text-canopy underline-offset-4 hover:underline">
                    {step.action}
                  </Link>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section aria-labelledby="capabilities" className="mx-auto max-w-7xl px-4 py-16 sm:px-8 sm:py-20">
          <h2 id="capabilities" className="text-2xl font-bold sm:text-3xl">What you can do with it</h2>
          <div className="mt-8 grid gap-6 lg:grid-cols-[1.2fr_1fr]">
            <div className="rounded-2 border border-line bg-panel p-5">
              <div className="flex items-center gap-2">
                <Landmark aria-hidden className="size-5 text-series-1" />
                <h3 className="font-semibold">See where climate funds approved money</h3>
              </div>
              <div className="mt-4">
                <LiveFundingPreview />
              </div>
              <Link href="/analytics" className="mt-4 inline-block text-sm font-semibold text-canopy underline-offset-4 hover:underline">
                Open financial analytics
              </Link>
            </div>
            <ul className="flex flex-col divide-y divide-line rounded-2 border border-line bg-panel">
              {[
                { Icon: FileSearch, t: "Evidence for every figure", b: "Each amount carries what it means, its currency, its year and the source record it came from." },
                { Icon: Scale, t: "Comparisons that refuse unsafe totals", b: "Linked records and parts of one funding package are shown side by side, never added together." },
                { Icon: Brain, t: "AI screening of project text", b: "Paste a description and see why the model thinks it is climate-related, word by word." },
                { Icon: ShieldCheck, t: "Hypothetical budgets that balance", b: "Allocated plus unallocated always equals your budget exactly, with the arithmetic on screen." },
              ].map(({ Icon, t, b }) => (
                <li key={t} className="flex gap-3 p-5">
                  <Icon aria-hidden className="mt-0.5 size-5 shrink-0 text-canopy" />
                  <div>
                    <h3 className="font-semibold">{t}</h3>
                    <p className="mt-1 text-sm text-text-2">{b}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section id="ai" aria-labelledby="ai-title" className="bg-ink text-ink-text">
          <div className="mx-auto grid max-w-7xl gap-10 px-4 py-16 sm:px-8 sm:py-20 lg:grid-cols-2">
            <div className="flex flex-col gap-4">
              <p className="text-sm font-semibold text-[#7fd1a3]">Compassio Climate Intelligence — ML v2</p>
              <h2 id="ai-title" className="text-2xl font-bold text-white sm:text-3xl">Finds the climate projects simpler screening overlooks</h2>
              <p className="text-ink-text-2">
                Our improved AI helps identify climate-related development projects that simpler screening
                can overlook, especially projects involving farming, water and flood protection. It reads the
                title and description, gives a score, and shows which words pushed it up or down.
              </p>
              <p className="text-sm text-ink-text-2">
                It helps you decide what to review first. It does not approve funding or verify
                environmental outcomes, and the earlier ML v1 model stays available for comparison.
              </p>
              <Link href="/screening" className="mt-2 w-fit rounded-1 bg-[#7fd1a3] px-5 py-3 text-sm font-semibold text-ink hover:bg-white">
                Try AI screening
              </Link>
            </div>
            <div className="rounded-2 border border-ink-2 p-5">
              <ModelAdvantage />
            </div>
          </div>
        </section>

        <section id="data" aria-labelledby="data-title" className="mx-auto max-w-7xl px-4 py-16 sm:px-8 sm:py-20">
          <div className="grid gap-10 lg:grid-cols-[1fr_1.3fr]">
            <div className="flex flex-col gap-4">
              <h2 id="data-title" className="text-2xl font-bold sm:text-3xl">Real data, honest arithmetic</h2>
              <ul className="flex flex-col gap-3 text-sm text-text-2">
                <li className="flex gap-3">
                  <Database aria-hidden className="mt-0.5 size-4 shrink-0 text-canopy" />
                  Every record comes from a registered public source with a file checksum. Nothing is generated.
                </li>
                <li className="flex gap-3">
                  <Landmark aria-hidden className="mt-0.5 size-4 shrink-0 text-canopy" />
                  Money is exact decimal arithmetic on the server. A missing amount is shown as missing, never as zero.
                </li>
                <li className="flex gap-3">
                  <ShieldCheck aria-hidden className="mt-0.5 size-4 shrink-0 text-canopy" />
                  Sources keep their licences and attribution. This demo runs on one machine under an event
                  authorization; it is not a public data service.
                </li>
              </ul>
              <div className="mt-2 rounded-2 border border-line bg-panel-2 p-4 text-sm text-text-2">
                <p className="font-semibold text-text">Built with</p>
                <p className="mt-1">
                  FastAPI with a read-only SQLite database and exact Decimal finance contracts · scikit-learn
                  text models with pinned checksums · Next.js and React for this interface.
                </p>
              </div>
            </div>
            <SourceList />
          </div>
        </section>

        <section aria-labelledby="cta" className="border-t border-line bg-panel">
          <div className="mx-auto flex max-w-7xl flex-col items-start gap-5 px-4 py-14 sm:px-8 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 id="cta" className="text-2xl font-bold">Start with the projects</h2>
              <p className="mt-1 text-text-2">Filter by country, open the evidence, and compare before you decide.</p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Link href="/projects" className={buttonClass("primary")}>Explore projects</Link>
              <Link href="/screening" className={buttonClass("secondary")}>Try AI screening</Link>
            </div>
          </div>
        </section>
      </main>

      <footer className="bg-ink px-4 py-8 text-2xs text-ink-text-2 sm:px-8">
        <div className="mx-auto flex max-w-7xl flex-col gap-2">
          <p>
            Compassio is decision support. Climate-relevance screening is not proof of environmental benefit;
            historical commitments are not returns; funded projects are not necessarily open to new funding.
          </p>
          <p>
            Data: AidData (ODC-By 1.0) and Qi et al. 2026; Green Climate Fund (first published by the Green
            Climate Fund); Climate Funds Update; Asian Development Bank IATI. Local event demonstration only.
          </p>
        </div>
      </footer>
    </div>
  );
}
