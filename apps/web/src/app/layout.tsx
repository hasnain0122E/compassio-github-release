import type { Metadata, Viewport } from "next";
import { Providers } from "@/components/providers";
import { PRODUCT_CATEGORY, PRODUCT_NAME, PRODUCT_TAGLINE } from "@/lib/brand";
import "./globals.css";
import { DEMO_MODE, DEMO_NOTICE } from "@/lib/demo-mode";

export const metadata: Metadata = {
  title: { default: `${PRODUCT_NAME} — ${PRODUCT_CATEGORY}`, template: `%s — ${PRODUCT_NAME}` },
  description: `${PRODUCT_TAGLINE} Find climate-related projects, understand their funding, and compare evidence before making decisions.`,
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#0f2a22" },
    { media: "(prefers-color-scheme: dark)", color: "#0b1f19" },
  ],
};

// Applies a saved theme before first paint (no flash). Reads only localStorage.
const THEME_SCRIPT = `try{var t=localStorage.getItem("compassio.theme");if(t==="dark"||t==="light")document.documentElement.dataset.theme=t}catch(e){}`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body className="min-h-full">
        {DEMO_MODE && <aside className="bg-canopy-soft px-4 py-2 text-center text-xs text-text" role="note">{DEMO_NOTICE}</aside>}
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
