"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Tabs } from "@/components/ui";
import { CompareTab } from "./compare";
import { PrioritizeTab } from "./prioritize";

export function WorkspaceTabs() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const tab = params.get("tab") === "prioritize" ? "prioritize" : "compare";
  return (
    <div className="flex flex-col gap-5">
      <Tabs
        label="Workspace"
        value={tab}
        onChange={(t) =>
          router.replace(t === "compare" ? pathname : `${pathname}?tab=${t}`, {
            scroll: false,
          })
        }
        tabs={[
          { id: "compare", label: "Saved projects" },
          { id: "prioritize", label: "Review priorities" },
        ]}
      />
      <div role="tabpanel">
        {tab === "compare" ? <CompareTab /> : <PrioritizeTab />}
      </div>
    </div>
  );
}
