// ZIP -> region slug (client-side convenience). Deliberately a modest, explicit
// set: the region SELECTOR is the always-correct mechanism. An unknown ZIP
// returns null so the UI asks the user to pick, rather than guessing wrong.
// Full address/ESI-ID precision is a deferred milestone (see TODOS.md).

const ZIP_TO_SLUG: Record<string, string> = {
  // Oncor
  "75201": "oncor", "75202": "oncor", "75204": "oncor", "76101": "oncor",
  "76102": "oncor", "76701": "oncor", "79701": "oncor", "78664": "oncor",
  "75080": "oncor", "76006": "oncor",
  // CenterPoint (Houston)
  "77002": "centerpoint", "77004": "centerpoint", "77008": "centerpoint",
  "77019": "centerpoint", "77494": "centerpoint", "77573": "tnmp",
  // AEP Central / North
  "78401": "aep-central", "78501": "aep-central", "78040": "aep-central",
  "79601": "aep-north", "76901": "aep-north",
  // TNMP
  "77590": "tnmp", "79772": "tnmp",
  // Lubbock
  "79401": "lubbock", "79424": "lubbock",
};

export function zipToSlug(zip: string): string | null {
  return ZIP_TO_SLUG[zip.trim().slice(0, 5)] ?? null;
}
