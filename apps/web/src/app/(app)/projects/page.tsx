import type { Metadata } from "next";
import { Suspense } from "react";
import { PageBody, PageHeader } from "@/components/shell";
import { LoadingBlock } from "@/components/ui";
import { Explorer } from "./explorer";

export const metadata: Metadata = { title: "Discover" };

export default function ProjectsPage() {
  return (
    <>
      <PageHeader
        title="Find projects worth a closer look."
        description="Discover development projects, explore their climate relevance and understand the funding evidence."
        crumbs={[
          { href: "/dashboard", label: "Compassio" },
          { label: "Discover" },
        ]}
      />
      <PageBody>
        <Suspense
          fallback={<LoadingBlock rows={10} label="Loading the explorer" />}
        >
          <Explorer />
        </Suspense>
      </PageBody>
    </>
  );
}
