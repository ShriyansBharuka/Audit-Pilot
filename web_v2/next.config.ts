import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  /* config options here */
  cacheComponents: true,
  partialPrefetching: true,
  experimental: {
    // every page renders client-side after the token check, so automatic instant-navigation validation
    // reports each route as a "dropped segment"; validate only segments that export `instant`
    instantInsights: { validationLevel: "manual-warning" },
  },
  turbopack: {
    // web_v2/node_modules is a junction to web/node_modules; the root must contain both
    root: path.join(__dirname, ".."),
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
