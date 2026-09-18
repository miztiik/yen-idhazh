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
| [20260823-known-defects-plan.md](20260823-known-defects-plan.md) | 9 | 7 | 2 | 2 |
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
| [20260914-27-pipeline-observability-plan.md](20260914-27-pipeline-observability-plan.md) | 11 | 0 | 11 | 11 |
| [20260917-33-collision-free-telemetry-plan.md](20260917-33-collision-free-telemetry-plan.md) | 29 | 6 | 22 | 0 |
| [20260917-34-similarity-autotune-plan.md](20260917-34-similarity-autotune-plan.md) | 4 | 0 | 4 | 0 |

## In flight - 6

| Row | Plan | Group | Title | Worktree |
| --- | --- | --- | --- | --- |
| #6 | 33 | A | The validation ledger leaves the root of `state/` | p33a6 |
| #3 | 33 | B | `item-health`, `scores`, `score-index` write segments | p33b3 |
| #4 | 33 | B | `span-rollup` writes segments | p33b4 |
| #17 | 33 | B | `runtime-counters` writes segments | p33b17 |
| #10 | 33 | C | `model_load_ms` and `job_seconds` join `host-fingerprint` | p33c10 |
| #29 | 33 | J | `prune.yml` wakes outside the digest window | p33j29 |

## Ready now - 31

Nothing these depend on is outstanding. It says nothing about which two can run
together - that is a question about files, and `20260911-execution-order.md`
section 3 is where it is answered.

| Row | Plan | Group | Title | Depends on |
| --- | --- | --- | --- | --- |
| #2 | 20260823-known-defects-plan | - | The faithfulness thresholds have no labelled error rate | - |
| #18 | 20260823-known-defects-plan | - | The truncation flag still cannot fire, now for a different reason | - |
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
| #2 | 27 | B | `state/item-health/` becomes the per-item spine | 1 |
| #3 | 27 | B | The selection score carries its own terms | - |
| #4 | 27 | B | Logging is a set of flags, not a level | - |
| #5 | 27 | C | `work.py` says what it is doing, per item and per stage | 2, 3, 4 |
| #6 | 27 | C | Every item records the machine that ran it | 2, 4 |
| #7 | 27 | C | The summary and the picture are timed apart | 2 |
| #8 | 27 | C | What the model saw, kept for 90 days | 4 |
| #9 | 27 | D | A cut reply keeps its summary | 1 |
| #10 | 27 | D | A killed shard keeps the work it finished | - |
| #11 | 27 | E | Two articles, three arms, one runner | 4 |

## Waiting on another row - 68

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
| #12 | 33 | D | Delete the merge machinery | 3 is IN-FLIGHT; 4 is IN-FLIGHT; 6 is IN-FLIGHT; 17 is IN-FLIGHT |
| #13 | 33 | D | Compaction lag and free swap on the console band | 12 is PENDING |
| #11 | 33 | E | Delete `runtime-counters` and everything that reads it | 10 is IN-FLIGHT; 17 is IN-FLIGHT |
| #15 | 33 | F | Generated TypeScript contracts replace the hand-written ones | 10 is IN-FLIGHT; 11 is PENDING |
| #16 | 33 | G | Docs, and the orphan sweep | all names no row |
| #19 | 33 | I | The shard board | 11 is PENDING |
| #21 | 33 | I | Memory and load, three grains - ABSORBS Row #14 | 15 is PENDING; 19 is PENDING |
| #23 | 33 | I | What a run reads against what it writes, in tokens and in seconds | 21 is PENDING |
| #25 | 33 | I | Outside the model call, as range marks | 23 is PENDING |
| #22 | 33 | I | Platform mix as grouped bars | 25 is PENDING |
| #24 | 33 | I | Counterfactual cost gets a shape | 22 is PENDING |
| #20 | 33 | I | Timing panels merge and move to Pipeline | 24 is PENDING |
| #26 | 33 | I | Machine cards: L3 and bandwidth as bars - AMENDS Row #5 | 11 is PENDING |
| #27 | 33 | K | Route grouping and panel order | 20 is PENDING; 26 is PENDING |
| #14 | 33 | - | The per-item machine load panel | - |
| #8 | 33 | - | Memory split by prefill and decode | - |
| #11 | 34 | - | The sample sheet utility | 7 names no row; 8 names no row; 10 names no row |
| #12 | 34 | - | Console: the holdout panel. **The merge count landed in #874; this is the other half** | 2 names no row; 8 names no row |
| #15 | 34 | - | Console: the confusion matrix | 7 names no row; 8 names no row; 12 is PENDING |
| #16 | 34 | - | The design document. **Mostly overtaken - see below** | 9 names no row |

## Finished - 19 plans with no live row

20260815-digest-pipeline-plan.md, 20260905-01-visible-chart-plan.md, 20260905-02-retire-the-route-name-plan.md, 20260905-03-console-backfill-plan.md, 20260905-04-site-cap-defence-plan.md, 20260905-05-span-tree-plan.md, 20260905-06-fewer-better-articles-plan.md, 20260905-07-better-summaries-plan.md, 20260905-08-element-table-plan.md, 20260905-09-pin-the-runtime-plan.md, 20260905-10-visual-plan-contract-plan.md, 20260905-11-two-call-planner-plan.md, 20260906-constant-cost-reads-plan.md, 20260907-growing-reads-window-plan.md, 20260910-24-day-sharded-ledgers-plan.md, 20260911-26-retire-prerender-plan.md, 20260912-27-adaptive-guardrails-plan.md, 20260913-reference-dataset-2-plan.md, 20260914-29-found-once-plan.md

## See also

- [20260911-handover.md](20260911-handover.md) - what to do first, with no
  context.
- [20260911-execution-order.md](20260911-execution-order.md) - which rows
  collide, and why.
