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
| [20260823-known-defects-plan.md](20260823-known-defects-plan.md) | 7 | 3 | 4 | 4 |
| [20260827-summarizer-fine-tuning-plan.md](20260827-summarizer-fine-tuning-plan.md) | 10 | 4 | 6 | 1 |
| [20260905-11-two-call-planner-plan.md](20260905-11-two-call-planner-plan.md) | 13 | 10 | 3 | 1 |
| [20260905-12-readable-visuals-plan.md](20260905-12-readable-visuals-plan.md) | 6 | 0 | 6 | 1 |
| [20260905-13-switch-on-deletion-plan.md](20260905-13-switch-on-deletion-plan.md) | 3 | 1 | 2 | 0 |
| [20260905-14-sufficiency-bar-plan.md](20260905-14-sufficiency-bar-plan.md) | 4 | 0 | 4 | 2 |
| [20260905-15-chart-vocabulary-plan.md](20260905-15-chart-vocabulary-plan.md) | 6 | 0 | 6 | 1 |
| [20260905-16-composition-vocabulary-plan.md](20260905-16-composition-vocabulary-plan.md) | 6 | 0 | 6 | 1 |
| [20260905-17-infographic-vocabulary-plan.md](20260905-17-infographic-vocabulary-plan.md) | 4 | 0 | 4 | 1 |
| [20260905-18-diagram-vocabulary-plan.md](20260905-18-diagram-vocabulary-plan.md) | 6 | 0 | 6 | 1 |
| [20260905-19-visual-telemetry-plan.md](20260905-19-visual-telemetry-plan.md) | 4 | 0 | 4 | 1 |
| [20260905-20-visual-console-plan.md](20260905-20-visual-console-plan.md) | 4 | 0 | 4 | 1 |
| [20260905-21-human-judgement-plan.md](20260905-21-human-judgement-plan.md) | 6 | 0 | 6 | 1 |
| [20260905-22-distil-and-close-plan.md](20260905-22-distil-and-close-plan.md) | 3 | 0 | 3 | 1 |
| [20260910-23-article-classification-plan.md](20260910-23-article-classification-plan.md) | 28 | 7 | 21 | 6 |
| [20260910-24-day-sharded-ledgers-plan.md](20260910-24-day-sharded-ledgers-plan.md) | 8 | 3 | 5 | 0 |
| [20260910-25-placement-plan.md](20260910-25-placement-plan.md) | 15 | 2 | 12 | 1 |
| [20260911-26-retire-prerender-plan.md](20260911-26-retire-prerender-plan.md) | 4 | 3 | 1 | 0 |

## In flight - 6

| Row | Plan | Group | Title | Worktree |
| --- | --- | --- | --- | --- |
| #3g | 11 | C7 | Call 1's reply does not fit its own budget | p11-3g |
| #2 | 13 | B | The window takes a value, and nothing is deleted yet | p13-2 |
| #1a | 23 | C | The fingerprint stops gating and stops being read | p23-1a |
| #3 | 24 | B | The migration utility, and it refuses to write a tree it cannot read back | p24-3 |
| #1 | 25 | A | Two docstrings defend a requirement the page retired | p25-1 |
| #4 | 26 | B | The ruling, written where the next person arrives | p26-4 |

## Ready now - 24

Nothing these depend on is outstanding. It says nothing about which two can run
together - that is a question about files, and `20260911-execution-order.md`
section 3 is where it is answered.

