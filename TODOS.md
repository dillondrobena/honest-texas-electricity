# TODOS

Deferred work captured during /plan-eng-review (2026-07-20). Not blocking v1.

## Anti-manipulation / adversarial robustness
- **What:** Defenses against providers engineering plans to pass the honest filter once the site has traffic.
- **Why:** The moat is trust. If a provider crafts a bill-credit teaser that happens to sit on a straight line through the 500/1000/2000 kWh sample points, it passes the linear-fit gimmick detector and a real user gets burned. Independence protects against conflict of interest, not against being gamed.
- **Pros:** Protects the core promise as the site grows; turns "we can't be fooled" into something defensible.
- **Cons:** Premature now — nobody games a site with no traffic.
- **Context / where to start:** Watch for (a) plans that pass structural rules but whose cost spikes outside the 500-2000 kWh window, (b) clustering of EFL parse-failures by provider (a signal of deliberately malformed PDFs), (c) plans reissued with tiny metadata changes to dodge history diffs. Add out-of-band cost sampling (price at 300 / 750 / 2500 kWh) as the first defense.
- **Depends on:** Meaningful traffic + the cost engine and EFL validation being live.

## Provider / plan identity normalization
- **What:** Collapse true content-duplicate offers that the live feed lists under different `idKey`s (observed: "TARA Sustainable Home Bundle" appears twice in Oncor).
- **Why:** The pipeline dedups by `plan_id` (= feed `idKey`), so distinct IDs for the same real plan slip through and show twice in the ranking — a visible quality blemish, and it makes month-over-month "what changed" diffs noisy (Codex #9/#10).
- **Pros:** Cleaner rankings; stable identity is a prerequisite for the M4 history/"what changed" feature.
- **Cons:** Risk of collapsing genuinely-distinct offers if the signature is too coarse; needs care.
- **Context / where to start:** Add a content-signature dedup pass after `plan_id` dedup in `pipeline.run` — signature = (rep, product, term_months, rate1000, renewable, cancel_fee). Verify against a month of data before trusting it for history diffs. This is the canonical-identity work that must land before M4 history.
- **Depends on:** Nothing; can be done anytime. Blocks the M4 "what changed" archive.

## Address / ESI-ID territory precision
- **What:** Upgrade from ZIP-based TDU mapping to address- or ESI-ID-level territory lookup.
- **Why:** Some Texas ZIP codes span two TDUs. v1 handles this with a "confirm your utility" disambiguation prompt, which is honest but adds a click. Address/ESI-ID lookup would make territory exact and remove the prompt.
- **Pros:** Eliminates the one class of silently-wrong answer (recommending plans for a territory the user can't enroll in).
- **Cons:** Adds friction and complexity to the "just tell me the answer" flow before it's proven necessary.
- **Context / where to start:** First build the list of ambiguous (multi-TDU) ZIPs so you know how big the problem actually is. If it's a handful of ZIPs, the disambiguation prompt may be permanent-good-enough.
- **Depends on:** v1 ZIP→TDU mapping being live so you can measure real ambiguity.
