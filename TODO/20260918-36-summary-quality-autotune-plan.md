# Plan 36 - the summariser grades itself, and content decides its future

**Created**: 2026-09-18
**Depends on**: plan 34's fit core (rows 5-8) merged; plan 35's `EvalRow` churn (rows 6, 7, 8) merged
**Correction level**: 5 - a model verdict decides what a reader is shown

## Start here - the handoff

Every summary already gets a faithfulness score (HHEM) the day it is written. That number sets a
display badge and nothing else: the item publishes whatever the badge says. This plan closes the loop
plan 34 opened for the merge line, for summary quality: measure every summary on four axes, fit a band
to each axis from its own rolling distribution with no human in the loop, and let the band decide
whether a summary publishes, publishes with a marker, or is withheld.

**The one sentence that orders every decision here, taken from plan 34 and still true: withholding a
story the reader never sees is an invisible loss; publishing a weak summary is a visible, recoverable
one. Only one of those is invisible.** So the default is to publish, the only failure that withholds is
a false claim, and the floor that withholds is an absolute line that does not drift.

**Execution stamp** (per [`docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md)):

```
Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes, and until plan 34's fit core and plan 35's EvalRow churn are on main.
```

## Section 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | The auto-tune is half-built: plan 35 measures four quality axes but nothing acts on them. This fits an adaptive band to each axis and gates publication on it, mirroring plan 34's proven loop. |
| Hard scope - in | Two new contracts (`MetricScoreDistribution`, `FittedMetricBand`); three `EvalRow` columns; the fold and fit stages; the G-Eval fluency judge in the `LLM-JUDGES` council; the veto-chain publish gate (record-only, then flagged on); the console panels; a G-Eval cost measurement. |
| Hard scope - out | see table below |
| ESCALATE triggers | (1) Row 8 flips the flag and withholds items - the first change to a published day, lands alone, owner sign-off. (2) promoting any metric's action from `watch`/`downgrade` to `block` - owner, on a track record. |
| Chosen strategy | Reuse plan 34 wholesale: extract its fit core direction-parameterised, mint data-parameterised per-metric contracts, host G-Eval on the existing `LLM-JUDGES` workflow, ship the gate record-only behind a flag. Owner + convergence debate, 2026-09-18. |
| Execution | autonomous orchestrator per docs/how-to/execute-a-plan.md, after the two dependencies land. Parallel N = 4; the running-pool orchestration + 8-PR wave grouping is section 0d. Stamp above; AUTHOR-AND-STOP until the user authorizes. |

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
| E4 | **Withhold = suppress our summary, keep the link (owner decision).** A below-0.50 faithfulness says OUR PROSE is untrustworthy, not that no story exists. Recommended: a blocked item degrades to a LINK-ONLY card (headline + source + a strong "we could not verify our summary" marker) - it carries no summary, so no false claim, and it is the visible/recoverable loss not the invisible one. The owner rules whether a below-0.50 (high-salience) story may appear link-only, and the max-withhold-fraction floor below which the least-bad items publish link-only rather than the digest going hollow. | D2, D8 | Editor proposes; owner rules (reader-safety boundary) |
| E5 | **State the ~11% steady-state block rate; add a length pre-filter.** The 0.50 line is the ~11th percentile, so Row 8 turns ~11% of items link-only every day, and 24% of that tail is sub-200-word stubs. A length pre-filter (never summarise a stub) and the stated baseline keep D8's alarm from reading 11% as an anomaly. | D8, Row 8 | Andre (B2), Editor |
| E6 | **Coherence RAM (owner decision, plan 35 Row 8's premise too).** MiniLM would be a THIRD resident model on the digest worker (summariser server ~14.31 GiB = 96% of 16 GB, + HHEM in-process, + MiniLM); "encoder already loaded" is FALSE (it loads in the plan job, not the work shard). Measure the 3-model peak RSS before coherence ships same-day; if the margin is under MiniLM's footprint, coherence runs NEXT-DAY (it is summary-only) and only coverage stays same-day. | Row 8 (35), Row 8 (36) | Carmack (A1/A2); owner on the measurement |
| E7 | **Where the block lands: BEFORE `collapse_same_story`.** Withdrawing a same-story group's representative after the fold silently deletes every duplicate folded into it and trips `DigestDay`/placement count invariants. Drop/relegate before the fold so the next-best duplicate is promoted, and recompute run/vertical/desk counts. `DigestDay`'s `planned = published + failed` gains a `link_only` term (`planned = published + failed + link_only`), counted on `RunManifest`, with a test that the arithmetic closes. | Row 8 | Fowler (A1, B5) |
| E8 | **The daily judge workflow may be renamed `LLM-JUDGES` -> `LLM-COUNCIL`.** The plan declares ONE dependency line and uses name-agnostic prose ("the daily judge council workflow") everywhere; the runtime (cache key, server start, matrix) is name-independent, so a rename touches only `name:`, `concurrency.group`, and the `_harness.py` expectation in one commit. | 0a, Row 6 | Fowler (B2), Carmack (A6) |
| E9 | **Row 6 (G-Eval leg) depends on Row 10 (measure the call)**, or the leg timeout is a labelled estimate x generous margin - do not repeat plan 34 row 17's sequencing gap. G-Eval is a STEP inside the existing judge legs (reuse the hot server), not a new job. It is monitor-only and feeds no gate (delete-first justification: an operator drift alarm). | Row 6, Row 10 | Carmack (A3, A5), Fowler (C1) |
| E10 | **Two guards to add.** (a) An integration test that the corpus harvest output is byte-identical with the gate off and on (a link-only/withheld item is still harvested from `items/` upstream of assemble), pinning the anti-Goodhart invariant. (b) The G-Eval canary asserts CONTAINMENT (`geval` never reaches `publish_decision`) and that thinking is off, not just that the grammar parsed. | Row 8, Row 6/10 | Andre (B3, B4) |

Also corrected: the committed HHEM count is 11,140 (8,461 at the current instrument identity), not ~6,966
(E2); the design-of-record doc's remaining "block p01" phrasing is reconciled to the absolute-0.50 block
in the same commit as Row 5.

### Section 0d - round-2 restructure (Fowler + Carmack, 2026-09-18)

The rows were written against 0b (D1-D8) and never reshaped to absorb the 0c corrections (E1-E10). Two
custom agents verified against the tree: most E-items float in 0c with no row owning them, and the
single biggest hole is that **E4 turned "withhold" into a link-only CARD but no row builds it** - Row 8
still says a withheld item "is absent". These corrections bind the rows and add **Row 11**.

**Table A - corrections-to-rows (each floating E-item and gap now has an owner)**

| id | Correction | Owner row | What the row must now do |
| --- | --- | --- | --- |
| G1 | **E4 link-only card has no builder (the critical hole).** | NEW Row 11 | Build the reader-facing card: add published `DigestViewItem.link_only` (bool, default false) + `withheld_reason` (nullable); the `ITEM_FIELDS` allow-list in `frontend/src/lib/payload/project.ts`; a card component (headline + source + "we could not verify our summary" marker, NO summary); a browser smoke. Ships INERT (field false until Row 8). Level-5 additive published contract. |
| G2 | E7 placement + DigestDay arithmetic (Row 8 named only `RunManifest`). | Row 8 | Drop/relegate a withheld item BEFORE `collapse_same_story` ([assemble.py:2038](../backend/idhazh/assemble.py)) so the next-best duplicate promotes; `DigestDay` gains a `link_only` term (`planned = published + failed + link_only`) + validator rewrite ([digest_day.py:615](../backend/idhazh/contracts/digest_day.py)) + schema/version/changelog; `RunManifest` counts it; a count-invariant test that the arithmetic closes. |
| G3 | E4 makes Row 8's gate self-contradict ("a withheld item is absent"). | Row 8 | The integration gate asserts the withheld item is PRESENT as a link-only card WITHOUT a summary, not absent; Row 8 writes `link_only=true` + `withheld_reason` using Row 11's field. |
| G4 | E5 length pre-filter + the ~11% baseline float. | Row 8 | Add a length pre-filter (never summarise a sub-200-word stub); state the ~11% steady-state link-only baseline so D8's alarm does not read 11% as an anomaly. |
| G5 | E10(a) corpus-harvest byte-identity test floats. | Row 8 | Integration test: corpus-harvest output is byte-identical gate-off vs gate-on (a link-only item is still harvested from `items/` upstream of assemble) - pins the anti-Goodhart invariant. |
| G6 | E1 all floors WATCH-only; the per-item downgrade band is empty by construction. | Rows 2, 5, 7 | Drop the per-item `downgrade` action; faithfulness's only per-item reader action is the absolute 0.50 block + the existing 0.80/0.50 display bands. Keep the `downgraded` enum value ONLY as a reserved future-promotion member said so on the field, or drop it (G12). |
| G7 | E2 seed keys on the HHEM instrument sub-identity, not `scorer_version`. | Rows 4, 5 | Row 4 folds faithfulness by the HHEM sub-identity (`hhem_rev@rev + weights_digest + window=900/150/anchored`), not the whole `scorer_version` (plan 35 changes it -> 0 of 11,140 match). Row 5 seeds from that key. |
| G8 | E3 symmetric damping floats. | Row 5 | Row 5 dec 2 + oracle: symmetric damping for every watch floor (the withhold is absolute+undamped; a watch floor is an operator signal, so asymmetric damping only ratchets the alarm down under noise). |
| G9 | Row 5 seed is a growing read + a test that walks committed data. | Row 5 | The production seed declares Guardrail #12's escape-hatch (what it reads, why a bounded input cannot answer); the seed TEST uses a bounded fixture, never the committed archive (section 13); cite the PROPERTY ("rows at the current HHEM identity"), never the rotting cardinal 8,461. |
| G10 | E6 coherence 3-model RAM is unowned; plan 36 inherits same-day/next-day. | Rows 4, 5 | Plan 36 does NOT measure the peak (that is plan 35 Row 8 + owner). Declare a hard dependency on plan 35 having resolved coherence's DAY; Rows 4/5 fold/fit coherence on whichever day plan-35 state says; coherence's action is `watch` (never gates). |
| G11 | E8 rename touch-points; E9 Row 6/10 sequencing. | Rows 6, 10 | If the `LLM-COUNCIL` rename lands, Row 6 edits only `name:`, `concurrency.group`, `_harness.py`. Row 6's leg timeout is a LABELLED estimate x generous margin and does NOT hard-block on Row 10 (E9); Row 10 measures the merged call after. E10(b): Row 6 canary asserts containment (`geval` never reaches `publish_decision`) + thinking off. |
| G12 | Row 3 dec 1 stale premise; the `downgraded` dead value. | Row 3 | Fix dec 1: under E4 a withheld item is PRESENT (link-only), not absent - the stamp stays on `EvalRow` because it records every scored item including link-only. Resolve `publish_decision`: values are `published` \| `withheld`; keep `downgraded` only if reserved for a named future promotion, else drop. |
| G13 | Row 2 omits the contract fixtures + `export.py` tuple. | Row 2 | Name `tests/fixtures/contracts/<stem>/` fixtures for both new contracts and the `CONTRACTS` tuple + import in `export.py`. |
| G14 | The design-of-record doc lags the corrections. | Row 5 commit | Widen the reconciliation: `docs/concepts/summary-quality-autotune.md` drops the faithfulness-downgrades-below-adaptive-floor language (E1), the `block p01` phrasing, and the asymmetric "damp the raise" (E3); adds the E4 link-only card to the publish-gate section. |

**Table B - PR-wave grouping (9 PRs across 4 waves; each PR independently green)**

| PR | Wave | Rows | Ships as / why grouped | Depends on |
| --- | --- | --- | --- | --- |
| fit-core | 1 | 1 | pure refactor; plan-34 tests are the oracle | 34 fit on main |
| eval-columns | 1 | 3 | expand-only EvalRow width; `merge=union` carve-out (lands on main before any writer, never branch-stacked) | 35 EvalRow on main |
| metric-fold-fit | 2 | 2, 4, 5 | all edit `ledger.py` + share the two new contracts; fold-before-fit; inert until Row 8 | fit-core, eval-columns |
| geval-leg | 2 | 6 | disjoint island (`quality/geval.py` + the council workflow) | eval-columns |
| publish-gate | 3 | 7 | backend veto chain, record-only, stamps `EvalRow` | metric-fold-fit |
| geval-measure | 3 | 10 | MEASURES -> runs alone (`measure.yml` on a clean runner) | geval-leg |
| link-only-card | 3 | 11 | reader-facing card, ships inert; the E4 surface | eval-columns |
| console-panels | 3 | 9 | frontend island on `/console/judgement/` | metric-fold-fit, publish-gate |
| apply-gate | 4 | 8 | ESCALATE, owner sign-off, first published-day change; uses Row 11's card, carries E7 contracts | publish-gate, link-only-card |

**Peak pool width 2** (Carmack): Rows 1 and 3 are TWO co-roots from t0, not one width-1 head. The serial
spine is `1 -> 2 -> 4 -> 5 -> 7 -> 8` (6 deep); the width-1 point is the TAIL (Row 8), by owner mandate.
Provision 2 workers; `Parallel N = 4` never binds.

**Table C - optimistic-dispatch rule (the CI-idle fix)**

| Edge class | Dispatch base | Why |
| --- | --- | --- |
| Disjoint (1 vs 3; 4 vs 6; 5 vs 10; 11 vs 8-frontend) | `origin/main`, at once | no shared file |
| Shared-file, shape settled + mechanical (1->2 once `ClampOutcome`/`FitEnd` settle; 4->5 once the `ledger.py` helper settles) | predecessor's BRANCH tip, pre-merge | shape cannot move; pool never idles on CI |
| New persisted contract (2->4/5/7) | wait on `main` | the contract shape is exactly what review moves; fold/fit WRITE it |
| Measuring (6->10) | wait on `main` | Row 10 must call the merged `geval.py`; runs alone anyway |
| ESCALATE / Level-5 (7->8) | wait on `main` + owner sign-off | first change to a published day; lands alone |
| EvalRow width vs the external plan-35 widening | HARD wait on `main` (never optimistic) | `state/scores` is `merge=union`; two open widenings stack silently. After any EvalRow merge, census committed shards for a stacked header. |

## Section 1 - Status Reckoner

The round-2 review regroups the eleven rows into **9 PRs across 4 waves** (section 0d Table B). A row's
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
| 11 | Link-only card surface (E4), ships inert | 3 | W3 / link-only-card | PENDING | - | - | - |
| 9 | Console: the quality bands on `/console/judgement/` | 5, 7 | W3 / console-panels | PENDING | - | - | - |
| 8 | Flip the flag: assemble acts on the stamp (link-only, E7) | 7, 11 | W4 / apply-gate (alone) | PENDING (ESCALATE) | - | - | - |

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
  | 3 | `MetricAction` is `block | downgrade | watch`; the knob's default is `block` for faithfulness, `watch` for the rest (D2) | Andre, Editor |
  | 4 | The band carries two floors - a block floor and a watch floor - not one line (D3) | Andre |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | One shared distribution file for all four metrics | Couples their cadence; a single archive-on-input-change would reset all four when one scorer moves | - | Fowler |
  | 2 | A `scored-pairs`-style per-item tree | Per-item scores already persist in `EvalRow`; a second copy is a second answer | - | Fowler |

### Row #3 - `EvalRow`: the three new columns

- **Scope:** add `geval` (fluency 0-1, nullable), `publish_decision` (`published`|`downgraded`|`withheld`,
  default `published`), `withheld_reason` (a `MetricId`-or-`unsupported_number` enum, nullable) to the
  committed eval ledger. Expand only; nothing writes the decision yet.
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
  committed HHEM readings once.
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
  from log-probs under the grammar).
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
  absolute block floor stamps `withheld`; below the watch floor stamps `downgraded`; a low coverage
  stamps nothing under the default `watch`; the bite - flip coverage's action to `block` and the same
  item stamps `withheld`.
- **Oracle:** the veto chain stamps the most severe action any metric earned and names the metric that
  earned it; it changes no published day (record-only).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Veto chain, not a composite; the reason names the metric (D4) | Andre, Fowler |
  | 2 | Record-only first; a person reads the counterfactual withheld/downgraded list once as go/no-go before Row 8 (D7) | Fowler, Editor |
  | 3 | A displayed "overall", if built, is labelled a display aggregate that feeds no action | Andre |

### Row #8 - flip the flag - ESCALATE

- **Scope:** assemble reads the `EvalRow` stamp and acts. A `withheld` (below-absolute-floor)
  faithfulness item does NOT vanish - it degrades to Row 11's link-only card (headline + source +
  "we could not verify our summary" marker, no summary), so the loss is visible and recoverable, not
  invisible (E4). The drop/relegate happens BEFORE `collapse_same_story`
  ([assemble.py:2038](../backend/idhazh/assemble.py)) so the next-best duplicate promotes (E7). A length
  pre-filter never summarises a sub-200-word stub (E5). Behind `publish_gate.enabled`, ships off; the
  first row that changes a published day.
- **Files touched:** `backend/idhazh/stages/assemble.py` (write `link_only`+`withheld_reason`, relegate
  before the fold, recompute run/vertical/desk counts), `backend/idhazh/contracts/digest_day.py`
  (`planned = published + failed + link_only`, validator rewrite + schema/version/changelog, E7),
  `RunManifest` (the link-only count + schema stamp), `config/idhazh.json` (`publish_gate.enabled` +
  the stub-length floor, removal condition on the declaring line).
- **Acceptance gates:** integration over the canary day, built once gate-off and once gate-on, asserting
  a withheld item is PRESENT as a link-only card WITHOUT a summary (not absent, E4/G3), a count-invariant
  test that `planned = published + failed + link_only` closes (E7), and that corpus-harvest output is
  byte-identical gate-off vs gate-on (a link-only item is still harvested upstream of assemble, E10a);
  browser smoke that the day renders with an item link-only and when the band tree is absent.
- **Oracle:** with the flag off, every published day is byte-identical to today; with it on, a
  below-absolute-floor item is a link-only card the manifest counts, the story's next-best duplicate is
  promoted, and the counts close; it cannot settle the editorial cost of a thin day (D8 - the link-only
  rate is watched on the console at the stated ~11% baseline, E5).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Lands alone, after a corpus turn of record-only review; owner sign-off (Level 5) | owner, Fowler |
  | 2 | Only faithfulness withholds by default; coverage/coherence downgrade only if the owner promotes them; the owner sets the floor and permits withholding (reader-safety boundary) | Editor, owner |

### Row #9 - console: the quality bands

- **Scope:** add panels to `/console/judgement/` drawing each metric's distribution, its fitted floors
  over time, the withhold-and-downgrade rate, and the record-only counterfactual list a person reviews
  before Row 8.
- **Files touched:** `frontend/src/routes/console/judgement/*.svelte`, a console reader under
  `frontend/src/lib/console/`, the affected browser specs.
- **Acceptance gates:** frontend `test:changed`; browser smoke per section 12, including the data-absent
  arm (rebuild with an empty band tree, confirm the panel draws its axis and its empty-state copy).
- **Oracle:** the browser oracle re-derives each drawn floor from the committed band shard; it cannot
  settle whether the panel reads well (Susan's sufficiency check).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The withhold rate is a first-class panel with its own alarm (D8) | Editor |
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

### Row #11 - the link-only card surface (E4), ships inert

- **Scope:** build the reader-facing surface a withheld item degrades to, so "withhold" is a visible,
  recoverable loss and never an invisible deletion (E4). Add published `DigestViewItem.link_only`
  (bool, default false) + `withheld_reason` (nullable) fields and the card that renders when `link_only`
  is true: headline + source + a strong "we could not verify our summary" marker, carrying NO summary
  text. Ships INERT - the field is always false until Row 8 flips the gate, so this row changes no
  published day.
- **Files touched:** `backend/idhazh/contracts/digest_view.py` (the two additive fields + schema +
  version + changelog), `frontend/src/lib/payload/project.ts` (the `ITEM_FIELDS` allow-list),
  `frontend/src/lib/payload/types.ts` (generated), a link-only card component under `frontend/src/lib/`,
  the affected browser specs.
- **Acceptance gates:** contract drift gate (the field regenerates byte-identical); frontend
  `test:changed`; browser smoke - a fixture item with `link_only=true` renders the card WITHOUT a
  summary and with the marker, a normal item is unchanged, and the day renders when the field is absent
  from an older payload (defaults false).
- **Oracle:** a built `DigestViewItem` with `link_only=true` renders the marker and no summary, and with
  the field defaulted the page is byte-identical to today; it cannot settle whether the card reads with
  the right tone (Susan's sufficiency check; Editor owns the copy).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The card is a published-payload field, not an `EvalRow` read: the site reads only committed output, so the withhold reason must reach the browser as published data | Fowler |
  | 2 | Ships inert (field default false) so the reader-facing surface lands and is smoke-tested BEFORE the ESCALATE flag flip that uses it (Row 8) | Fowler, owner |
  | 3 | The marker copy is Editor's; the card omits the summary entirely, so there is no false claim to make | Editor |

## Section 3 - the loop, and where it is documented

The design of record, with the mermaid and the formulas, is
[`docs/concepts/summary-quality-autotune.md`](../docs/concepts/summary-quality-autotune.md). That page
carries the four metrics, how each is measured, the fold-fit loop, and the publish gate; this plan
sizes the rows that build it. When Row 8 lands, the page's "target design (in flight)" framing is
removed in the same commit.

## See also

- [`20260917-34-similarity-autotune-plan.md`](20260917-34-similarity-autotune-plan.md) - the loop this
  plan mirrors, and the fit core Row 1 extracts.
- [`20260918-35-search-eval-key-points-plan.md`](20260918-35-search-eval-key-points-plan.md) - the
  cleanup and the recorded-only scorers this plan consumes.
- [`docs/concepts/summary-quality-autotune.md`](../docs/concepts/summary-quality-autotune.md) - the
  metrics, the formulas, and the loop diagram.
