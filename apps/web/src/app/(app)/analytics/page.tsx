import type { Metadata } from "next";
import { Suspense } from "react";
import { PageBody, PageHeader } from "@/components/shell";
import { LoadingBlock } from "@/components/ui";
import { AnalyticsView } from "./view";

export const metadata: Metadata = { title: "Financial analytics" };

export default function AnalyticsPage() {
  return (
    <>
      <PageHeader
        title="Financial analytics"
        description="Explore historical climate finance by country, sector, institution and source. Every chart shows one metric with its flow, currency, price basis, period and exclusions, because figures with different meanings cannot be added."
        crumbs={[{ href: "/dashboard", label: "Compassio" }, { label: "Analytics" }]}
      />
      <PageBody>
        <Suspense fallback={<LoadingBlock rows={10} />}>
          <AnalyticsView />
        </Suspense>
      </PageBody>
    </>
  );
}
