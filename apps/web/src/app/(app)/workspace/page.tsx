import type { Metadata } from "next";
import { Suspense } from "react";
import { PageBody, PageHeader } from "@/components/shell";
import { LoadingBlock } from "@/components/ui";
import { WorkspaceTabs } from "./tabs";

export const metadata: Metadata = { title: "My Shortlist" };

export default function WorkspacePage() {
  return (
    <>
      <PageHeader
        title="My Shortlist"
        description="Keep the projects that caught your attention. Compare the evidence. Know what to review next."
        crumbs={[
          { href: "/dashboard", label: "Compassio" },
          { label: "My Shortlist" },
        ]}
      />
      <PageBody>
        <Suspense fallback={<LoadingBlock rows={6} />}>
          <WorkspaceTabs />
        </Suspense>
      </PageBody>
    </>
  );
}
