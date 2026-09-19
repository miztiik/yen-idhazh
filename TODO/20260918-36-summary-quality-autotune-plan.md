# Plan 36 - the summariser grades itself, and content decides its future

**Created**: 2026-09-18
**Depends on**: plan 34's fit core (rows 5-8) merged; plan 35's `EvalRow` churn (rows 6, 7, 8) merged
**Correction level**: 5 - a model verdict decides what a reader is shown

## Start here - the handoff

Every summary already gets a faithfulness score (HHEM) the day it is written. That number sets a
display badge and nothing else: the item publishes whatever the badge says. This plan closes the loop
plan 34 opened for the merge line, for summary quality: measure every summary on four axes, fit a band
to each axis from its own rolling distribution with no human in the loop, and let the band decide
whether a summary publishes or is withheld - and a withheld summary is absent from the reader's day,
tracked in item-health telemetry and surfaced in the console, never a reader-facing card (section 0e).

**The one sentence that orders every decision here, taken from plan 34 and still true: withholding a
story the reader never sees is an invisible loss; publishing a weak summary is a visible, recoverable
one. Only one of those is invisible.** So the default is to publish, the only failure that withholds is
a false claim, and the floor that withholds is an absolute line that does not drift.

**Execution stamp** (per [`docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md)):

```
Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. Execution is AUTHORIZED (owner, 2026-09-19); it begins once plan 34's fit core and plan 35's EvalRow churn are on main.
```

## Execution handover (zero-context cold start)

Paste-ready brief for an agent that picks this plan up with zero prior context. It restates the
execution stamp above in operating detail; [`docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md)
is the canonical contract, and the Onboarding subsection below lists the page that owns each surface.

```text
You are the OWNER of this plan-doc (TODO/20260918-36-summary-quality-autotune-plan.md).
You have zero prior context. Execute it end to end. Execution is AUTHORIZED (owner,
2026-09-19), but this plan is BLOCKED until plan 34's fit core (its rows 5-8) AND plan 35's
EvalRow churn (its rows 6, 7, 8) are on main. Confirm both are merged before dispatching.

STEP 0 - COLD START. Read, in order: CLAUDE.md; docs/how-to/execute-a-plan.md (you are
"the owner"); docs/agents/bootstrap.md; docs/how-to/run-the-gates.md;
docs/how-to/ship-a-pr.md; the design of record docs/concepts/summary-quality-autotune.md;
then this plan's Section 0, its Onboarding subsection, Sections 0a-0e (0e holds the current
owner rulings that SUPERSEDE earlier E-/G-items - read it before trusting any link-only or
eviction language above it), Section 0d Tables B and C (PR grouping + optimistic dispatch),
and Section 1 (the Status Reckoner). Section 2 is the per-row detail.

STEP 1 - ADOPT OR CLOSE FIRST. git worktree list, list branches, gh pr list. Reconcile any
half-done row against the Reckoner. Do not switch or edit the shared checkout. Work only in
dedicated worktrees under the repo's sibling .worktrees/ directory.

STEP 2 - RUN THE POOL. Parallel N = 4, running pool, not a wave - but this plan's real peak
width is 2 (Section 0d): the serial spine is Rows 1 -> 2 -> 4 -> 5 -> 7 -> 8 (six deep), and
Row 8 is the width-1 tail. A slot frees when a worker RETURNS its report, never on merge
(Section 0d Table C, optimistic dispatch). Isolated worktree per row off origin/main, named
branch, never shared. Worker brief + the two pre-dispatch checks: as in execute-a-plan.md.

STEP 3 - DISPATCH ORDER (Section 0d Table B; 11 PRs / 4 waves). Three co-roots from t0, each
gated on an external merge:
    fit-core         Row 1     needs plan 34 fit core on main    AUTO-merge on green
    eval-columns     Row 3     needs plan 35 EvalRow on main     AUTO-merge on green
    coherence-place  Row 11    needs plan 35 coherence on main   AUTO-merge on green
  Then, as each predecessor lands: metric-fold-fit (Rows 2,4,5) after fit-core + eval-columns;
  geval-leg (Row 6) after eval-columns; publish-gate (Row 7) after metric-fold-fit;
  geval-measure (Row 10 - MEASURES, runs ALONE) after geval-leg; console-panels (Row 9) after
  metric-fold-fit + publish-gate; rejects-store (Row 12) after publish-gate; plan34-gaps
  (Row 13) after plan 34 landed + geval-leg; apply-gate (Row 8) after publish-gate - PAUSE
  (STEP 5). Readiness is computed, not read off the wave letter.

STEP 4 - MERGE + REFILL. Dispatch the next ready row when a worker returns; verify CI + test
records against the Definition of Done (CLAUDE.md section 9) and ship-a-pr.md; on green remove
the worktree then gh pr merge <N> --squash --delete-branch. Merging is serialized, never
blocks the pool.

STEP 5 - ESCALATE (PAUSE that row, not the pool). Surface with the five-part shape
(CLAUDE.md 0c) for:
  - Row 8 (apply-gate) flips the flag and WITHHOLDS items - the FIRST change to a published
    day. Lands ALONE, owner sign-off. This is the plan's width-1 tail.
  - Promoting any metric's action from watch/downgrade to block - owner, on a track record.
  - Any new Design rationale that changes a persisted contract, an unresolved persona
    conflict, a scope change, or a 3x cost overrun.
  HARD WAIT: eval-columns (Row 3) widens the EvalRow, and state/scores is merge=union - two
  open widenings (this plan's and any plan-35 one) stack silently with NO conflict. Row 3
  waits on main, never branch-stacked; after any EvalRow merge, census committed shards for a
  stacked header (Section 0d Table C).

STEP 6 - PERSONAS resolve ambiguity, not an approval gate (exact CLAUDE.md section 14 names;
Explore for read-only breadth). Consult only when two answers lead to DIFFERENT code; DEBATE
to one ruling on a contested decision.

STEP 7 - REPORT in plain English (CLAUDE.md 0b/0c): lead with what happened, lettered tables
with row-ids, decisions as five-part requests.

CLOSURE. When every row is DONE/COLLAPSED: resolve the Reckoner, distil anything durable
(distill-a-plan.md) - the offline-judge TODO note in Section 0e moves to
docs/concepts/summary-quality-autotune.md as the named future consumer - delete the plan-doc,
then sweep the worktrees.

FIRST ACTION: confirm plan 34's fit core and plan 35's EvalRow churn are on main; then STEP 1
(adopt-or-close); then dispatch fit-core (Row 1), eval-columns (Row 3) and coherence-place
(Row 11) as their external gates clear.
```

## Section 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | The auto-tune is half-built: plan 35 measures four quality axes but nothing acts on them. This fits an adaptive band to each axis and gates publication on it, mirroring plan 34's proven loop. |
| Hard scope - in | Two new contracts (`MetricScoreDistribution`, `FittedMetricBand`); three `EvalRow` columns; the fold and fit stages; the G-Eval fluency judge in the `LLM-JUDGES` council; the veto-chain publish gate (record-only, then flagged on); the console panels; a G-Eval cost measurement. |
| Hard scope - out | see table below |
| ESCALATE triggers | (1) Row 8 flips the flag and withholds items - the first change to a published day, lands alone, owner sign-off. (2) promoting any metric's action from `watch`/`downgrade` to `block` - owner, on a track record. |
| Chosen strategy | Reuse plan 34 wholesale: extract its fit core direction-parameterised, mint data-parameterised per-metric contracts, host G-Eval on the existing `LLM-JUDGES` workflow, ship the gate record-only behind a flag. Owner + convergence debate, 2026-09-18. |
| Execution | AUTHORIZED (owner, 2026-09-19); begins once plan 34's fit core and plan 35's EvalRow churn are on main. Parallel N = 4; the running-pool orchestration + 9-PR wave grouping is section 0d Table B. |
| Intent | Every summary is measured on four axes; an adaptive band is fit to each from its own rolling distribution with no human in the loop; and the band decides whether a summary publishes or is withheld - a withheld item is absent from the reader's day and recorded as an item-health metric surfaced in the console (section 0e). The contracts each row names FOLLOW this intent; when a contract and the intent disagree, the contract changes, not the intent (CLAUDE.md 0d). |

### Onboarding (cold start - read these first, zero context assumed)

A worker picks up any row with no prior context by reading, in order: [`CLAUDE.md`](../CLAUDE.md) (the
engineering contract), [`docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md) (how this plan
runs), [`docs/agents/bootstrap.md`](../docs/agents/bootstrap.md) (which page owns the surface a row
touches), and [`docs/how-to/run-the-gates.md`](../docs/how-to/run-the-gates.md) (the gate commands). The
design of record is [`docs/concepts/summary-quality-autotune.md`](../docs/concepts/summary-quality-autotune.md)
(the four metrics, the fold-fit loop, the publish gate). The loop this plan mirrors is the adaptive
merge line in [`docs/architecture/publishing/same-story.md`](../docs/architecture/publishing/same-story.md)
- Row 1 extracts its fit core from `backend/idhazh/similarity/fit.py`. Owning pages per surface:
contracts + schema versioning ->
[`docs/architecture/contracts/schemas.md`](../docs/architecture/contracts/schemas.md); evaluation + the
console -> [`docs/concepts/evaluation.md`](../docs/concepts/evaluation.md). Every row's `Files touched`
is the exact surface; every persisted change stamps its schema `version` + `changelog` (CLAUDE.md 11).

### Hard scope - out

| What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- |
| A composite/normalised single score as the gate | No one "quality number" to gate on | Never for the gate - it dilutes the one reliable signal and erases which axis fired (veto chain instead). A displayed "overall" is Row 7's optional console convenience |
| Blocking on coverage, coherence or fluency | Only faithfulness can withhold | A calibration showing that metric's low tail means "bad" and the owner promoting its action to `block` |
| An adaptive percentile as the BLOCK floor | The block binds to the absolute HHEM 0.50 that already ships | Never - a percentile floor drifts up as the summariser improves and silently deletes fine stories |
| A human holdout set (plan 34 has one) | No hand-marked drift alarm | Nothing - plan 34's holdout was its only floor; plan 36's absolute floors replace it, and the record-only corpus turn is the go/no-go |
| Human quality labels for calibration | Bands are set from each metric's own distribution | The owner's standing "no human labour" rule forbids it; distributional bands self-correct |

### Section 0a - what plan 34 taught, and what transfers

Plan 34 built the same loop for the merge line. Every load-bearing piece transfers; the table is the map.

| Plan 34 pattern | Transfers to plan 36 as | Change |
| --- | --- | --- |
| `StorySimilarityDistribution` - fixed-size 120-slot record, folded daily, never grows (Guardrail #12) | `MetricScoreDistribution` - one per metric | Add a `metric` enum; data-parameterised |
| `FittedSimilarityThreshold` - per-day row, proposed/damped/applied, gates, clamp, `held_reason` | `FittedMetricBand` - one per metric per day | Add a `metric` enum; two floors (block, watch) not one line |
| The fit: walk slots from the TOP (NO verdicts), `discard_share`, the `+ bin_width` boundary | The fit: walk from the BOTTOM (low scores) | One direction parameter; the boundary rule is identical and load-bearing |
| One-directional damping: the risky move is damped, the safe move lands at once | Same invariant | The risky move is RAISING the floor (withhold more = invisible deletion), so the raise is damped |
| `enabled` flag ships off; the "Apply" row is the first that changes a published day; everything before writes numbers nobody reads | Same | Row 8 is the Apply row; it lands alone |
| Record-only first: stamp what WOULD happen for a corpus turn before acting | Same | Row 7 stamps `publish_decision` counterfactually; a person reads it once as go/no-go |
| The `LLM-JUDGES` daily workflow hosts the judge; reads committed data, never article bodies | Hosts G-Eval fluency as another leg | Fluency is summary-only, so committed `digest.json` is enough |
| Held reasons, min-days/min-samples gates, settle test, step-change guard | Same, per metric | Faithfulness seeds from committed history, so its gates clear on day one |
| Row 17 measures a real judge call before trusting the leg budget | Row 10 measures a real G-Eval call | Same discipline |
| The console draws the loop on `/console/judgement/` | Adds the quality panels beside the merge panels | Same route |

### Section 0b - the converged design (owner + debate, 2026-09-18)

| # | Decision | Ruling | Authority |
| --- | --- | --- | --- |
| D1 | Instrument all four, or just gate faithfulness? | All four get the full fold/fit/band. The ACTION on crossing is a per-metric config knob: `block` / `downgrade` / `watch`. Fully instrumented; the default action is conservative and promotable. | owner, Andre |
| D2 | Which metric may withhold? | Faithfulness only. A false claim is the one failure where no story beats the story. Coverage and coherence are confounded (reward extractive / reward repetition), so their low tail can be a GOOD summary - default `watch`. Fluency is next-day, so it structurally cannot gate - `watch`. | Andre, Editor |
| D3 | Block floor: absolute or adaptive? | BLOCK on the absolute reader-safety lines that already ship and do not drift: HHEM 0.50 and unsupported-number. The adaptive p01/p05 bands DOWNGRADE (faithfulness) or WATCH (others), never block, until the owner promotes one. | Andre, Editor |
| D4 | A composite score for the gate? | No. Veto chain, like `verdict()`. Averaging dilutes HHEM with confounded signals and erases which axis fired (`doubt-reasons.ts`). A displayed "overall" is console convenience that feeds no action. | Andre, Fowler |
| D5 | Sane defaults with no human labels? | Faithfulness seeds its band from p01/p05 of the ~6,966 committed HHEM readings, filtered to the current `scorer_version`. Coverage/coherence/fluency are record-only until their distribution fills (~5-10 days), then `downgrade`/`watch`. | Andre |
| D6 | Damping direction | Damp the RAISE, drop at once: raising a floor withholds/marks more, which is the invisible-deletion direction. Same invariant as plan 34. For a `downgrade` band the asymmetry is weaker (a marker is visible), so the first fortnight measures whether the direction should differ per action. | Andre |
| D7 | Human holdout? | Killed. Plan 34's holdout was its only floor; the absolute block floors replace it. The safety net is the record-only corpus turn a person reads once before the flag flips - reviewing output, not producing labels. | Fowler |
| D8 | Withhold rate | WATCHed. A thin-but-true digest beats a full-but-false one, but a rising withhold rate is a bad-summariser day an operator must see, not a digest silently going hollow. | Editor |

### Section 0c - critical-review corrections (2026-09-18)

The 2026-09-18 critical review (Andre, Carmack, Fowler, Editor, each verified against the committed
code and the 11,140-row ledger) reshaped the gate. These supersede the 0b rows they cite. Two are owner
decisions (E4, E6) and gate their rows.

| # | Correction | Supersedes | Authority |
| --- | --- | --- | --- |
| E1 | **All adaptive floors are WATCH-only (fleet-rate alarms), none downgrades per item.** Measured: faithfulness p05 = 0.14, but the absolute block 0.50 sits at the ~11th percentile, so the adaptive faithfulness floor is BELOW the block and the "downgrade" band is empty by construction - it can never fire. The only per-item faithfulness reader action is the absolute 0.50 block plus the EXISTING 0.80/0.50 display bands. | D1, D3 | Andre (A2) |
| E2 | **The seed keys on the HHEM instrument sub-identity** (`hhem_rev@rev + weights_digest + window=900/150/anchored`), NOT the whole `scorer_version`. Plan 35 changes `scorer_version` (drops `;lead=`, bumps `metrics-3`->`4`), so a whole-version filter matches 0 of 11,140 rows and day one is empty. Keying on HHEM identity keeps ~8,461 current-geometry rows. | D5 | Andre (A1) |
| E3 | **Symmetric damping for every watch floor.** "Damp the raise" belonged to plan 34's INVISIBLE-deletion trigger; here the withhold is absolute and undamped, and a watch/downgrade floor is a visible/operator signal, so asymmetric damping only ratchets the alarm down under noise and silences it. Resolve now, not after a fortnight. | D6 | Andre (B1) |
| E4 | **SUPERSEDED by 0e H1 (2026-09-19): the reader sees nothing; the withhold is an item-health metric, not a card.** Historical rationale (no longer in force): the Editor proposed degrading a below-0.50 item to a link-only card so the loss stayed visible; the owner instead ruled the item ABSENT from the day and the signal an operator-only item-health metric surfaced in the console. | D2, D8 | Editor proposed; superseded by owner (0e H1) |
| E5 | **State the ~11% steady-state withhold rate; add a length pre-filter.** The 0.50 line is the ~11th percentile, so Row 8 withholds (does not publish) ~11% of items every day, and 24% of that tail is sub-200-word stubs. A length pre-filter (never summarise a stub) and the stated baseline keep D8's alarm from reading 11% as an anomaly. | D8, Row 8 | Andre (B2), Editor |
| E6 | **SUPERSEDED by 0e H5 (2026-09-19): no 3-model peak - coherence runs in `assemble`, not the `work` shard.** Verified: MiniLM is already loaded in the `plan`/`assemble` jobs (it builds the search index) and the summariser is NOT resident there, so coherence scores in `assemble` reusing the loaded MiniLM - summariser + HHEM + MiniLM never coexist in one process. Historical concern (no longer in force): that coherence would be a third resident model on the busy `work` shard. | Row 8 (35), Row 11 (36) | Carmack; corrected by owner (0e H5) |
| E7 | **Where the block lands: BEFORE `collapse_same_story`.** Withdrawing a same-story group's representative after the fold silently deletes every duplicate folded into it and trips `DigestDay`/placement count invariants. Drop/relegate before the fold so the next-best duplicate is promoted, and recompute run/vertical/desk counts. `DigestDay`'s `planned = published + failed` gains a `link_only` term (`planned = published + failed + link_only`), counted on `RunManifest`, with a test that the arithmetic closes. **(The `link_only` DigestDay term is SUPERSEDED by 0e H3: it is dropped - a withheld item counts in `failed`, so `published + failed <= planned` already holds and `digest_day.py` is untouched. The `collapse_same_story` placement above still applies.)** | Row 8 | Fowler (A1, B5) |
| E8 | **The daily judge workflow may be renamed `LLM-JUDGES` -> `LLM-COUNCIL`.** The plan declares ONE dependency line and uses name-agnostic prose ("the daily judge council workflow") everywhere; the runtime (cache key, server start, matrix) is name-independent, so a rename touches only `name:`, `concurrency.group`, and the `_harness.py` expectation in one commit. | 0a, Row 6 | Fowler (B2), Carmack (A6) |
| E9 | **Row 6 (G-Eval leg) depends on Row 10 (measure the call)**, or the leg timeout is a labelled estimate x generous margin - do not repeat plan 34 row 17's sequencing gap. G-Eval is a STEP inside the existing judge legs (reuse the hot server), not a new job. It is monitor-only and feeds no gate (delete-first justification: an operator drift alarm). | Row 6, Row 10 | Carmack (A3, A5), Fowler (C1) |
| E10 | **Two guards to add.** (a) REVISED by 0e J6/J7 (2026-09-19): the corpus is NO LONGER byte-identical gate-off vs gate-on - Row 12 fences withheld items out of the corpus on purpose. The anti-Goodhart guard is instead that the fence reads the stamped `publish_decision` (not `hhem`) and `keeps_its_counterweights` stays faithfulness-free; the rejects store makes the fence auditable. (b) The G-Eval canary asserts CONTAINMENT (`geval` never reaches `publish_decision`) and that thinking is off, not just that the grammar parsed. | Row 8, Row 12, Row 6/10 | Andre (B3, B4); owner (J6/J7) |

Also corrected: the committed HHEM count is 11,140 (8,461 at the current instrument identity), not ~6,966
(E2); the design-of-record doc's remaining "block p01" phrasing is reconciled to the absolute-0.50 block
in the same commit as Row 5.

### Section 0d - round-2 restructure (Fowler + Carmack, 2026-09-18)

The rows were written against 0b (D1-D8) and never reshaped to absorb the 0c corrections (E1-E10). Two
custom agents verified against the tree: most E-items float in 0c with no row owning them, and the
single biggest hole is that **E4 turned "withhold" into a link-only CARD but no row builds it** - Row 8
still says a withheld item "is absent". These corrections bind the rows and add **Row 11**. (Section 0e,
2026-09-19, later REVERSED the E4 link-only card that G1/G2/G3 describe and repurposed Row 11 - read 0e
first; the link-only references in this section are historical.)

**Table A - corrections-to-rows (each floating E-item and gap now has an owner)**

| id | Correction | Owner row | What the row must now do |
| --- | --- | --- | --- |
| G1 | **E4 link-only card has no builder (the critical hole).** | NEW Row 11 | Build the reader-facing card: add published `DigestViewItem.link_only` (bool, default false) + `withheld_reason` (nullable); the `ITEM_FIELDS` allow-list in `frontend/src/lib/payload/project.ts`; a card component (headline + source + "we could not verify our summary" marker, NO summary); a browser smoke. Ships INERT (field false until Row 8). Level-5 additive published contract. |
| G2 | E7 placement (the DigestDay `link_only` term is SUPERSEDED by 0e H3). | Row 8 | Drop/relegate a withheld item BEFORE `collapse_same_story` ([assemble.py:2038](../backend/idhazh/assemble.py)) so the next-best duplicate promotes; recompute run/vertical/desk counts. The `DigestDay` `link_only` term + validator rewrite are DROPPED by 0e H3 - a withheld item counts in `failed`, so `published + failed <= planned` holds and `digest_day.py` is untouched. |
| G3 | E4 makes Row 8's gate self-contradict ("a withheld item is absent"). | Row 8 | The integration gate asserts the withheld item is PRESENT as a link-only card WITHOUT a summary, not absent; Row 8 writes `link_only=true` + `withheld_reason` using Row 11's field. |
| G4 | E5 length pre-filter + the ~11% baseline float. | Row 8 | Add a length pre-filter (never summarise a sub-200-word stub); state the ~11% steady-state link-only baseline so D8's alarm does not read 11% as an anomaly. |
| G5 | E10(a) corpus-harvest test. **REVISED by 0e J6/J7:** the fence (Row 12) excludes withheld items from the corpus, so byte-identity gate-off-vs-on no longer holds. | Row 12 | Integration test: an item stamped `publish_decision == withheld` is excluded by `harvest_rows`, and `keeps_its_counterweights` is unchanged (still reads no `hhem`) - the fence reads the decision, not the score. |
| G6 | E1 all floors WATCH-only; the per-item downgrade band is empty by construction. | Rows 2, 5, 7 | Drop the per-item `downgrade` action; faithfulness's only per-item reader action is the absolute 0.50 block + the existing 0.80/0.50 display bands. Keep the `downgraded` enum value ONLY as a reserved future-promotion member said so on the field, or drop it (G12). |
| G7 | E2 seed keys on the HHEM instrument sub-identity, not `scorer_version`. | Rows 4, 5 | Row 4 folds faithfulness by the HHEM sub-identity (`hhem_rev@rev + weights_digest + window=900/150/anchored`), not the whole `scorer_version` (plan 35 changes it -> 0 of 11,140 match). Row 5 seeds from that key. |
| G8 | E3 symmetric damping floats. | Row 5 | Row 5 dec 2 + oracle: symmetric damping for every watch floor (the withhold is absolute+undamped; a watch floor is an operator signal, so asymmetric damping only ratchets the alarm down under noise). |
| G9 | Row 5 seed is a growing read + a test that walks committed data. | Row 5 | The production seed declares Guardrail #12's escape-hatch (what it reads, why a bounded input cannot answer); the seed TEST uses a bounded fixture, never the committed archive (section 13); cite the PROPERTY ("rows at the current HHEM identity"), never the rotting cardinal 8,461. |
| G10 | E6 coherence 3-model RAM. **SUPERSEDED by 0e H5 (2026-09-19): no peak - coherence runs in `assemble` where MiniLM is already loaded.** | Rows 4, 5, 11 | Row 11 confirms coherence is wired into `assemble` (not the `work` shard) and takes one cheap RSS reading; no eviction, no timeout bump. Coherence is same-day (in `assemble`, after `work`); its action stays `watch` (never gates). |
| G11 | E8 rename touch-points; E9 Row 6/10 sequencing. | Rows 6, 10 | If the `LLM-COUNCIL` rename lands, Row 6 edits only `name:`, `concurrency.group`, `_harness.py`. Row 6's leg timeout is a LABELLED estimate x generous margin and does NOT hard-block on Row 10 (E9); Row 10 measures the merged call after. E10(b): Row 6 canary asserts containment (`geval` never reaches `publish_decision`) + thinking off. |
| G12 | Row 3 dec 1 stale premise; the `downgraded` dead value. | Row 3 | Fix dec 1: a withheld item is ABSENT from the day but recorded in item-health telemetry (0e H1/H2); the `EvalRow` stamp still records every scored item including the withheld. Resolve `publish_decision`: values are `published` \| `withheld`; keep `downgraded` only if reserved for a named future promotion, else drop. |
| G13 | Row 2 omits the contract fixtures + `export.py` tuple. | Row 2 | Name `tests/fixtures/contracts/<stem>/` fixtures for both new contracts and the `CONTRACTS` tuple + import in `export.py`. |
| G14 | The design-of-record doc lags the corrections. | Row 5 + Row 8 commits | Widen the reconciliation: `docs/concepts/summary-quality-autotune.md` drops the faithfulness-downgrades-below-adaptive-floor language (E1), the `block p01` phrasing, and the asymmetric "damp the raise" (E3); the publish-gate section says withhold = absent + item-health telemetry, surfaced in the console (0e H1/H2/H4), NOT a link-only card. |

**Table B - PR-wave grouping (11 PRs across 4 waves; each PR independently green)**

| PR | Wave | Rows | Ships as / why grouped | Depends on |
| --- | --- | --- | --- | --- |
| fit-core | 1 | 1 | pure refactor; plan-34 tests are the oracle | 34 fit on main |
| eval-columns | 1 | 3 | expand-only EvalRow width; `merge=union` carve-out (lands on main before any writer, never branch-stacked) | 35 EvalRow on main |
| metric-fold-fit | 2 | 2, 4, 5 | all edit `ledger.py` + share the two new contracts; fold-before-fit; inert until Row 8 | fit-core, eval-columns |
| geval-leg | 2 | 6 | disjoint island (`quality/geval.py` + the council workflow) | eval-columns |
| publish-gate | 3 | 7 | backend veto chain, record-only, stamps `EvalRow` | metric-fold-fit |
| geval-measure | 3 | 10 | MEASURES -> runs alone (`measure.yml` on a clean runner) | geval-leg |
| coherence-place | 1 | 11 | confirm coherence runs in `assemble` (MiniLM already loaded there); one cheap RSS reading; no peak, no eviction, no timeout bump (0e H5-H7) | 35 coherence scorer |
| console-panels | 3 | 9 | frontend island on `/console/judgement/`; + the not-published/withhold panel from item-health (0e H4) | metric-fold-fit, publish-gate |
| apply-gate | 4 | 8 | ESCALATE, owner sign-off, first published-day change; withhold = absent + item-health (0e H1-H3, E7 placement) | publish-gate |
| rejects-store | 3 | 12 | the `state/rejects/` store + its prune verb + the corpus fence; reads the stamped `publish_decision` (0e Table C) | publish-gate |
| plan34-gaps | 4 | 13 | retro plan-34 latent gaps (space-trap re-arm, thinking-variant, injection live-test note); the space-trap guard is shared with Row 6's G-Eval | 34 landed, geval-leg |

**Peak pool width 2** (Carmack): Rows 1 and 3 are TWO co-roots from t0, not one width-1 head. The serial
spine is `1 -> 2 -> 4 -> 5 -> 7 -> 8` (6 deep); the width-1 point is the TAIL (Row 8), by owner mandate.
Provision 2 workers; `Parallel N = 4` never binds.

**Table C - optimistic-dispatch rule (the CI-idle fix)**

| Edge class | Dispatch base | Why |
| --- | --- | --- |
| Disjoint (1 vs 3; 4 vs 6; 5 vs 10; 11 vs 8) | `origin/main`, at once | no shared file (Row 11 is a backend measure utility, Row 8 is `assemble.py`) |
| Shared-file, shape settled + mechanical (1->2 once `ClampOutcome`/`FitEnd` settle; 4->5 once the `ledger.py` helper settles) | predecessor's BRANCH tip, pre-merge | shape cannot move; pool never idles on CI |
| New persisted contract (2->4/5/7) | wait on `main` | the contract shape is exactly what review moves; fold/fit WRITE it |
| Measuring (6->10) | wait on `main` | Row 10 must call the merged `geval.py`; runs alone anyway |
| ESCALATE / Level-5 (7->8) | wait on `main` + owner sign-off | first change to a published day; lands alone |
| EvalRow width vs the external plan-35 widening | HARD wait on `main` (never optimistic) | `state/scores` is `merge=union`; two open widenings stack silently. After any EvalRow merge, census committed shards for a stacked header. |

### Section 0e - owner rulings, 2026-09-19 (supersede 0d G1/G2/G3, refine E6/G10)

The owner reversed the E4 link-only card and set the coherence-RAM approach. User approval supersedes
the Editor's link-only recommendation and every advisor (CLAUDE.md section 0).

**Table A - the withhold surface (supersedes E4, G1, G2, G3)**

| id | Ruling |
| --- | --- |
| H1 | **A withheld item is NOT published - it is ABSENT from the reader's day.** No link-only card, no reader-facing surface. Row 11's link-only card is RETIRED. Rationale: a below-0.50 faithfulness says our prose is untrustworthy; the reader sees nothing rather than a card, and the signal lives on the operator surface. |
| H2 | **The withhold is a METRIC in item-health telemetry.** A withheld item is `ItemOutcome.failed` with a NEW `FailureCode` member (the summary was written but failed the faithfulness floor) + the `detail`. "Expand columns are necessary" - the enum member is that expansion. The item-health census already feeds the console, so the metric ships with no new persisted reader surface. |
| H3 | **Row 8 simplifies.** The `DigestDay` `link_only` arithmetic term (old G2) is DROPPED - a withheld item counts in `failed`, so `published + failed <= planned` already holds and `digest_day.py` is not touched. The E7 "drop BEFORE `collapse_same_story`" placement STILL applies (promote the next-best duplicate). |
| H4 | **The console surfaces the signal (Row 9).** A not-published/withhold panel on `/console/judgement/` reads item-health: the withhold count, the ~11% baseline (E5), and the reason breakdown by `FailureCode` - the operator's view of what the gate withheld and why. |

**Table B - coherence placement: no 3-model peak (owner + verified, 2026-09-19; supersedes the earlier eviction design)**

| id | Ruling |
| --- | --- |
| H5 | **No 3-model peak: coherence runs in `assemble`.** MiniLM is already loaded in the `plan`/`assemble` jobs to build the search index, and the summariser is NOT resident there (it lives only in the `work` shard, with HHEM). So coherence scores in `assemble`, reusing the loaded MiniLM - summariser + HHEM + MiniLM never coexist in one process. The sequential-eviction machinery the earlier design feared is unnecessary. |
| H6 | **Row 11 collapses to a confirmation.** It confirms coherence is wired into `assemble` (not the `work` shard, plan 35 Row 8) and takes one cheap RSS reading in `assemble` (MiniLM + the ROUGE work) to show it fits with headroom. No server-stop step, no two-phase `work` shard, no eviction. |
| H7 | **The 200 -> 220 shard-timeout bump is RETIRED** - it existed only for the two-pass `work` shard, which is gone. `assemble` absorbs coherence's ~0.16 s/item (a few tens of seconds over a day). Keep a timeout bump only if a separate measurement asks for it; it is not part of this plan. |

**Table C - the rejects store (owner, 2026-09-19; adds Row 12)**

| id | Ruling |
| --- | --- |
| J1 | **Persist every withheld summary for troubleshooting.** Today a withheld summary's TEXT survives nowhere committed (only the discarded run intermediate); the `EvalRow` keeps the scores + a one-way hash, not the prose - so the gate deletes ~11% of items daily and erases its own evidence. Row 12 adds a committed, fully-sharded store: `state/rejects/<YYYY>/<MM>/<DD>/<item_id>.json`, one `RejectRow` per withheld item. |
| J2 | **What the `RejectRow` carries** (for a person or a bigger model to judge later, never a reader): `title`, `summary` (the failing prose), `source_text` (the sanitised extract the model read), `prompt` (the rendered system + user turns), the failure (`hhem`, `withheld_reason`, `band`, `scorer_version`), the summariser fingerprint (model + decode), identity (`item_id`, `url_key`, `canonical_url`, `source_id`), provenance (`version`, `generated_at`, `run_id`). |
| J3 | **Source text is committed here - a second carve-out beyond `corpus/` (CLAUDE.md 0a).** The owner authorised it (2026-09-19); the executing PR amends 0a to write BOTH carve-outs - the `corpus/` one (today only cross-referenced from section 8) and `state/rejects/` - so 0a becomes the canonical list (S5 A1). It is sanitised extract (crossed the trust boundary once at extraction, Guardrail #11), stored as data a person or an offline judge reads - never re-fed to a model as instruction. Bounded by J4. |
| J4 | **Prune prose and source together, tightly: 30 days, config-driven.** A new knob (`finetune.reject_window_days`, default 30 - tighter than the corpus's 60) + its own verb (`retention.prune_rejects`) wired into the retention prune, deleting whole day directories past the window; the history bytes ride `prune.yml`'s force-push on the same schedule. |
| J5 | **Never served.** `state/rejects/` stays unwired from `payload.ts`, the telemetry projection, the embed/index input, and the `DigestViewItem`/`ITEM_FIELDS` allow-list. The console (Row 9) plots only the aggregate - the rate, the reasons, the withheld-tail score distribution - never the prose or the source. |
| J6 | **Fence the corpus: never train on a withheld summary.** The harvest reads `items/` directly ([corpus.py:217](../backend/idhazh/corpus.py)), so a withheld summary IS harvested today. Row 12 skips any `Scored` whose `EvalRow.publish_decision == withheld`, placed BEFORE `keeps_its_counterweights` - reading the stamped DECISION, not the raw `hhem`, so `keeps_its_counterweights` stays faithfulness-free (Andre's anti-monitor-selector rule holds). |
| J7 | **This inverts E10(a) on purpose, and the store is the safety net.** E10(a) pinned "corpus byte-identical gate-off vs gate-on"; the fence deliberately breaks that (do not train on what we blocked). The Goodhart risk - training only on high-HHEM prose teaches the model to game HHEM - is mitigated because the store makes the fence AUDITABLE: a bigger model or a human reads the withheld tail offline and confirms the floor catches real failures rather than deleting good summaries. E10(a) + G5 + Row 8's gate are revised to match. |
| J8 | **Replaces the "extend the human label draw" idea.** That would feed withheld items back into the live label queue and muddy the distribution-based autotune (owner). Instead the store is the substrate for offline judging (bigger model or human), never reader-facing; the label queue is untouched. |

Note: `state/rejects/` is committed, so the withheld prose lives in the repository (not the digest, not
the Pages site). If the repository is public it is browsable there for the 30-day window; the prune +
`prune.yml` force-push bound it. The owner accepts this to have a committed, queryable store rather than
an expiring CI artifact - revisit if the repository's visibility changes.

TODO (a note, not a plan row; distils to `docs/` per distill-a-plan.md): the OFFLINE JUDGE that reads
the rejects store - a bigger model or a person auditing the withheld tail (J7/J8) - is a deferred
follow-up with no row in this plan. When this plan distils it moves to
`docs/concepts/summary-quality-autotune.md` as the named future consumer that makes the corpus-fence
auditable.

## Section 1 - Status Reckoner

The round-2 review regroups the thirteen rows into **11 PRs across 4 waves** (section 0d Table B). A row's
`Parallel-group` names its wave + PR; readiness is computed from `Depends-on` + a `Files touched`
disjointness check, never the letter (execute-a-plan.md).

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Extract the fit core, direction-parameterised | 34-fit merged | W1 / fit-core | PENDING | - | - | - |
| 3 | `EvalRow`: `geval`, `publish_decision`, `withheld_reason` | 35-EvalRow merged | W1 / eval-columns | PENDING | - | - | - |
| 2 | The two contracts + the per-metric knob block, inert | 1 | W2 / metric-fold-fit | PENDING | - | - | - |
| 4 | The fold: per-metric distributions (HHEM sub-identity key, G7) | 2, 3 | W2 / metric-fold-fit | PENDING | - | - | - |
| 5 | The fit + seed faithfulness (symmetric damping, bounded fixture) | 1, 2, 4 | W2 / metric-fold-fit | PENDING | - | - | - |
| 6 | G-Eval fluency judge in the council (estimate x margin timeout) | 3 | W2 / geval-leg | PENDING | - | - | - |
| 7 | The veto-chain publish gate, record-only | 2, 3, 5 | W3 / publish-gate | PENDING | - | - | - |
| 10 | Measure a real G-Eval call; replace the estimate | 6 | W3 / geval-measure (alone) | PENDING | - | - | - |
| 11 | Confirm coherence runs in `assemble` (MiniLM loaded there); no peak, no eviction | 35 coherence | W1 / coherence-place (alone) | PENDING | - | - | - |
| 9 | Console: the quality bands + the not-published/withhold panel | 5, 7 | W3 / console-panels | PENDING | - | - | - |
| 8 | Flip the flag: withhold = absent + item-health telemetry (E7 placement) | 7 | W4 / apply-gate (alone) | PENDING (ESCALATE) | - | - | - |
| 12 | The rejects store + corpus fence (`state/rejects/`, 30-day prune) | 3, 7 | W3 / rejects-store | PENDING | - | - | - |
| 13 | Retro: plan-34 latent gaps + the shared space-trap guard | 34 landed, 6 | W4 / plan34-gaps | PENDING | - | - | - |

## Section 2 - Row detail

### Row #1 - extract the fit core, direction-parameterised

- **Scope:** move plan 34's fit arithmetic into a neutral, contract-free logic package both plans call,
  parameterised on which tail it walks. Behaviour-preserving for plan 34.
- **Files touched:** new `backend/idhazh/fitting/edge.py` (imports stdlib only; takes a `Sequence[int]`
  of cost-counts, the band edges, `bin_width`, `previous`, the knobs; returns plain values and a frozen
  `ClampOutcome`); `backend/idhazh/similarity/fit.py` becomes a thin adapter (Distribution -> primitives
  -> core).
- **Acceptance gates:** plan 34's `backend/tests/test_similarity_fit.py` stays byte-for-byte green;
  new unit tests drive `edge.py` with both `FitEnd.TOP` and `FitEnd.BOTTOM` primitives.
- **Oracle:** for a built count array, `FitEnd.TOP` returns the upper edge plan 34 returns and
  `FitEnd.BOTTOM` returns the lower edge; it cannot settle whether the quality direction is
  semantically right (that is Row 5 against real scores).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Extract at the second user; the `+ bin_width` boundary is a reader-facing correctness invariant, so rule-of-three yields | Fowler |
  | 2 | Direction is one parameter (`FitEnd`), so a caller cannot mismatch walk and returned edge | Fowler |
  | 3 | `ClampKind` stays a per-Band wire enum; the core returns a neutral `ClampOutcome.kind` each adapter maps | Fowler |

### Row #2 - the two contracts + the per-metric knob block

- **Scope:** `MetricScoreDistribution` (fixed-size, one file per metric) and `FittedMetricBand` (one
  row per metric per day), both carrying a `metric: MetricId` enum, plus a per-metric `MetricBandConfig`
  knob block, `enabled` off. Nothing reads or writes them yet.
- **Files touched:** `backend/idhazh/contracts/metric_score_distribution.py`,
  `backend/idhazh/contracts/fitted_metric_band.py` (declares `MetricId`, `ClampKind`, `HeldReason`,
  `MetricAction`), `backend/idhazh/contracts/knobs/evaluation.py` (the `MetricBandConfig` block),
  `backend/idhazh/contracts/export.py` + regenerated schemas, `backend/idhazh/ledger.py` (paths),
  committed seed distributions, `config/idhazh.json`, `config/appearance.json` if a console knob lands.
- **Acceptance gates:** contract drift gate; contract tests over the validators (band divides into
  slots, slot count matches, a date folds once - the plan 34 shapes); a fresh clone runs on the
  defaults with `enabled` off.
- **Oracle:** a fitted band without its two floors, or a distribution whose slots miss the grid, is
  refused; it cannot settle whether the seeded faithfulness floor is a good number (Row 5).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | One Distribution + one Band contract, data-parameterised by `metric`; adding a metric is an enum member + a config block, not a new contract | Fowler |
  | 2 | One file per metric under `state/summary-quality/<metric>/`, so the fold-once guard and the input-change archive fire per metric | Fowler |
  | 3 | `MetricAction` is `block`, `downgrade`, or `watch`; the knob's default is `block` for faithfulness, `watch` for the rest (D2) | Andre, Editor |
  | 4 | The band carries two floors - a block floor and a watch floor - not one line (D3) | Andre |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | One shared distribution file for all four metrics | Couples their cadence; a single archive-on-input-change would reset all four when one scorer moves | - | Fowler |
  | 2 | A `scored-pairs`-style per-item tree | Per-item scores already persist in `EvalRow`; a second copy is a second answer | - | Fowler |

### Row #3 - `EvalRow`: the three new columns

- **Scope:** add `geval` (fluency 0-1, nullable), `publish_decision` (`published`|`withheld`, default
  `published`; `downgraded` is a RESERVED future-promotion value that nothing stamps today - E1 makes the
  per-item downgrade band empty, G6/G12), `withheld_reason` (a `MetricId`-or-`unsupported_number` enum,
  nullable) to the committed eval ledger. Expand only; nothing writes the decision yet.
- **Files touched:** `backend/idhazh/contracts/eval_row.py` (+ schema + changelog + version), the
  read-side tolerance for old shards, the affected tests.
- **Acceptance gates:** contract drift gate; a fixture read of an old shard that omits all three columns
  (defaults on read); no positional CSV reader exists (header-keyed).
- **Oracle:** an old `state/scores` row without the columns validates and reads back `published`; it
  cannot settle whether the gate ever writes `withheld` (Row 7).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The stamp lives on `EvalRow`, not the published item: a withheld item is ABSENT from the day, so it cannot be stamped there, and `EvalRow` records every scored item including the withheld | Fowler |
  | 2 | `hhem` and `coverage` already exist; `coherence`/`semantic_coverage` are added by plan 35 row 8; plan 36 only adds `geval` + the two decision columns | Fowler |

### Row #4 - the fold

- **Scope:** read one committed day's `EvalRow`s and fold each metric's scores into that metric's
  fixed-size distribution, one slot each, dropping nothing. Archive and restart a distribution when its
  scorer version, band edges or slot width moved (plan 34's `inputs_changed`).
- **Files touched:** new `backend/idhazh/quality/fold.py`, `backend/idhazh/stages/quality_fold.py`,
  `backend/idhazh/ledger.py` (append/load for the distribution).
- **Acceptance gates:** unit tests over a built day of `EvalRow`s and a built distribution; a fold of a
  date already folded raises; a moved `scorer_version` archives and restarts.
- **Oracle:** a score lands in the slot whose edge it clears, and a re-fold of one date is refused; it
  reads one named day file, never the ledger tree (Guardrail #12).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The fold reads `EvalRow` one day at a time by date, never the whole ledger | Fowler, Carmack |
  | 2 | Faithfulness folds only rows under the current `scorer_version` (D5), so p01 is not a mixture artefact | Andre |

### Row #5 - the fit

- **Scope:** for each metric, walk its distribution from the low tail and write a `FittedMetricBand`
  row: the block floor (absolute, from config), the watch floor (adaptive p05, damped/clamped/gated),
  and the held reason on a day nothing moved. Seed faithfulness from committed HHEM history so its
  gates clear on day one.
- **Files touched:** new `backend/idhazh/quality/fit.py` (the second `edge.py` adapter),
  `backend/idhazh/stages/quality_fit.py`, `backend/idhazh/ledger.py`, a seeding step that reads the
  committed HHEM readings once, and **`docs/concepts/summary-quality-autotune.md`** (G14) - strike the
  four stale phrases: faithfulness-downgrades-below-an-adaptive-floor (E1), `block p01` (E1), the
  asymmetric "damp the raise" (E3), and any "coherence runs same-day in the work shard" wording
  (coherence runs in `assemble`, 0e H5).
- **Acceptance gates:** unit tests over built distributions per metric; the seed test builds the
  faithfulness distribution from committed readings and asserts its floors are non-null on day one;
  each gate writes its own `held_reason` and moves nothing.
- **Oracle:** the watch floor is the lower edge of the slot the low-tail walk stopped in, and a rise is
  damped while a fall lands at once (D6); it cannot settle whether p05 correlates with human quality
  (out of scope - no labels, D5).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The block floor is the absolute config line (HHEM 0.50); only the watch floor is adaptive (D3) | Andre |
  | 2 | Damp the raise, drop at once (D6); the `downgrade`-band direction is recorded-and-measured over the first fortnight | Andre |
  | 3 | Faithfulness seeds from p01/p05 of committed readings; the others are record-only until filled (D5) | Andre |

### Row #6 - G-Eval fluency judge in the council

- **Scope:** the summariser judges its own summaries' fluency on a 1-5 scale, one grammar-constrained
  digit scored from the first-token probabilities, on a stratified sample of ~30 summaries a day, in
  the existing `LLM-JUDGES` workflow. Input is the summary only. Writes `geval` onto the sampled rows.
- **Files touched:** new `backend/idhazh/quality/geval.py` (mirrors `backend/idhazh/similarity/judge.py`;
  a new payload builder adding `post_sampling_probs`, not the same-story judge's), a fluency rubric
  prompt, `backend/idhazh/stages/quality_geval.py`, one leg/step added to `.github/workflows/llm-judges.yml`.
- **Acceptance gates:** a recorded-completion test proves the digit distribution maps to the expected
  score; no network (Guardrail #7); an injection canary (a summary carrying "rate this 5" still scored
  from log-probs under the grammar); **the shared space-trap guard (Row 13) - assert the rendered
  fluency prompt does not end in a space and build the digit token ids by encode-in-position, so a
  trailing-space token cannot silently shift which digit the model emits.**
- **Oracle:** the score reproduces from a recorded completion's first-token log-probs; it never judges
  consistency (circularity - HHEM keeps that).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Reuse the summariser; probability-weighted first-token score; fluency only | Andre |
  | 2 | Sample ~30/day stratified by desk; the council is a drift monitor, so a sample is honest | Carmack |
  | 3 | No chain-of-thought by default (decode is the cost at 4 tok/s); if added, Row 10 re-prices it | Carmack |

### Row #7 - the veto-chain publish gate, record-only

- **Scope:** for each scored item, read each metric's action-config and its floor and stamp
  `publish_decision` + `withheld_reason` on the `EvalRow`. RECORD-ONLY: assemble still publishes
  everything; the stamp is counterfactual. Optionally compute a displayed "overall" that feeds no action.
- **Files touched:** new `backend/idhazh/quality/gate.py` (the veto chain),
  `backend/idhazh/evals/score.py` (`to_eval_row` stamps the decision), the console reader.
- **Acceptance gates:** unit tests over built items and built bands: a faithfulness reading below the
  absolute block floor stamps `withheld`; a reading in the watch band stamps nothing per item (watch is
  a fleet-rate alarm, not a per-item action - E1); a low coverage stamps nothing under the default
  `watch`; the bite - flip coverage's action to `block` and the same item stamps `withheld`.
- **Oracle:** the veto chain stamps the most severe action any metric earned and names the metric that
  earned it; it changes no published day (record-only).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Veto chain, not a composite; the reason names the metric (D4) | Andre, Fowler |
  | 2 | Record-only first; a person reads the counterfactual withheld list once as go/no-go before Row 8 (D7) | Fowler, Editor |
  | 3 | A displayed "overall", if built, is labelled a display aggregate that feeds no action | Andre |

### Row #8 - flip the flag - ESCALATE

- **Scope:** assemble reads the `EvalRow` stamp and acts. A `withheld` (below-absolute-floor)
  faithfulness item does NOT publish - it is ABSENT from the reader's day, no card, no reader-facing
  surface (0e H1). The withhold is recorded in item-health telemetry as `ItemOutcome.failed` with a new
  `FailureCode` (the summary was written but failed the faithfulness floor) + the `detail`, so the
  operator has the metric and the reason (0e H2). The drop/relegate happens BEFORE `collapse_same_story`
  ([assemble.py:2038](../backend/idhazh/assemble.py)) so the next-best duplicate promotes (E7). A length
  pre-filter never summarises a sub-200-word stub (E5). Behind `publish_gate.enabled`, ships off; the
  first row that changes a published day.
- **Files touched:** `backend/idhazh/stages/assemble.py` (drop a withheld item before the fold, record
  the item-health row, recompute run/vertical/desk counts), `backend/idhazh/contracts/item_health.py`
  (the new `FailureCode` member + schema/version/changelog, 0e H2), `config/idhazh.json`
  (`publish_gate.enabled` + the stub-length floor, removal condition on the declaring line).
  `digest_day.py` is NOT touched - a withheld item counts in `failed`, so `published + failed <= planned`
  already holds (0e H3).
- **Acceptance gates:** integration over the canary day, built once gate-off and once gate-on, asserting
  a withheld item is ABSENT from the day and PRESENT in item-health with the new `FailureCode` + detail
  (0e H2), and the `published + failed <= planned` invariant still closes; browser smoke that the day
  renders with an item withheld and when the band tree is absent. (The corpus fence + its test move to
  Row 12; the old byte-identity assertion is retired, 0e J6/J7.)
- **Oracle:** with the flag off, every published day is byte-identical to today; with it on, a
  below-absolute-floor item is absent from the day and carries an item-health row naming why, and the
  story's next-best duplicate is promoted; it cannot settle the editorial cost of a thin day (D8 - the
  not-published rate is watched on the console at the stated ~11% baseline, E5).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Lands alone, after a corpus turn of record-only review; owner sign-off (Level 5) | owner, Fowler |
  | 2 | Only faithfulness withholds; coverage/coherence are watch-only (E1) and never withhold; the owner sets the absolute floor and permits withholding (reader-safety boundary) | Editor, owner |

### Row #9 - console: the quality bands

- **Scope:** add panels to `/console/judgement/` drawing each metric's distribution, its fitted floors
  over time, and the record-only counterfactual list a person reviews before Row 8. Add a not-published
  / withhold panel that reads item-health: the withhold count, the ~11% baseline (E5), and the reason
  breakdown by `FailureCode` - the operator's view of what the gate withheld and why (0e H4).
- **Files touched:** `frontend/src/routes/console/judgement/*.svelte`, a console reader under
  `frontend/src/lib/console/`, the affected browser specs.
- **Acceptance gates:** frontend `test:changed`; browser smoke per section 12, including the data-absent
  arm (rebuild with an empty band tree, confirm the panel draws its axis and its empty-state copy).
- **Oracle:** the browser oracle re-derives each drawn floor from the committed band shard; it cannot
  settle whether the panel reads well (Susan's sufficiency check).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The not-published/withhold rate is a first-class panel with its own alarm, read from item-health (D8, 0e H4) | Editor |
  | 2 | A tiny glyph links each metric to `docs/concepts/summary-quality-autotune.md` | Susan |

### Row #10 - measure a real G-Eval call

- **Scope:** measure a real fluency G-Eval call on a stock `ubuntu-latest`, prefill and decode
  separately, over at least 20 calls, and replace the ~28 s estimate that sizes the council leg.
- **Files touched:** new `backend/utilities/measure_geval_call.py`, a `workflow_dispatch` job in
  `.github/workflows/measure.yml`, `docs/reference/benchmarks/what-a-geval-call-costs.md`,
  `docs/reference/measurements.md`.
- **Acceptance gates:** unit tests over built readings (the cold call is reported not averaged, a run
  stopped on the clock reports what it got); the record names the weights and the processor it drew.
- **Oracle:** the record reproduces its statistics from the committed `calls.jsonl`; it cannot settle a
  different runner's number (the processor lottery is named).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Measure prefill (summary + rubric) and decode (confirm it is one digit, not generated CoT) separately; worst x 30 sizes the leg, never the mean | Carmack |

### Row #11 - confirm coherence runs in `assemble` (no 3-model peak)

- **Scope:** confirm coherence (plan 35's MiniLM scorer) is wired into the `assemble` job, where MiniLM
  is ALREADY loaded to build the search index and the summariser is NOT resident - so the feared
  3-model peak (summariser + HHEM + MiniLM) never occurs (0e H5). Take one cheap RSS reading in
  `assemble` to show MiniLM + the coherence/ROUGE work fits with headroom.
- **Files touched:** confirm plan 35 Row 8 wired coherence into `assemble` (not `work`); a one-off RSS
  reading recorded in `docs/reference/measurements.md`. NO server-stop step, NO two-phase `work` shard,
  NO `shard_timeout_minutes` change - all retired with the eviction (0e H7).
- **Acceptance gates:** the reading shows the `assemble` peak RSS (MiniLM + ROUGE, no summariser) fits
  16 GB with headroom, hardware + date named (Guardrail #10); coherence scores land on the same day's
  eval rows.
- **Oracle:** coherence is computed in `assemble` and the `work` shard's peak is unchanged (summariser
  + HHEM only). It cannot settle a future model swap's footprint (re-measure then).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Coherence runs in `assemble`, reusing the MiniLM already loaded for the search index; no 3-model peak (0e H5, corrected 2026-09-19) | owner, Carmack |
  | 2 | The sequential server-eviction + two-phase `work` shard + the 200->220 timeout are RETIRED - they solved a peak that does not occur | owner |

### Row #12 - the rejects store + the corpus fence (`state/rejects/`, 30-day prune)

- **Intent:** capture every withheld summary with enough context to investigate WHY it failed - offline,
  by a person or a bigger model, NEVER shown to a reader - and stop training the model on summaries we
  blocked. Row 8 removes the item; Row 12 keeps the evidence and fences the corpus (owner, 2026-09-19;
  section 0e Table C).
- **Scope + files touched:**
  - **The contract:** new `RejectRow` in `backend/idhazh/contracts/reject_row.py` + generated
    `schemas/reject-row.schema.json` + the `CONTRACTS` tuple/import in `contracts/export.py` + a
    `tests/fixtures/contracts/reject-row/` round-trip fixture. Fields per 0e J2; `version` + one
    `changelog`.
  - **The write:** at the record-only gate (`backend/idhazh/quality/gate.py`, Row 7), when an item is
    stamped `withheld`, write `state/rejects/<YYYY>/<MM>/<DD>/<item_id>.json` (temp-file-plus-rename,
    one item one file - no `merge=union`). The summary, article extract and scores are already in hand;
    render the prompt with `summarize.system_prompt(...)` + `summarize.user_turn(...)` (the same
    reconstruction the corpus harvest uses at [corpus.py:400](../backend/idhazh/corpus.py)) so the
    stored prompt is the exact one the model saw. Reuse the `ledger` / day-partition helpers.
  - **The prune:** a `finetune.reject_window_days` knob (default 30) + `retention.prune_rejects` wired
    into `backend/idhazh/stages/prune_state.py` beside `prune_traces`, deleting whole day directories
    past the window (the `keep-future-dated` guard applies unchanged).
  - **The corpus fence:** in `backend/idhazh/corpus.py` `harvest_rows`, skip any `Scored` whose
    `row.publish_decision == withheld` BEFORE `keeps_its_counterweights` (which stays `hhem`-free). Do
    NOT add `hhem` to `keeps_its_counterweights` (0e J6).
  - **The 0a amendment + docs:** amend `CLAUDE.md` section 0a to write BOTH committed-article-text
    carve-outs (S5 A1, owner 2026-09-19): the `corpus/` one FIRST (today it is only cross-referenced
    from section 8, never stated in 0a) and `state/rejects/` SECOND, bounded by the 30-day prune (0e J3),
    so section 0a becomes the canonical list. Document the store + the fence in
    `docs/how-to/fine-tune-a-model.md` and the design-of-record.
- **Acceptance gates:** contract drift gate (the new schema regenerates byte-identical); a unit test
  that a withheld item writes exactly one `RejectRow` carrying the prose + source + rendered prompt
  (driven from a bounded fixture, never the archive); a `harvest_rows` test that an item stamped
  `withheld` is excluded from the corpus while a published sibling stays, and `keeps_its_counterweights`
  still reads no `hhem`; a prune test on a bounded fixture that a day past the window is deleted. No
  test walks the committed store (section 13, Guardrail #12).
- **Oracle:** for a built withheld item, a `RejectRow` round-trips with the failing prose, the source
  extract and the exact rendered prompt, and the corpus harvest drops it. It cannot settle whether the
  0.50 floor is well-calibrated - that is the offline judge the store exists to feed (J8), out of scope.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | A committed JSON payload store (not a CSV ledger - prose has newlines), one file per item, day-sharded, on the `state/traces/` pattern | Fowler |
  | 2 | Source text committed here, a second 0a carve-out, bounded by a 30-day config-driven prune | owner (J3/J4) |
  | 3 | The corpus fence reads the stamped `publish_decision`, never `hhem`; `keeps_its_counterweights` stays faithfulness-free | Andre, owner (J6) |
  | 4 | The store is the auditable safety net that makes fencing the corpus sound despite the Goodhart risk; offline judging (bigger model or human) reads it, never a reader (J7/J8) | Andre, owner |

### Row #13 - retro: plan-34 latent gaps + the shared space-trap guard

- **Intent:** three defects flagged during the plan-34 review were never given a home (out of scope for
  plan 34's merge). They land here as the last row because one - the first-token-probability space trap -
  is re-introduced by Row 6's G-Eval fluency judge, so the guard is shared (owner, 2026-09-19).
- **Scope + files touched:**
  - **Space-trap re-arm:** a trailing-space token in a rendered prompt silently shifts which
    digit/verdict the model emits from its first-token probabilities, and the output still parses.
    Assert the rendered prompt does not end in a space; build the digit/verdict token ids by
    encode-in-position (not by string); log all first-token probabilities. Covers
    `backend/idhazh/similarity/judge.py` (plan 34) and `backend/idhazh/quality/geval.py` (Row 6).
  - **Thinking-variant:** confirm `thinking` is OFF for every judge/council call and pin it with a canary
    that a thinking-on recorded completion is REJECTED, not silently scored (plan 34 + Row 6).
  - **Injection live-test note:** the injection canary runs against a RECORDED completion only (Guardrail
    #7 forbids a live server in tests), so it proves the grammar + log-prob read resists a side-loaded
    instruction in the fixture, not a live model. State this as accepted-by-contract in one line; a live
    red-team is a separate, out-of-scope follow-up.
- **Acceptance gates:** the space-trap + thinking-off canaries pass against recorded fixtures for BOTH
  the plan-34 judge and Row 6's G-Eval; no network (Guardrail #7).
- **Oracle:** a rendered prompt ending in a space fails the guard, and a thinking-on recorded completion
  is rejected. It cannot settle live-model injection resistance (accepted-by-contract, Guardrail #7).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Retro plan-34 gaps re-homed here as the last row (owner, 2026-09-19); the space-trap guard is shared with Row 6 because both read first-token probabilities | owner, Andre |
  | 2 | The injection test stays recorded-fixture only (Guardrail #7); a live red-team is a separate, out-of-scope follow-up | Andre |

## Section 3 - the loop, and where it is documented

The design of record, with the mermaid and the formulas, is
[`docs/concepts/summary-quality-autotune.md`](../docs/concepts/summary-quality-autotune.md). That page
carries the four metrics, how each is measured, the fold-fit loop, and the publish gate; this plan
sizes the rows that build it. When Row 8 lands, the page's "target design (in flight)" framing is
removed in the same commit.

## See also

- [`docs/architecture/publishing/same-story.md`](../docs/architecture/publishing/same-story.md) - the
  merge line that fits itself: the loop this plan mirrors, and the fit core Row 1 extracts.
- [`20260918-35-search-eval-key-points-plan.md`](20260918-35-search-eval-key-points-plan.md) - the
  cleanup and the recorded-only scorers this plan consumes.
- [`docs/concepts/summary-quality-autotune.md`](../docs/concepts/summary-quality-autotune.md) - the
  metrics, the formulas, and the loop diagram.
