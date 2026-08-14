import { defineConfig } from "astro/config";
import { writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import cloudflare from "@astrojs/cloudflare";

const SITE = "https://honesttexaselectricity.com";

// Minimal sitemap integration. The official @astrojs/sitemap is incompatible
// with output:"hybrid" + the Cloudflare adapter (crashes in build:done), so we
// emit a plain sitemap.xml from the prerendered pages ourselves.
function sitemap() {
  return {
    name: "inline-sitemap",
    hooks: {
      "astro:build:done": ({ pages, dir }) => {
        const paths = new Set(
          (pages ?? [])
            .map((p) => p.pathname.replace(/index\.html$/, ""))
            .map((path) => (path.startsWith("/") ? path : `/${path}`)),
        );
        const urls = [...paths]
          .sort()
          .map((path) => `  <url><loc>${SITE}${path}</loc></url>`)
          .join("\n");
        const xml =
          `<?xml version="1.0" encoding="UTF-8"?>\n` +
          `<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`;
        writeFileSync(new URL("sitemap.xml", dir), xml);
        console.log(`[sitemap] wrote ${paths.size} unique urls`);
      },
    },
  };
}

export default defineConfig({
  site: SITE,
  output: "hybrid",
  adapter: cloudflare(),
  integrations: [sitemap()],
});
