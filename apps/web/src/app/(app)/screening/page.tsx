import type { Metadata } from "next";
import { Suspense } from "react";
import { PageBody, PageHeader } from "@/components/shell";
import { LoadingBlock } from "@/components/ui";
import { ScreeningWorkspace } from "./workbench";

export const metadata: Metadata = {
  title: "Analyze a Project",
  description:
    "Compassio Climate Intelligence — ML v2: climate-relevance screening of project text with word-level explanations.",
};

export default function ScreeningPage() {
  return (
    <>
      <PageHeader
        title="Compassio Climate Intelligence"
        description="A clearer starting point for climate research. Describe a project, understand the signal, and decide what to review next."
        crumbs={[
          { href: "/dashboard", label: "Compassio" },
          { label: "Analyze a Project" },
        ]}
      />
      <PageBody>
        <Suspense
          fallback={<LoadingBlock rows={8} label="Loading screening" />}
        >
          <ScreeningWorkspace />
        </Suspense>
      </PageBody>
    </>
  );
}
