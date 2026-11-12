import type { NextConfig } from "next";

// Vercel bundles this public value into browser JavaScript. Refuse accidental
// localhost fallbacks or mixed content in a hosted deployment.
if (process.env.VERCEL === "1" && process.env.NEXT_PUBLIC_COMPASSIO_DEMO_MODE !== "true") {
  const value = process.env.NEXT_PUBLIC_COMPASSIO_API_URL;
  const api = value ? new URL(value) : null;
  if (
    !api || api.protocol !== "https:" || api.username || api.password ||
    api.pathname !== "/" || api.search || api.hash ||
    ["localhost", "127.0.0.1", "[::1]"].includes(api.hostname)
  ) {
    throw new Error("Vercel requires NEXT_PUBLIC_COMPASSIO_API_URL as an HTTPS backend origin");
  }
}

const nextConfig: NextConfig = {
  /* config options here */
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
