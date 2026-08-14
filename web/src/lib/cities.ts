// Major deregulated Texas cities mapped to their TDU region slug, for SEO
// landing pages ("cheapest electricity in <city>"). Sourced from the region
// map in the curator's spreadsheet plus well-established DFW/Houston metro
// suburbs. Conservative on purpose — a wrong city→TDU mapping would send someone
// to plans they can't buy.

export interface City {
  slug: string;   // URL slug, e.g. "fort-worth"
  name: string;   // display name, e.g. "Fort Worth"
  region: string; // region/TDU slug from REGION_META
}

export const CITIES: City[] = [
  // Oncor (DFW metro, Central/West TX)
  { slug: "dallas", name: "Dallas", region: "oncor" },
  { slug: "fort-worth", name: "Fort Worth", region: "oncor" },
  { slug: "arlington", name: "Arlington", region: "oncor" },
  { slug: "plano", name: "Plano", region: "oncor" },
  { slug: "irving", name: "Irving", region: "oncor" },
  { slug: "garland", name: "Garland", region: "oncor" },
  { slug: "waco", name: "Waco", region: "oncor" },
  { slug: "temple", name: "Temple", region: "oncor" },
  { slug: "midland", name: "Midland", region: "oncor" },
  { slug: "odessa", name: "Odessa", region: "oncor" },
  { slug: "round-rock", name: "Round Rock", region: "oncor" },
  { slug: "pflugerville", name: "Pflugerville", region: "oncor" },
  // CenterPoint (Houston metro)
  { slug: "houston", name: "Houston", region: "centerpoint" },
  { slug: "sugar-land", name: "Sugar Land", region: "centerpoint" },
  { slug: "katy", name: "Katy", region: "centerpoint" },
  { slug: "pasadena", name: "Pasadena", region: "centerpoint" },
  { slug: "pearland", name: "Pearland", region: "centerpoint" },
  // AEP Texas Central (South TX / Coastal Bend / RGV)
  { slug: "corpus-christi", name: "Corpus Christi", region: "aep-central" },
  { slug: "mcallen", name: "McAllen", region: "aep-central" },
  { slug: "laredo", name: "Laredo", region: "aep-central" },
  { slug: "victoria", name: "Victoria", region: "aep-central" },
  { slug: "harlingen", name: "Harlingen", region: "aep-central" },
  // AEP Texas North (West TX)
  { slug: "abilene", name: "Abilene", region: "aep-north" },
  { slug: "san-angelo", name: "San Angelo", region: "aep-north" },
  { slug: "vernon", name: "Vernon", region: "aep-north" },
  // Texas-New Mexico Power
  { slug: "league-city", name: "League City", region: "tnmp" },
  { slug: "angleton", name: "Angleton", region: "tnmp" },
  { slug: "pecos", name: "Pecos", region: "tnmp" },
  { slug: "glen-rose", name: "Glen Rose", region: "tnmp" },
  // Lubbock Power & Light
  { slug: "lubbock", name: "Lubbock", region: "lubbock" },
];
