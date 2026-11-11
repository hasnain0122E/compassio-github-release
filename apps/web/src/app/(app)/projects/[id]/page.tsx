import type { Metadata } from "next";
import { Suspense } from "react";
import { PageBody } from "@/components/shell";
import { LoadingBlock } from "@/components/ui";
import { ProjectDetailView } from "./detail";

export const metadata: Metadata = { title: "Project" };

export default function ProjectPage() {
  return (
    <Suspense
      fallback={
        <PageBody>
          <LoadingBlock rows={10} label="Loading project" />
        </PageBody>
      }
    >
      <ProjectDetailView />
    </Suspense>
  );
}
