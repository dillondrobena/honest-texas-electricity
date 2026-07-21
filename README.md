# Honest Texas Electricity

A free, no-affiliate tool that helps Texas consumers find the honest cheapest
electricity plan. It pulls PowerToChoose data, filters out the gimmick plans
(bill credits, teaser rates, min-usage traps, prepaid, time-of-use, variable
rates), and ranks the rest by true cost at your actual usage.

**Independence is the whole point.** No provider pays us. We recommend the
genuinely cheapest honest plan even when it earns us nothing.

See `DESIGN.md` for the visual system and
`~/.gstack/projects/Untitled-Power-Project/` for the full design doc and
milestone plan.

## Milestone 1 (this code): the Oncor trust engine

The pipeline that turns raw plan data into an honest, ranked answer:

```
ingest ─▶ validate ─▶ filter ─▶ cost ─▶ recommend ─▶ per-region JSON
```

- **`src/htx/filter.py`** — the four structural rules that reproduce the
  volunteer curator's honest-plan judgment. Fidelity is proven by a golden-file
  test against the real July 2026 data (every plan he kept passes our rules).
- **`src/htx/cost.py`** — fits `bill = base + rate × kWh` to the three feed
  price points. One function prices the plan at any usage AND detects gimmicks
  (a bent line = a hidden bill credit / tier).
- **`src/htx/recommend.py`** — ranks honest plans by true cost with a published
  tie-break ladder. Only trustworthy (linear-priced) plans can be the #1 pick.
- **`src/htx/validate.py`** — drops only truly unusable records; non-monotonic
  bills are kept and exposed as gimmicks, never hidden.

### What's NOT in Milestone 1 (by design)
- EFL PDF parsing / verification (every plan is `efl_verified = False` for now;
  the EFL-verified #1 gate turns on when that milestone lands).
- The other five TDU regions (Oncor only for now).
- ZIP→TDU precision beyond a seed map (`zip_tdu.py`).
- The web frontend (this is the data brain it will read).

## Run it

```bash
pip install -e ".[dev]"          # pytest + openpyxl (dev only; runtime is stdlib)

python scripts/build_fixtures.py # extract Oncor test fixtures from the spreadsheet
python -m pytest                 # 37 tests, incl. the golden-file fidelity anchor
python scripts/run_pipeline.py   # offline run -> data/out/oncor.json
python scripts/run_pipeline.py --live   # fetch current data from PowerToChoose
```

Top honest pick at 1000 kWh is *Budget Power — No Gimmicks 11* (~$118/mo).

**Offline vs live counts differ, and that's expected:** the offline fixture is
built from the curator's spreadsheet, which has no stable plan IDs, so it dedups
by a content slug (297 raw rows → 171 unique → 130 honest). The live feed gives
every offer a unique `idKey`, so it keeps all 297 (→ 220 honest) — including a few
plans listed twice under different IDs. Collapsing those true content-duplicates
is provider-identity normalization, a deferred item (see `TODOS.md`).

## Layout

```
src/htx/            the pipeline (stdlib-only runtime)
  models.py         normalized Plan + reason codes + PowerToChoose mapping
  ingest.py         live CSV/API fetch + offline fixture loading
  filter.py         the editorial filter (the heart of the product)
  cost.py           line-fit cost engine + gimmick detector
  validate.py       data-integrity checks (non-blocking)
  recommend.py      true-cost ranking + tie-break ladder
  zip_tdu.py        ZIP -> TDU (region) mapping
  pipeline.py       orchestration -> per-region JSON
scripts/            build_fixtures.py, run_pipeline.py
tests/              unit tests + the golden-file fidelity anchor
```
