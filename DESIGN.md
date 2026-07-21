# Design System — Honest Texas Electricity

## Product Context
- **What this is:** A free, no-affiliate website that helps Texas consumers find the honest cheapest electricity plan by filtering PowerToChoose data and exposing gimmick plans.
- **Who it's for:** Everyday Texans shopping for residential electricity, overwhelmed by PowerToChoose and distrustful of comparison sites that take referral money.
- **Space/industry:** Consumer-advocacy / civic utility / energy shopping. Peers: ComparePower, Texas Electricity Ratings, EnergyBot (all monetized via provider referrals — the thing we are NOT).
- **Project type:** Content-forward web app (light client-side calculator over precomputed static data).
- **Memorable thing:** "This tool is on my side." Every design decision serves the sense of an honest broker no provider pays.

## Aesthetic Direction
- **Direction:** Editorial / civic-utilitarian. Warm, printed, serious — reads like a trusted consumer publication, not a SaaS app.
- **Decoration level:** Minimal. Typography and hairline rules carry the design. No gradients, blobs, icon-cards, or decorative shadows.
- **Mood:** Credible, calm, plain-spoken. Feels audited, not marketed.
- **Reference posture:** Consumer Reports / ProPublica / a well-made government data site — NOT a startup landing page.

## Typography
- **Display/Hero:** Newsreader (self-hosted woff2) — editorial serif; its italic pairs with the "Honest *Texas* Electricity" accent.
- **Body:** Newsreader — reads at a comfortable 17px+ for trust content.
- **UI/Labels:** System sans stack (`ui-sans-serif, "Segoe UI", Roboto, Helvetica, Arial, sans-serif`) — uppercase micro-labels only (field labels, badges, section kickers).
- **Data/Tables/Money:** IBM Plex Mono (self-hosted) — prices, estimated bills, the "see the math" breakdown, EFL figures. Monospace makes numbers read as audited facts, not offers. Use `font-feature-settings: "tnum"` for alignment.
- **Code:** IBM Plex Mono.
- **Loading:** Self-host Newsreader + IBM Plex Mono as woff2 (no third-party font request — matches the "no one else in the room" promise). System sans needs no loading.
- **Scale (modular ~1.2, 17px base):**
  - body 17px / 1.5
  - small 14px (captions, footnotes)
  - micro-label 12px uppercase, letter-spacing .08em (sans)
  - h3 / result plan name 22px
  - h2 / section 20px
  - h1 / page headline 26px
  - masthead 30px
  - hero price 26px (mono)

## Color
- **Approach:** Restrained — one accent, neutrals do the rest. Color is rare and meaningful.
- **Primary accent:** `#0b5d3b` (deep green) — trust, independence, "this one's good / go".
- **Ink (text):** `#1a1a17` (warm near-black).
- **Paper (bg):** `#f7f4ee` (warm off-white).
- **Muted text:** `#5a554b` (meets WCAG AA 4.5:1 on paper).
- **Hairline rule:** `#d8d2c6`.
- **Surface (cards):** `#fffdf8`.
- **Semantic:** success `#0b5d3b` · error/reject `#9a2a2a` · warning `#9a6a12` · info `#2a5a6a`.
- **Contrast rule:** all body/muted text ≥ 4.5:1; the "EFL-verified" badge and reject rows must convey meaning by text, never color alone.
- **Dark mode:** warm, not cold. bg `#14130f` · surface `#1c1a15` · ink `#ece7db` · muted `#a8a294` · accent lifted to `#4faf7f` · rule `#33302a`. Reduce accent/semantic saturation ~15%.

## Spacing
- **Base unit:** 4px.
- **Density:** Comfortable.
- **Scale:** 2xs(4) xs(8) sm(12) md(16) lg(24) xl(32) 2xl(48) 3xl(64).

## Layout
- **Approach:** Grid-disciplined with an editorial reading measure. Left-aligned, single column for the primary flow; tabular for "see the math" and region tables.
- **Max content width:** 760px.
- **Reading measure:** ~65-75 characters for body.
- **Border radius:** Restrained. sm 2px (badges), md 4px (inputs), cards use a 1px ink border with 0 radius (printed-document feel). No uniform bubbly radius.

## Motion
- **Approach:** Minimal-functional. DELIBERATE: the result card has NO entrance animation — it appears solid and static, like a printed fact. This is a trust choice, counter to animated SaaS heroes.
- **Allowed motion:** slider drag, link underline transitions, focus rings.
- **Easing:** enter ease-out, exit ease-in, move ease-in-out.
- **Duration:** micro 80ms · short 180ms · medium 300ms. Nothing longer.

## Signature Patterns
- **Trust line first:** "No affiliate links. No provider pays us. Ever." + "Updated <date>" sit above everything on every page.
- **The answer card:** 1px ink border, no radius, plan name (serif) + price (mono) + facts row (4-up, wraps to 2×2 under 480px) + "EFL-verified" text badge + plain-English "why this won."
- **"Plans we threw out for you":** a first-class designed section. Struck-through plan name (serif, muted, red strike) + one-line reason with the trap word in red. Making exclusions visible IS the trust play.
- **Verified vs feed-only:** verified plans carry the green "EFL-verified" badge and can be the #1 pick; feed-only plans show a "feed estimate — verify EFL" caveat and never rank #1 without it.

## Accessibility
- WCAG AA contrast on all text (4.5:1 body/muted).
- Usage input is a real `<input type="range">` with `aria-label`, a visible numeric readout, and a typed-entry fallback.
- Touch targets ≥ 44px.
- Meaning never by color alone (badges + reject rows carry text).
- Visited links get a distinct color.

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-07-20 | Initial design system created | /design-consultation, building on the approved wireframe from /plan-design-review. Editorial/civic direction chosen to make independence legible; memorable thing = "this tool is on my side." |
| 2026-07-20 | Newsreader + IBM Plex Mono + system sans | Editorial serif for trust, mono for money-as-facts, system sans for labels. No default stacks as primary display. |
| 2026-07-20 | No motion on the result card | Deliberate departure: a static result reads as a printed fact, reinforcing trust over app-delight. |
