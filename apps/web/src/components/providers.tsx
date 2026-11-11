"use client";

import { SelectionProvider } from "@/lib/selection";
import { ToastProvider } from "@/lib/toast";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ToastProvider>
      <SelectionProvider>{children}</SelectionProvider>
    </ToastProvider>
  );
}
