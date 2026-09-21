# The plan queue

**Generated, and written by one job after a merge lands on `main`. Do not
hand-edit, and do not regenerate it on a branch - a pull request that carries
this file is refused.** The Status Reckoner in each plan-doc is the source;
this page is the single place to read all of them at once. To see what it
would say about the tree in front of you:

```
python backend/utilities/plan_status.py
```

That prints the same answer and writes nothing. Nothing here comes from the
network, a clock or a worktree, so the same tree always gives the same bytes.
For what is on this box right now, and for drift against merged pull requests,
run `--in-flight` instead; neither belongs in a committed file.

## Where each plan stands

| Plan | Rows | Landed | Live | Ready |
| --- | --- | --- | --- | --- |
| [20260823-known-defects-plan.md](20260823-known-defects-plan.md) | 18 | 7 | 11 | 11 |
| [20260827-summarizer-fine-tuning-plan.md](20260827-summarizer-fine-tuning-plan.md) | 10 | 4 | 6 | 1 |
| [20260905-12-readable-visuals-plan.md](20260905-12-readable-visuals-plan.md) | 7 | 3 | 4 | 1 |
| [20260905-13-switch-on-deletion-plan.md](20260905-13-switch-on-deletion-plan.md) | 3 | 2 | 1 | 1 |
| [20260905-14-sufficiency-bar-plan.md](20260905-14-sufficiency-bar-plan.md) | 4 | 1 | 3 | 1 |
| [20260905-15-chart-vocabulary-plan.md](20260905-15-chart-vocabulary-plan.md) | 6 | 0 | 6 | 1 |
| [20260905-16-composition-vocabulary-plan.md](20260905-16-composition-vocabulary-plan.md) | 6 | 1 | 5 | 1 |
| [20260905-17-infographic-vocabulary-plan.md](20260905-17-infographic-vocabulary-plan.md) | 4 | 0 | 4 | 1 |
| [20260905-18-diagram-vocabulary-plan.md](20260905-18-diagram-vocabulary-plan.md) | 6 | 0 | 6 | 1 |
| [20260905-19-visual-telemetry-plan.md](20260905-19-visual-telemetry-plan.md) | 4 | 2 | 2 | 1 |
| [20260905-20-visual-console-plan.md](20260905-20-visual-console-plan.md) | 4 | 0 | 4 | 1 |
| [20260905-21-human-judgement-plan.md](20260905-21-human-judgement-plan.md) | 6 | 1 | 5 | 1 |
| [20260905-22-distil-and-close-plan.md](20260905-22-distil-and-close-plan.md) | 3 | 0 | 3 | 1 |
| [20260910-23-article-classification-plan.md](20260910-23-article-classification-plan.md) | 28 | 16 | 12 | 2 |
| [20260910-25-placement-plan.md](20260910-25-placement-plan.md) | 16 | 10 | 5 | 4 |
| [20260914-27-pipeline-observability-plan.md](20260914-27-pipeline-observability-plan.md) | 11 | 0 | 11 | 4 |
| [20260918-35-search-eval-key-points-plan.md](20260918-35-search-eval-key-points-plan.md) | 8 | 0 | 8 | 4 |
| [20260918-36-summary-quality-autotune-plan.md](20260918-36-summary-quality-autotune-plan.md) | 13 | 0 | 13 | 0 |
| [20260921-39-delete-the-scaffolding-plan.md](20260921-39-delete-the-scaffolding-plan.md) | 21 | 0 | 1 | 0 |
| [20260921-40-bonsai-probe-plan.md](20260921-40-bonsai-probe-plan.md) | 7 | 0 | 7 | 4 |
| [20260921-41-lane-a-model-file-plan.md](20260921-41-lane-a-model-file-plan.md) | 7 | 0 | 7 | 0 |
| [20260921-42-lane-b-workflows-plan.md](20260921-42-lane-b-workflows-plan.md) | 11 | 4 | 7 | 1 |
| [20260921-43-the-ledgers-and-the-generated-layer-plan.md](20260921-43-the-ledgers-and-the-generated-layer-plan.md) | 7 | 0 | 7 | 2 |

