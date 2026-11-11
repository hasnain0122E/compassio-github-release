import type { Metadata } from "next";
import { PageBody, PageHeader } from "@/components/shell";
import { Planner } from "./planner";

export const metadata: Metadata = { title: "Budget scenarios" };

export default function ScenariosPage() {
  return (
    <>
      <PageHeader
        title="Budget scenario planner"
        description="Try how a hypothetical budget could be split across selected projects: equally, by sector priority, or by priority score, under your own limits. Allocated plus unallocated always equals the budget."
        crumbs={[{ href: "/dashboard", label: "Compassio" }, { label: "Budget scenarios" }]}
      />
      <PageBody>
        <Planner />
      </PageBody>
    </>
  );
}