| Row | Plan | Group | Title | Depends on |
| --- | --- | --- | --- | --- |
| #2 | 20260823-known-defects-plan | - | The faithfulness thresholds have no labelled error rate | - |
| #18 | 20260823-known-defects-plan | - | The truncation flag still cannot fire, now for a different reason | - |
| #19 | 20260823-known-defects-plan | - | A summarize call that failed on its reply reports no cost at all | - |
| #20 | 20260823-known-defects-plan | - | The `publishing` group dirties a file the build fingerprint hashes, so it can never certify its own build | - |
| #5 | 20260827-summarizer-fine-tuning-plan | A | Reference set | 3 |
| #6 | 11 | F | The small model, its job and its cache go | 5b |
| #1 | 12 | A | A new engine behind the same seam | - |
| #1 | 14 | A | A drawing that costs too much is not drawn | - |
| #2 | 14 | A | Every fact is reachable without a mouse | - |
| #1 | 15 | A | The whole vocabulary is declarable, and an unbuilt type steps down | - |
| #1 | 16 | A | How often does an article actually state a whole | - |
| #1 | 17 | A | A real sentence made to fit, without anyone re-writing it | - |
| #1 | 18 | A | The words that mean "then", and the words that mean "against" | - |
| #1 | 19 | A | The fold key, decided before anything writes a row | - |
| #1 | 20 | A | The two funnels | - |
| #1 | 21 | A | A place to look at a visual, that never ships with the site | - |
| #1 | 22 | A | What is durable, and where it already lives | - |
| #20 | 23 | A | The order of the day, written down | - |
| #P2 | 23 | B | The reference dataset, built so a number cannot flatter us | - |
| #P5 | 23 | C | Which distribution the runtime reports at a masked token | - |
| #4 | 23 | F | An event gets a lifecycle | 3 |
| #13 | 23 | F | The encoder alarm | 3 |
| #21 | 23 | L | The unpublished pool is scored with the bonus and without it | plan 24 row #1 |
| #13 | 25 | I | `Voices` - who supplied the day, and what it is worth | 11 |

## Waiting on another row - 73

