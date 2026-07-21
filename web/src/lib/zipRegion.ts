// ZIP -> region resolution, backed by an authoritative map built from
// PowerToChoose's own ZIP lookup for every real Texas ZIP (scripts/build_zip_map.py).
//
// Three outcomes, so the UI never shows a wrong answer:
//   a region slug  -> this ZIP is served by that TDU (shop away)
//   "none"         -> a real TX ZIP with no competitive plans we cover
//                     (non-deregulated: Austin, San Antonio, El Paso, co-ops…)
//   null           -> we don't recognize this ZIP at all

import mapRaw from "../data/zip-tdu.json";

const ZIPS = (mapRaw as { zips: Record<string, string> }).zips;

export type ZipResult = string | "none" | null;

export function zipToSlug(zip: string): ZipResult {
  const key = zip.trim().slice(0, 5);
  const v = ZIPS[key];
  if (v === undefined) return null; // unknown ZIP
  return v; // a region slug, or "none" for non-deregulated / uncovered
}
