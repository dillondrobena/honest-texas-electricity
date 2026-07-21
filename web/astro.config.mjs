import { defineConfig } from "astro/config";

import cloudflare from "@astrojs/cloudflare";

// Static output — near-zero-cost hosting (GitHub Pages / Cloudflare Pages).
// Update `site` to the real domain when it exists.
export default defineConfig({
  site: "https://honest-texas-electricity.example",
  output: "hybrid",
  adapter: cloudflare()
});