| Row | Plan | Group | Title | Waiting on |
| --- | --- | --- | --- | --- |
| #6 | 20260827-summarizer-fine-tuning-plan | B | Train the adapter, merge, quantise | 5 is PENDING |
| #7 | 20260827-summarizer-fine-tuning-plan | B | Publish the weights | 6 is PENDING |
| #8 | 20260827-summarizer-fine-tuning-plan | C | Judge and decide | 7 is PENDING |
| #9 | 20260827-summarizer-fine-tuning-plan | B+C | Distil into the student | 8 is PENDING |
| #10 | 20260827-summarizer-fine-tuning-plan | C | Adopt, or do not | 8 (and 9 for the student) is PENDING |
| #3f | 11 | C6 | The window is sized for two calls | plan 23 row #1a is IN-FLIGHT |
| #2 | 12 | B | The drawing takes the width it is given | 1 is PENDING |
| #3 | 12 | B | Numbers a reader can say out loud | 1 is PENDING |
| #4 | 12 | C | The smallest label a person can read, and enough marks to be worth the space | 2 is PENDING; 3 is PENDING |
| #5 | 12 | D | A caption, and one mark that lands first | 4 is PENDING |
| #6 | 12 | E | A whole day, again | 5 is PENDING |
| #3 | 13 | C | The fuse comes out, and one run is watched | 2 is IN-FLIGHT |
| #3 | 14 | B | The browser draws exactly what the build drew | 1 is PENDING; 2 is PENDING |
| #4 | 14 | C | Motion that can be turned off, and that ends | 3 is PENDING |
| #2 | 15 | B | Position and length: bar, dot, slope | 1 is PENDING |
| #3 | 15 | C | Trend and magnitude: line, area | 2 is PENDING |
| #4 | 15 | D | Relationship: scatter | 3 is PENDING |
| #5 | 15 | E | Parts as bars: stacked_bar, with its own question | 4 is PENDING |
| #6 | 15 | F | The two the reader asked for | 5 is PENDING |
| #2 | 16 | B | The four ways code may reach a number the article did not write | 1 is PENDING |
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
| #2 | 19 | B | A stage of its own | 1 is PENDING |
| #3 | 19 | C | One row per attempt, and a reason for every refusal | 2 is PENDING |
| #4 | 19 | D | What a re-render needs, and where a rejected plan lives | 3 is PENDING |
| #2 | 20 | B | Why it was refused, and what happened when it stepped down | 1 is PENDING |
| #3 | 20 | C | The rules for reading any of it | 2 is PENDING |
| #4 | 20 | D | How each feature gets retired without a fresh argument | 3 is PENDING |
| #2 | 21 | B | A machine verdict and a human one, never in the same column | 1 is PENDING |
| #3 | 21 | C | Two ways to ask, and the question locked before the verdict | 2 is PENDING |
| #4 | 21 | D | Weights that cannot quietly get worse | 3 is PENDING |
| #5 | 21 | E | Did the reader actually understand it faster | 4 is PENDING |
| #6 | 21 | F | How this loop knows when it is done | 5 is PENDING |
| #2 | 22 | B | The numbers, taken again on the tree that shipped | 1 is PENDING |
| #3 | 22 | C | The two documents go, and nothing links to a ghost | 2 is PENDING |
| #P3 | 23 | D | A person labels the dev split and the test split | P2 is PENDING |
| #7b | 23 | H | The two calls become a DAG, and every label rides in the first | plan 11 row 6 is PENDING |
| #8 | 23 | I | Call 1 labels: desk, lenses, article kind | 7b is PENDING |
| #14 | 23 | J | The classification ledger, and the day file the console reads | 8 is PENDING |
| #12 | 23 | J | The quote: seven conditions, three checks, ten codes | 7b is PENDING; 8 is PENDING |
| #9 | 23 | K | Confidence is a masked probability over the label's whole span | 8 is PENDING; 14 is PENDING; P5 is PENDING |
| #15 | 23 | K | The console tab, at `/console/judgement/` | 14 is PENDING; plan 25 row #12 is PENDING |
| #10 | 23 | L | Five stances, each with its own decline, behind a gate written in code | 8 is PENDING; 14 is PENDING |
| #11 | 23 | M | Sentiment about one named subject | 8 is PENDING; 14 is PENDING; P3 is PENDING |
| #18 | 23 | M | The closing measurement: is a read desk better than a declared one | P3 is PENDING; 14 is PENDING |
| #16 | 23 | N | A vertical is proposed into a channel and promoted by a person | 14 is PENDING; 8 is PENDING |
| #19 | 23 | N | The keyword lenses retire, or they do not | 14 is PENDING; 13 is PENDING; 8 is PENDING |
| #17 | 23 | O | The lens weight learns every run, and a run never writes `config/` | 14 is PENDING; 21 is PENDING; 20 is PENDING |
| #1b | 23 | P | The fingerprint field is dropped from the contracts | 1a is IN-FLIGHT |
| #5 | 24 | C | `state/item-health/` files by day | 3 is IN-FLIGHT |
| #6 | 24 | D | `state/feed-health/` files by day | 3 is IN-FLIGHT |
| #7 | 24 | E | `state/seen/` files by day | 3 is IN-FLIGHT |
| #8 | 24 | F | `state/scores/` and `state/score-index/` file by day | 3 is IN-FLIGHT |
| #2 | 25 | B | One order over the whole day, inside a frame a person set | 1 is IN-FLIGHT |
| #3 | 25 | C | `rank_score` orders the stream, and its terms are the editor's | 2 is PENDING |
| #6 | 25 | C | The topic pills order by what is running | 2 is PENDING |
| #4 | 25 | D | Carriage becomes a tie-break | 3 is PENDING |
| #7 | 25 | D | A desk floor and a desk ceiling | 2 is PENDING |
| #8 | 25 | E | A story cross-files to a second desk | 7 is PENDING |
| #9a | 25 | E | The placement terms on the counterfactual ledger plan 23 creates | 3 is PENDING; plan 23 row #21 is PENDING |
| #10 | 25 | F | The `assemble` consolidation | 2 is PENDING; 7 is PENDING; 8 is PENDING |
| #14 | 25 | G | A target distribution, and the day's distance from it | 7 is PENDING |
| #12 | 25 | H | `Judgement` - what the model made of each article | plan 23 row #14 is PENDING |

## Finished - 14 plans with no live row

20260815-digest-pipeline-plan.md, 20260905-01-visible-chart-plan.md, 20260905-02-retire-the-route-name-plan.md, 20260905-03-console-backfill-plan.md, 20260905-04-site-cap-defence-plan.md, 20260905-05-span-tree-plan.md, 20260905-06-fewer-better-articles-plan.md, 20260905-07-better-summaries-plan.md, 20260905-08-element-table-plan.md, 20260905-09-pin-the-runtime-plan.md, 20260905-10-visual-plan-contract-plan.md, 20260906-constant-cost-reads-plan.md, 20260907-growing-reads-window-plan.md, 20260912-27-adaptive-guardrails-plan.md

## See also

- [20260911-handover.md](20260911-handover.md) - what to do first, with no
  context.
- [20260911-execution-order.md](20260911-execution-order.md) - which rows
  collide, and why.