## In flight - 5

| Row | Plan | Group | Title | Worktree |
| --- | --- | --- | --- | --- |
| #1 | 41 | A | The server-log reader goes | `p41c` -> `p41a` |
| #2 | 41 | A | The decode stamp and the dead fingerprint go | `p41a` |
| #4 | 41 | A | Both decode caps go | `p41c` |
| #6 | 41 | A | The engineering contract catches up | `p41a` |
| #7 | 41 | B | The markers are derived at server start | `p41b` |

## Ready now - 44

Nothing these depend on is outstanding. It says nothing about which two can run
together - that is a question about files, and `20260911-execution-order.md`
section 3 is where it is answered.

| Row | Plan | Group | Title | Depends on |
| --- | --- | --- | --- | --- |
| #2 | 20260823-known-defects-plan | - | The faithfulness thresholds have no labelled error rate | - |
| #18 | 20260823-known-defects-plan | - | The truncation flag still cannot fire, now for a different reason | - |
| #23 | 20260823-known-defects-plan | - | The canary day records no settings, so nothing renders the rules that say a setting moved | - |
| #24 | 20260823-known-defects-plan | - | `failed_field` costs a cell on every row and answers nobody | - |
| #25 | 20260823-known-defects-plan | - | `host_model` is a column nothing fills, and two rulings disagree about whether it should | - |
| #26 | 20260823-known-defects-plan | - | The settlement-key check reads one constant twice, so it cannot see a key lose a cell | - |
| #27 | 20260823-known-defects-plan | - | The decode stamp excludes the grammar but not the schema | - |
| #28 | 20260823-known-defects-plan | - | The one-at-a-time guard tells the operator the wrong verb | - |
| #29 | 20260823-known-defects-plan | - | A shard is called a `unit` in the council's workflow and its tests | - |
| #30 | 20260823-known-defects-plan | - | A third spelling of the vector norm lives in the canary builder | - |
| #31 | 20260823-known-defects-plan | - | The council's selection artifact is named for one date and carries several | - |
| #5 | 20260827-summarizer-fine-tuning-plan | A | Reference set | 3 |
| #3 | 12 | C | Numbers a reader can say out loud | 1b |
| #3 | 13 | C | The fuse comes out, and one run is watched | 2, plan 12 row #1b |
| #1 | 14 | A | A drawing that costs too much is not drawn | - |
| #1 | 15 | A | The whole vocabulary is declarable, and an unbuilt type steps down | - |
| #2 | 16 | B | The four ways code may reach a number the article did not write | 1 |
| #1 | 17 | A | A real sentence made to fit, without anyone re-writing it | - |
| #1 | 18 | A | The words that mean "then", and the words that mean "against" | - |
| #3 | 19 | C | One row per attempt, and a reason for every refusal | 2 |
| #1 | 20 | A | The two funnels | - |
| #2 | 21 | B | A machine verdict and a human one, never in the same column | 1 |
| #1 | 22 | A | What is durable, and where it already lives | - |
| #P5 | 23 | C | Which distribution the runtime reports at a masked token | - |
| #8 | 23 | I | Call 1 labels: desk, lenses, article kind | 7b, 2 |
| #8a | 25 | J | The second desk reaches the reader | 8 |
| #9a | 25 | E | The placement terms on the counterfactual ledger plan 23 creates | 3, plan 23 row #21 |
| #10 | 25 | F | The `assemble` consolidation | 2, 5, 7, 8 |
| #14 | 25 | G | A target distribution, and the day's distance from it | 7 |
| #1 | 27 | A | The two calls get names that say what they do | - |
| #3 | 27 | B | The selection score carries its own terms | - |
| #4 | 27 | B | Logging is a set of flags, not a level | - |
| #10 | 27 | D | A killed shard keeps the work it finished | - |
| #1 | 35 | A / cap | Raise `truncation_cap_tokens` to 30000, pin to `n_ctx` (+ fingerprint move, C5) | - |
| #5 | 35 | A / search | Live-day search - instant + semantic (+ frontend `key_points` owner, C2) | - |
| #7 | 35 | A / eval-core | Remove `lead_coverage` (+ day-metrics bucket + qualification, C4) | - |
| #8 | 35 | A / eval-core | Add coherence + coverage scorers (recorded-only) | - |
| #1 | 40 | A | The model entry, and whether it fits | - |
| #2 | 40 | A | The test workflow takes named addresses | - |
| #5 | 40 | A | The eight telemetry steps move across | - |
| #6 | 40 | A | A trial state root, and what the run keeps | - |
| #5 | 42 | B | Five checks move into the thing they check | 2, 4 |
| #1 | 43 | - | The replay count leaves the dispatch surface | - |
| #4 | 43 | - | Nine console specs visit every route the site serves | - |

