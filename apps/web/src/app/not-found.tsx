import Link from "next/link";
import { CompassMark } from "@/components/brand";
import { buttonClass } from "@/components/styles";

export default function NotFound() {
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center gap-5 bg-ink px-6 text-center text-ink-text">
      <CompassMark className="size-14 text-white" />
      <h1 className="text-3xl font-bold text-white">This page is off the map</h1>
      <p className="max-w-md text-ink-text-2">The address does not match any Compassio page. Start again from the overview or the project explorer.</p>
      <div className="flex gap-3">
        <Link href="/dashboard" className={buttonClass("primary")}>
          Go to overview
        </Link>
        <Link href="/projects" className="rounded-1 border border-[#3c6a59] px-4 py-2 text-sm font-medium text-white hover:border-ink-text-2">
          Explore projects
        </Link>
      </div>
    </main>
  );
}
