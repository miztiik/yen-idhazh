# What the renormalised margin rule changes, 2026-09-21

**Last Updated**: 2026-09-21
Living, one question one answer. The readings below were taken on one day and
the date is in the title; a re-run of this measurement REPLACES this page and
moves **Last Updated**, and git history holds what it said.

**At the window the judge asked for until today, the new rule can say nothing at
all.** The three tokens that came back were `NO`, `No` and ` NO`. Two of those
are the same verdict spelled twice and the third is not a legal opening, so one
verdict took every unit of legal mass and there was no second verdict to
subtract. The old rule answered 0.9997 by subtracting NO from itself. **So the
wider window is a requirement of the new rule and not an improvement on it** -
the two land together or the column empties.

**At the wider window the same reply reads 0.99994 against the old rule's
0.99970**, a difference of 0.00024 - about two hundredths of one percent on a
reply this model was certain about. That number says nothing about a reply the
model was torn about, which is the case the column exists for, and this page
cannot say what the difference is there.

**These weights split UNCLEAR across two tokens.** The vocabulary spells it
`UNC` + `LEAR`, and ` UNCLEAR` as ` UNC` + `LEAR`. A rule bucketing a window
against the three whole words would score UNCLEAR at zero on every reply these
weights ever write, and report a two-way gap as though three answers had been
weighed.

## Conditions

| | |
| --- | --- |
| Instrument, live arm | `idhazh.llm.server.grammar_completion_payload` off the committed entry, posted to a server started by `idhazh.llm.server.server_argv` - the judge's own body, not a body written for this page |
| Instrument, census arm | Every committed row read back through `StorySimilarityPair.from_csv_row` |
| Weights | `Qwen3.5-9B-Q4_K_M.gguf`, sha256 `03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8` - the file `models.summarizer` declares |
| Build | `b10444-5f754ea0e`, read off `/props` on the running process |
| Prompt | The judge's own system turn and the first two items of `tests/fixtures/contracts/digest-day`, rendered through the entry's turn markers |
| Grammar | `root ::= " "? ("YES" \| "NO" \| "UNCLEAR")`, unchanged by this work - its digest is still `c1d1b9dc`, which is what every committed row and the record itself carry |
| Sampler | `temperature` 0.0, `top_p` 1.0, `seed` 0 - the judging knob's temperature, as a shard sends it |
| Machine | 12th Gen Intel Core i7-1265U, 10 cores and 12 threads, 31.8 GiB. **Not the production runner** - what a token window contains is a property of the weights and the build rather than of the host, so a developer box answers this and could not answer a throughput one (Guardrail #2) |
| Date | 2026-09-21. Weights loaded in 15.2 s |
| Spread | Zero on the live arm. Three runs at each width returned identical logprobs to sixteen significant figures, which is what temperature 0.0 and a fixed seed should give. The census arm is a count of a fixed file, so it has no spread to report |

## The window, at both widths

One reply, asked twice. The content was `NO` both times.

| Width asked | Returned | Tokens that name one verdict | Dropped as naming none | Not a legal opening | Old reading | New reading |
| --- | --- | --- | --- | --- | --- | --- |
| 3 | 3 | `NO`, ` NO` - both NO | none | `No` | 0.99970 | **empty** |
| 25 | 25 | `NO`, ` NO`, `N` - NO; `YES` - YES; `UN`, `UNC` - UNCLEAR | the bare empty token, at rank 4 | 18 of 25 | 0.99970 | 0.99994 |

**The old reading does not move with the width**, because the two likeliest
tokens are `NO` and `No` at both. That is the measurement behind the claim that
widening the window alone buys nothing: the bucketing is what makes a wider
window mean something, and the width is what gives the bucketing a second
verdict to find.

**The token that names no verdict is really there.** It came back with an empty
spelling at rank 4 of 25 - higher than `YES`. A rule that credited it to all
three verdicts would have added the same mass three times. The margin over the
recorded window and the margin over that window with it removed are the same
value, which is the assertion the test makes rather than a number it quotes.

## What the column said before today

Every committed row, read on 2026-09-21 before the rule changed. 82 rows across
two day files, and all 82 carry a margin.

| Rows | Lowest | Quarter | Middle | Three-quarter | Highest | Mean | Spread |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 82 | 0.1082 | 0.6190 | 0.9001 | 0.9703 | 0.9943 | 0.7714 | 0.2715 |

Forty-one of the eighty-two sit above 0.90 and none below 0.10. Read against the
live arm, **a large part of that spread is an artefact rather than a finding**:
the old rule subtracted a verdict's second spelling from its first whenever the
vocabulary offered one, and on the reply measured here it did exactly that.

## What this cannot settle

**How far the two readings differ across the 82 rows.** The committed rows carry
`first_token_probabilities` empty - the column was added on 2026-09-21 and the
judge that fills it landed after those rows were judged - so there is no window
on those rows to re-read, and one reply is not a distribution. **The instrument
that could answer it is a re-judge of the same 82 pairs, priced at 82 x 94.53 s
= 2.15 h on the judging runner.** Nothing on this page should be read as a claim
about the population.

**Whether a reasoned verdict is a better verdict.** Not measured, and not
estimated either. The plumbing for a reasoning span in front of the answer ships
here behind a config entry that no committed file declares, and it stays shut
until a replay says otherwise. **That replay is priced rather than guessed**:
82 pairs at the measured 94.53 s a pair is 2.15 h for the cold arm, and the
thinking arm at the measured 11.18 tokens a second is about 5.4 h at an
estimated 800 reasoning tokens a call and about 8.3 h at 1,500 - past the 6 h
job ceiling on one job, so it runs as a matrix on the council's own workflow.
The 800 and the 1,500 are estimates and the measurement that would replace them
is the run itself.

**What a margin THRESHOLD should be.** That is a reading over a judge's own
replies under the new rule, and no such population exists yet.

## See also

- [`which-probabilities-the-server-returns.md`](which-probabilities-the-server-returns.md) - whether the numbers are the model's own or the grammar's, which is what makes renormalising real work.
- [`../../architecture/publishing/autotune-content-similarity.md`](../../architecture/publishing/autotune-content-similarity.md) - the judge this column belongs to, and what the reset costs.
- [`../../architecture/summarize/model-boundary.md`](../../architecture/summarize/model-boundary.md) - why the layer hands back the raw window and computes no margin.