## Waiting on another row - 89

| Row | Plan | Group | Title | Waiting on |
| --- | --- | --- | --- | --- |
| #6 | 20260827-summarizer-fine-tuning-plan | B | Train the adapter, merge, quantise | 5 is PENDING |
| #7 | 20260827-summarizer-fine-tuning-plan | B | Publish the weights | 6 is PENDING |
| #8 | 20260827-summarizer-fine-tuning-plan | C | Judge and decide | 7 is PENDING |
| #9 | 20260827-summarizer-fine-tuning-plan | B+C | Distil into the student | 8 is PENDING |
| #10 | 20260827-summarizer-fine-tuning-plan | C | Adopt, or do not | 8 (and 9 for the student) is PENDING |
| #4 | 12 | D | The smallest label a person can read, and enough marks to be worth the space | 3 is PENDING |
| #5 | 12 | E | A caption, and one mark that lands first | 4 is PENDING |
| #6 | 12 | F | A whole day, again | 5 is PENDING |
| #3 | 14 | B | The browser draws exactly what the build drew | 1 is PENDING |
| #4 | 14 | C | Motion that can be turned off, and that ends | 3 is PENDING |
| #2 | 15 | B | Position and length: bar, dot, slope | 1 is PENDING |
| #3 | 15 | C | Trend and magnitude: line, area | 2 is PENDING |
| #4 | 15 | D | Relationship: scatter | 3 is PENDING |
| #5 | 15 | E | Parts as bars: stacked_bar, with its own question | 4 is PENDING |
| #6 | 15 | F | The two the reader asked for | 5 is PENDING |
| #3 | 16 | C | A declared whole: pie | 2 is PENDING |
| #4 | 16 | D | Three numbers at once: bubble | 3 is PENDING |
| #5 | 16 | E | A spread of values: histogram | 4 is PENDING |
| #6 | 16 | F | The flag that settles the pie question later | 3 is PENDING; 4 is PENDING |
| #2 | 17 | B | One striking figure: callout | 1 is PENDING |
| #3 | 17 | C | Who did what: whowhat | 2 is PENDING |
| #4 | 17 | D | Three to five takeaways, and the switch that kills them | 3 is PENDING |
| #2 | 18 | B | The last two classes, and a denominator that finally names five | 1 is PENDING |
| #3 | 18 | C | Steps with arrows nobody invented: flow | 2 is PENDING |
| #4 | 18 | D | A layout that draws the same twice | 3 is PENDING |
| #5 | 18 | E | Trees, states and branches | 4 is PENDING |
| #6 | 18 | F | A whole day, once more | 5 is PENDING |
| #4 | 19 | D | What a re-render needs, and where a rejected plan lives | 3 is PENDING |
| #2 | 20 | B | Why it was refused, and what happened when it stepped down | 1 is PENDING |
| #3 | 20 | C | The rules for reading any of it | 2 is PENDING |
| #4 | 20 | D | How each feature gets retired without a fresh argument | 3 is PENDING |
| #3 | 21 | C | Two ways to ask, and the question locked before the verdict | 2 is PENDING |
| #4 | 21 | D | Weights that cannot quietly get worse | 3 is PENDING |
| #5 | 21 | E | Did the reader actually understand it faster | 4 is PENDING |
| #6 | 21 | F | How this loop knows when it is done | 5 is PENDING |
| #2 | 22 | B | The numbers, taken again on the tree that shipped | 1 is PENDING |
| #3 | 22 | C | The two documents go, and nothing links to a ghost | 2 is PENDING |
| #14 | 23 | J | The classification ledger, and the day file the console reads | 8 is PENDING |
| #12 | 23 | J | The quote: seven conditions, three checks, ten codes | 8 is PENDING |
| #9 | 23 | K | Confidence is a masked probability over the label's whole span | 8 is PENDING; 14 is PENDING; P5 is PENDING |
| #15 | 23 | K | The console tab, at `/console/judgement/` | 14 is PENDING; plan 25 row #12 is PENDING |
| #10 | 23 | L | Five stances, each with its own decline, behind a gate written in code | 8 is PENDING; 14 is PENDING |
| #11 | 23 | M | Sentiment about one named subject | 8 is PENDING; 14 is PENDING |
| #18 | 23 | M | The closing measurement: is a read desk better than a declared one | 14 is PENDING |
| #16 | 23 | N | A vertical is proposed into a channel and promoted by a person | 14 is PENDING; 8 is PENDING |
| #19 | 23 | N | The keyword lenses retire, or they do not | 14 is PENDING; 8 is PENDING |
| #17 | 23 | O | The lens weight learns every run, and a run never writes `config/` | 14 is PENDING |
| #12 | 25 | H | `Judgement` - what the model made of each article | plan 23 row #14 is PENDING |
| #2 | 27 | B | `state/item-health/` becomes the per-item spine | 1 is PENDING |
| #5 | 27 | C | `work.py` says what it is doing, per item and per stage | 2 is PENDING; 3 is PENDING; 4 is PENDING |
| #6 | 27 | C | Every item records the machine that ran it | 2 is PENDING; 4 is PENDING |
| #7 | 27 | C | The summary and the picture are timed apart | 2 is PENDING |
| #8 | 27 | C | What the model saw, kept for 90 days | 4 is PENDING |
| #9 | 27 | D | A cut reply keeps its summary | 1 is PENDING |
| #11 | 27 | E | Two articles, three arms, one runner | 4 is PENDING |
| #6 | 35 | A / eval-core | Remove `new_fact_rate` + `key_point_weight` (+#34 field, judge stages, C3) | #34 names no row |
| #2 | 35 | B / chart | Redesign + re-label the faithfulness chart; docs glyph-link | 8 is PENDING |
| #3 | 35 | B / chart | Reword recorded-only copy; relabel `compression` | 8 is PENDING |
| #4 | 35 | B / retire | Retire `key_points` completely (published + internal + corpus + `output_digest`) | 5 is PENDING; 6 is PENDING; 7 is PENDING |
| #1 | 36 | W1 / fit-core | Extract the fit core, direction-parameterised | 34-fit merged names no row |
| #3 | 36 | W1 / eval-columns | `EvalRow`: `geval`, `publish_decision`, `withheld_reason` | 35-EvalRow merged names no row |
| #2 | 36 | W2 / metric-fold-fit | The two contracts + the per-metric knob block, inert | 1 is PENDING |
| #4 | 36 | W2 / metric-fold-fit | The fold: per-metric distributions (HHEM sub-identity key, G7) | 2 is PENDING; 3 is PENDING |
| #5 | 36 | W2 / metric-fold-fit | The fit + seed faithfulness (symmetric damping, bounded fixture) | 1 is PENDING; 2 is PENDING; 4 is PENDING |
| #6 | 36 | W2 / geval-leg | G-Eval fluency judge in the council (estimate x margin timeout) | 3 is PENDING |
| #7 | 36 | W3 / publish-gate | The veto-chain publish gate, record-only | 2 is PENDING; 3 is PENDING; 5 is PENDING |
| #10 | 36 | W3 / geval-measure (alone) | Measure a real G-Eval call; replace the estimate | 6 is PENDING |
| #11 | 36 | W1 / coherence-place (alone) | Confirm coherence runs in `assemble` (MiniLM loaded there); no peak, no eviction | 35 coherence names no row |
| #9 | 36 | W3 / console-panels | Console: the quality bands + the not-published/withhold panel | 5 is PENDING; 7 is PENDING |
| #8 | 36 | W4 / apply-gate (alone) | Flip the flag: withhold = absent + item-health telemetry (E7 placement) | 7 is PENDING |
| #12 | 36 | W3 / rejects-store | The rejects store + corpus fence (`state/rejects/`, 30-day prune) | 3 is PENDING; 7 is PENDING |
| #13 | 36 | W4 / plan34-gaps | Retro: plan-34 latent gaps + the shared space-trap guard | 34 landed names no row; 6 is PENDING |
| #15 | 39 | - | The hosted span sink goes | - |
| #3 | 40 | B | One plan job, so a fan-out agrees what it is reading | 2 is PENDING |
| #4 | 40 | C | The fan-out | 3 is PENDING |
| #7 | 40 | D | One dispatch, and the readings written up | 1 is PENDING; 4 is PENDING; 5 is PENDING; 6 is PENDING |
| #3 | 41 | A | The draft head becomes a companion file | 2 is IN-FLIGHT |
| #5 | 41 | A | The model file carries llama-server's own flags | 4 is IN-FLIGHT |
| #6 | 42 | B | Fourteen assertions go, and the lists become computed | 5 is PENDING |
| #7 | 42 | C | The printer learns the whole file set, and the traversal closes | 6 is PENDING; plan 41 names no row |
| #8 | 42 | C | The workflows read the model file instead of relaying it | 7 is PENDING |
| #9 | 42 | C | The cache names the set, and the binary gets its own key | 8 is PENDING |
| #10 | 42 | D | The benchmark arms learn the server died, and the repeat count is config | 9 is PENDING |
| #11 | 42 | D | The harness keeps only what more than one module reads | 9 is PENDING |
| #2 | 43 | - | The utilities with no caller go, and the search evaluation is bounded | 1 is PENDING |
| #3 | 43 | - | The pipeline test commits what it produced | 2 is PENDING |
| #5 | 43 | - | The generated contract layer goes | 1 is PENDING; 2 is PENDING; 3 is PENDING; 4 is PENDING; plan 41 names no row; plan 42 names no row |
| #6 | 43 | - | The engineering contract and the pages catch up | 5 is PENDING; plan 41 names no row |
| #7 | 43 | - | The dependency's beneficiary line says what it buys | 5 is PENDING |

## Finished - 18 plans with no live row

20260815-digest-pipeline-plan.md, 20260905-01-visible-chart-plan.md, 20260905-02-retire-the-route-name-plan.md, 20260905-03-console-backfill-plan.md, 20260905-04-site-cap-defence-plan.md, 20260905-05-span-tree-plan.md, 20260905-06-fewer-better-articles-plan.md, 20260905-07-better-summaries-plan.md, 20260905-08-element-table-plan.md, 20260905-09-pin-the-runtime-plan.md, 20260905-10-visual-plan-contract-plan.md, 20260905-11-two-call-planner-plan.md, 20260906-constant-cost-reads-plan.md, 20260907-growing-reads-window-plan.md, 20260910-24-day-sharded-ledgers-plan.md, 20260911-26-retire-prerender-plan.md, 20260913-reference-dataset-2-plan.md, 20260914-29-found-once-plan.md

## See also

- [20260911-handover.md](20260911-handover.md) - what to do first, with no
  context.
- [20260911-execution-order.md](20260911-execution-order.md) - which rows
  collide, and why.
