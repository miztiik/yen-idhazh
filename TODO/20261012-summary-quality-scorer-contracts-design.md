# The summary-quality judge as a pipeline of replaceable scorers: intent and contracts

**Last Updated**: 2026-10-12

**Author**: Fowler (architecture), 2026-10-12, plan 65 Q68. **Status**: design for the owner's review before plan 65.2; nothing here is ruled. It changes no ruling, and Section 9 asks for the three it needs. "Estimate" marks an estimate.
**Ids**: Q61, QQ28, P15, X8.4 cite plan 65 (`TODO/20261011-65-summary-fidelity-judge-plan.md`), as "plan 65 B2" where a row here could be meant; "research Q5" cites `TODO/20261012-unsupervised-summary-improvement-research-record.md`. Code paths are repository paths.

## Answer first

- **One protocol.** A scorer answers one question - does this text support this claim? - through `ClaimChecker.check(premise, claims)`, for a GGUF model behind llama.cpp and an in-process encoder alike. What it scores is a task in config, never a code path per model.
- **One file per scorer**, bound to a slot (primary, held-out, key-fact listing, key-fact coverage, every-summary). Its derived instrument id rides on every row; only a metric's own instrument restarts it (Q61).
- **Candidates, not training.** A newer model scores the incumbent's units every night and takes the slot by itself when it beats it on planted faults with known answers, inside guards, with an off switch. The same records test a candidate summarizer; whether code may switch the summarizer is the owner's (Table T).
- **Cells.** A cell learns its model from the judge's cell plan, asked at planning; it replaces X8.4, which cannot run a candidate beside its incumbent.

## 1. Intent

- A model is a part, not a code path: one protocol, one config file; a new kind of model is one adapter (Config-driven and evolvable).
- Newer models replace older ones without training, by beating the incumbent on the same sample (Unsupervised improvement; plan 65 E3 pending).
- Every automatic move is bounded, recorded whether applied or not, and stoppable by a switch with no default (Unsupervised improvement).
- A scorer counts only while tonight's planted faults and controls pass; its identity rides on every reading, so a swap restarts only the metrics that read it, and other changes are named on rows (Metrics, not messages; QQ22, Q61).
- Sample size follows a precision target and measured accuracy; scorers run in the council, from families other than the summarizer's; the work step does no extra work (Sample, never check everything).
- Cost per unit is measured nightly; budgets and widths are config; the every-summary score, the one cost that grows with volume, can change model through the sample (Built for tomorrow).
- Length is recorded, never a band, target or guard (Quality over brevity; Q62).

## 2. The judge as a pipeline

"Persisted": a committed record a later run reads. "Scratch": a council artifact crossing the jobs of one run.

Table A - the stages

| # | Stage | Takes -> gives | Runs in | Boundary | Swappable |
| --- | --- | --- | --- | --- | --- |
| A1 | Score every summary | summary, text seen, full text -> eval-row score | digest work step (HHEM today, `evals/hhem.py`) | persisted | the scorer, qualified in A6, never in the work step |
| A2 | Draw the sample | scored summaries, precision target, measured accuracy -> kept entries with draw facts (Table K) | digest assemble job (X1.3) | persisted where open decision A puts it | the sample design |
| A3 | Prepare units | kept entries, sentence rule, planted-fault library -> each cell's units: real, planted, control | council prepare | scratch selection file | rule and library, versioned |
| A4 | List key facts | kept text -> one list per article, shared by every arm | cell serving the lister | persisted in the kept entry (X2.4) | the lister (open decision B) |
| A5 | Write candidate summaries | kept articles, a candidate change -> summaries by the production path | cell serving the candidate | persisted in the kept entry | the candidate |
| A6 | Score | the cell's units -> one reading per unit per instrument | council cells, one runtime each | in memory at the call; scratch per cell; filed at settle (Table L) | every scorer |
| A7 | Check the scorers | readings of known answers and real units -> health; whether readings count | settle | persisted (Table M) | guards are config |
| A8 | Decide | health or pair rows over a window -> decisions, slot assignment | settle | persisted (Table O) | guard settings |
| A9 | Aggregate | counted readings, draw facts, health -> additive counts | drift judge's settle | in memory | - |
| A10 | Publish metrics | counts -> the record other judges read (Table P) | drift judge's settle, ledger door | persisted, numbers only | - |

A job boundary is always a file, never a call. The digest touches only A1 and A2, which exist today. Shards run side by side, so what A4 and A5 write tonight is scored the next night.

## 3. The scorer as a replaceable stage

### 3.1 One protocol; the unit is a declared task

Five models are in view: Granite Guardian 3.3 8B and Gemma 4 E4B (GGUF); HHEM, MiniCheck-Flan-T5-L, FactCG-DeBERTa-L (encoders). Four tasks ask one question - does this premise support this claim? - of different texts, so one protocol serves them (Table J). Listing key facts writes text, so it has a second, smaller protocol.

Table B - the tasks

| # | Task | Premise; claims | Unit | Slot |
| --- | --- | --- | --- | --- |
| B1 | sentence_against_source | text the summarizer saw; each summary sentence | sentence | sentence_support, sentence_support_held_out |
| B2 | summary_against_source | text seen, then full text; the summary | summary | summary_support (every summary) |
| B3 | key_fact_against_summary | the summary; each listed key fact | key fact | key_fact_coverage (completeness) |
| B4 | sentence_against_key_facts | the key-fact list; each summary sentence | sentence | key_fact_coverage (conciseness) |
| B5 | list_key_facts | text seen; writes a list (GGUF only) | article | key_fact_listing |

B3 and B4 sell an option: completeness needs a generating model only to list facts, and coverage can be any claim checker, the cheap encoder included. Whether that is good enough is the model-quality advisor's to measure.

### 3.2 The declaration

A scorer is one config file (Table H), bound to a slot by name (Table I) in the hosting judge's file or, for summary_support, `config/idhazh.json`; no reader lists a folder (Guardrail #12). It is P38's scorer in config, kept by Q61: `HHEM_MODEL` and `HHEM_REVISION` leave `hhem.py`, `chunk_words` and `chunk_overlap_words` become HHEM's window, and today's `Scorer.score` becomes HHEM's adapter, with `score_over_chunks` and `dual_score` behind `check`.

### 3.3 Instrument identity

Table C - what the instrument id covers

| # | Part | In or out, and why |
| --- | --- | --- |
| C1 | Weight bytes as verified: the GGUF sha256; each encoder file's sha256 and a digest of the loaded tensors (`weights_digest`, hhem.py) | in: a silent weight change moves every reading |
| C2 | Runtime: the llama.cpp build (`config/llama-cpp-pin.json`); an encoder's installed transformers, torch and tokenizers | in: the runtime computes the reading (Y2.7) |
| C3 | The call: rendered prompt and grammar digests, decoding, thinking off, the model file's server block | in: each can move an answer |
| C4 | The reading: answer mapping, label threshold, premise window | in |
| C5 | The unit: task and sentence-rule version | in: a new rule changes every sentence (Y2.8) |
| C6 | Status, slot, standing, budgets, shards, cache rule, byte count, timeout | out: cost or use, never a reading; a stamp that moves too often never builds a series (qualification.md) |
| C7 | Derivation | sha256 of a canonical JSON of C1 to C5, after load and verification, never typed; the health row spells it |
| C8 | To confirm | C2 makes a llama.cpp bump restart every GGUF scorer's metrics, not the encoders'; this reads Q61's "a metric's own scorer", and the owner may narrow it |

### 3.4 How a cell learns its model

Table D - from X8.4 to a cell plan

| # | Step | What |
| --- | --- | --- |
| D1 | Today | A cell is "tenant, date, shard, shards and runs_model" (`llm-council.yml`); true serves the summarizer. One server and the shard's Python take 14.31 GiB of 16; "a second server on one runner does not fit at all" (`contracts/knobs/council.py`) |
| D2 | X8.4 | `served_model` per judge and a `checker` slot: one model per judge, so no GGUF candidate beside its incumbent (Table S) |
| D3 | Replace | The tenant answers its cell plan, an optional module-level verb asked at planning as `refuse_a_night_this_tenant_cannot_finish` is ("not an eighth member of the protocol", `council/registry.py`): entries (serves, runs), `shard_count` their number, following the effective slot assignment |
| D4 | Matrix | The cell gains `serves`, a `config/models` stem or empty; `council_matrix.py` already asks the tenants, and the council reads no scorer (plan 65 C9 holds) |
| D5 | Cell | model-server runs only for a non-empty `serves`: fetch, verify sha256, serve. Only the summarizer slot's file is cached: X8.6's reason (4.94 plus 5.68 GB passes the 10 GB cache) as a rule |
| D6 | Unit | `run_shard` fails if the server reports another model id than its entry's; a tenant with no plan keeps today's rule, so the content-similarity judge is unchanged |
| D7 | ModelsConfig | No checker slot; the entry is renamed `summarizer` to `model`, the old key refused by name (as `summarize` was): a file describes weights, a binding names the role |

## 4. Moving to newer models without retraining

### 4.1 Status and standing

Table E - two words, two questions

| # | Word | Meaning; moved by |
| --- | --- | --- |
| E1 | Status: active, paused, retired | runs anywhere or not, as for judges; a person, in its file |
| E2 | Standing: incumbent | fills the slot; read while healthy; a decision |
| E3 | Standing: candidate | scores the same units; read only by its health and the comparison; added by a person |
| E4 | Standing: fallback | a displaced incumbent kept running for `fallback_nights`; a decision |
| E5 | Standing: retired | not run in the slot; back only as a new committed candidate |
| E6 | Effective standing | declared standing moved by the newest applied decision (X5.6); code never writes config |

### 4.2 Qualifying a scorer candidate

This keeps `docs/concepts/qualification.md`'s pattern where it fits - frozen paired inputs, a margin because better is not enough, every candidate recorded, the production score never selecting - and moves one clause with the North Star: the rule now applies a switch, inside guards.

The exam never reads a scorer (X3.1's rule). Planted faults are summary sentences with a number, name or date swapped for one the article lacks, negated, or taken from another article: unsupported by construction. Controls are the article's own sentences, verbatim or meaning-preserving edits: supported by construction. An inverted answer mapping fails night one. Kinds and sizes are the model-quality advisor's.

Table F - promotion guards, all required

| # | Guard | Passes when |
| --- | --- | --- |
| F1 | Same units | both scored the same faults, controls and real units every night |
| F2 | Evidence | `min_nights`, `min_planted_per_kind`, `min_controls` |
| F3 | Better on known answers | informedness (catch rate plus control pass rate, minus one: research Q2's J) beats the incumbent's by `informedness_margin`; paired counts, one-sided at `alpha`, up to `looks` looks with a stricter early line |
| F4 | No blind spot | every fault kind caught at least `catch_floor` |
| F5 | False alarms | control flag rate at most the incumbent's plus `control_margin` |
| F6 | Agreement | agreement beyond chance with the held-out incumbent on real units at most `agreement_margin` below the incumbent's; never a selector, as errors correlate (research Q5(d)) |
| F7 | Calibration | mean squared gap to known answers at most the incumbent's plus `calibration_margin` |
| F8 | Cost | seconds per unit times planned units fit `minutes_per_night` |
| F9 | Family | not the summarizer's in a faithfulness slot; named on every row (QQ22) |
| F10 | Held-out stays held out | never a scorer that has filled sentence_support |
| F11 | Healthy | its readings counted every night of the window |
| F12 | Tenure | the incumbent has held `min_tenure_nights` |

Proposed process defaults: `min_nights` 14, `looks` 5, `min_tenure_nights` 28, `fallback_nights` 14, `max_candidates_per_slot` 2 (research Q7), `max_candidate_nights` 56. Margins and floors are the model-quality advisor's.

### 4.3 Promotion, off switch, switch and series boundary

- **First seating (Q66).** Granite and the encoder start as candidates for an empty sentence_support; the better on F3 takes it, the other takes the held-out slot, each only past F4, F5 and F11. An empty slot publishes null with a reason.
- **Look.** Every `look_every_nights` the host's settle files a decision per candidate - continue, promote or reject - with every guard's numbers; with `auto_promote_scorers` (no default, like QQ28's) false, none applies.
- **Switch.** An applied promote names `effective_from` and moves the assignment; the old incumbent becomes fallback. The row is the recorded switch.
- **Series.** The instrument id changes, so only that slot's metrics restart (Q61). The gate's guard (QQ12) reads only counted nights since `effective_from`, so the gate is record-only until its window refills.
- **Fall back.** If the new incumbent's health fails inside `fallback_nights`, the fallback takes the slot back; afterwards it retires.
- **summary_support is record-only.** Its score feeds the published band, cut at 0.80 and 0.50 on today's scorer's scale (`knobs/evaluation.py`), and plan 65 B2 keeps published surfaces still; a person moves pointer and cuts together.

### 4.4 The same pattern for a candidate summarizer (the test bench, research Stage 1)

Table G - one pattern, two slots

| # | Step | Scorer slot | Summarizer slot |
| --- | --- | --- | --- |
| G1 | Enters | a committed scorer file and candidate line | a committed change to the incumbent - model, prompt, decoding or input budget, never an output cap - so an incumbent change moves both arms and a test survives churn (a change about every 9 days, research Q1) |
| G2 | Same sample | tonight's units | kept articles: the published summary against one a council cell writes through the production path ("the gate has to call what the digest calls", qualification.md) |
| G3 | Decides | known answers (Table F) | the sentence_support incumbent's unsupported share, paired by article, up to `looks` looks |
| G4 | Guards | Table F | no worse on held-out share, completeness, copying, unsupported numbers, hedges both ways, every-summary score, failures; no source harmed; scorers healthy; seconds per summary sized for 10,000 a day; a clean A/A test (the incumbent as its own candidate); the gain holds on fresh articles; a family unlike the scorers' |
| G5 | Records; applied; after | Tables M, O; `auto_promote_scorers`; new instrument id, fallback scorer | Tables N, O; Table T; new identity named on rows (series per QQ1), old configuration a candidate arm for `fallback_nights` |

Research Q2 (estimate): a 3-point fall in the unsupported share needs about 1,700 pairs at Granite's news accuracy and 1,200 at FactCG's (17 and 12 nights at 100 a night), so F3 seats the better scorer first.

## 5. Contracts

Deleted against current rows: X9.29's copy of the main score, X8.4's checker slot, settings on result rows (Q61) and a separate switch record.

Table H - contract: scorer declaration

| # | Field | Meaning |
| --- | --- | --- |
| H1 | Kind; version; writer; readers | `ScorerDeclaration` (`contracts/knobs/scorer.py`); config, `config/scorers/<scorer_id>.json`, unstamped (CLAUDE.md section 11), unknown keys refused by name; a person writes it; the host judge, the work step and the measurement read it |
| H2 | scorer_id; lifecycle_status | the file stem; Table E |
| H3 | runtime: llama_server or in_process; loader: sequence_classification, seq2seq_label_tokens, hhem_remote_code | closed sets in code: a new model of a known kind is config only |
| H4 | task | Table B |
| H5 | model_file (GGUF) | a `config/models` stem: pins and server flags |
| H6 | weights (encoder): repo, 40-character revision, files with sha256, trust_remote_code | true refused unless every code file is hashed |
| H7 | family | declared for encoders, the model file's `arch` for GGUF (F9) |
| H8 | prompt_template (GGUF) | a file under `backend/idhazh/prompts/`; premise and claims in untrusted blocks, the ask after (Guardrail #11) |
| H9 | answer (GGUF): forced prefix, words, meanings | renders the grammar (Granite's yes means unsupported, X7.2); no prose path |
| H10 | decoding (GGUF): temperature, first-token alternatives | thinking on refused (QQ25) |
| H11 | supported_output (encoder) | the label index or token meaning supported |
| H12 | premise_window: words and overlap, or whole | max over windows; a premise too long is skipped with a reason |
| H13 | label_threshold | under it a claim reads unsupported |

Table I - contract: slot binding and cell plan

| # | Field | Meaning |
| --- | --- | --- |
| I1 | Kind; version; writer; readers | `SlotBinding`: config in the host judge's file (summary_support: `config/idhazh.json`), refused by name, written by a person. `CellPlanEntry`: in memory, beside `JudgeDeclaration` (`contracts/knobs/council.py`), carried in the matrix JSON; read by `council_matrix.py`, model-server and `run_shard` |
| I2 | slots: name -> incumbent, candidates, minutes_per_night, shards_per_scorer | names: summary_support, sentence_support, sentence_support_held_out, key_fact_listing, key_fact_coverage, summarizer |
| I3 | auto_promote_scorers | the off switch; no default |
| I4 | every setting Section 4 names | each with a declared range (Guardrail #6) |
| I5 | Refusals at load | an unknown or retired scorer; two standings in one slot; a task the slot rejects; F9, F10; a GGUF scorer no cell can serve; automatic promotion of summary_support |
| I6 | CellPlanEntry: serves, runs | a `config/models` stem or empty; the scorer or candidate it runs |

Table J - contract: scoring protocols

| # | Field | Meaning |
| --- | --- | --- |
| J1 | Kind; version; writer; readers | `ClaimChecker` and `FactLister`, `typing.Protocol` in `backend/idhazh/scorers/` (new); never persisted, and a test holds each adapter to them; called by the host judge and the digest, never by the council |
| J2 | instrument | id, spelled form and parts (Table C); raises before load, like `weights_digest` |
| J3 | check(premise, claims, *, deadline) | one premise, many claims: the server pays the article's prefill once (prompt cache, `llm/server.py`); an encoder batches |
| J4 | ClaimReading | supported_probability, label (or None), parsed, best_window, seconds; a reply outside the grammar is recorded, never read as prose (`similarity/judge.py`) |
| J5 | list_facts(source, *, deadline) | a grammar-held list, or None; untrusted data |

Table K - contract: sample draw record

| # | Field | Meaning |
| --- | --- | --- |
| K1 | Kind; version; writer; readers | `SampleDraw`: fields of each kept entry (X9's, wherever open decision A puts it), numbers copied onto every verdict to outlive the text; section 11; the digest's keep stage writes; A3, A9 and the bench read |
| K2 | date, run_id, url_key, item_id, source_id, feed_id, model_id, summarizer_identity | which summary, run and series |
| K3 | kept_because: sampled, checked_for_gate, withheld | only sampled entries enter a rate |
| K4 | stratum, population, drawn, inclusion_probability | per run and stratum (source today); rates weight by its inverse |
| K5 | draw_rank | the blind digest of date and url_key (X1.3); scoring in its order makes a budget cut a random subsample |
| K6 | design: selector version, target margin, expected rate, informedness used and its source, n computed and kept | Q61's precision target: $n_0 = z^2 q(1-q)/(EJ)^2$, then the finite-population correction (research Q6), clamped |

Table L - contract: scorer verdict

| # | Field | Meaning |
| --- | --- | --- |
| L1 | Kind; version; writer; readers | `ScorerVerdict`, a door row per instrument per unit, in grounding-verdicts (sentences) and key-fact-scores (key facts), names ruled in QQ16 and QQ11; section 11; the host's settle files it under the council's writer identity (the judge-ledger rule, `ledger-registry.md`); A7 to A9, the gate's guard and the console read it |
| L2 | run_id, date, judge_id, work_part_index | council run, judged date, cell |
| L3 | url_key, source_id, feed_id, model_id, arm, test_id | the summary, its series, its bench arm |
| L4 | unit_kind (real, planted, control), fault_kind, truth, unit_index, variant | truth by construction, null for real units |
| L5 | scorer_id, instrument_id, slot, standing | the instrument that night |
| L6 | supported_probability, label, parsed, best_window, seconds; skipped (budget, premise_too_long) | the reading, or why there is none |
| L7 | kept_because, inclusion_probability, draw_rank | from Table K |
| L8 | Key | run_id, date, url_key, arm, test_id, instrument_id, unit_kind, unit_index, variant; no text, so it may be published (X7.10) |

Table M - contract: scorer health

| # | Field | Meaning |
| --- | --- | --- |
| M1 | Kind; version; writer; readers | `ScorerHealth`, a door row per instrument per night, proposed ledger scorer-health; section 11; the host's settle writes; A2, A8, A9, the gate's guard and the console read |
| M2 | run_id, date, scorer_id, instrument_id, instrument (spelled), slot, standing, planted_library_version | who took which exam |
| M3 | caught_by_kind: fault_kind, planted, caught | catch rate per kind |
| M4 | controls, controls_flagged | false alarms |
| M5 | squared_error_sum, units_with_truth, calibration bins | calibration |
| M6 | per other instrument: both supported, both unsupported, each alone unsupported | agreement beyond chance, computed on read |
| M7 | units_scored, units_skipped, model_seconds, unit_seconds_max, load_seconds | cost |
| M8 | verdicts_count, failed_guards | readings feed metrics only while F4, F5 and F11 hold over `health_window_nights` (QQ22) |
| M9 | Key | run_id, date, instrument_id; every count additive, never a stored rate |

Table N - contract: paired summary scores

| # | Field | Meaning |
| --- | --- | --- |
| N1 | Kind; version; writer; readers | `PairedSummaryScore`, a door row per arm per article per test, proposed ledger paired-summary-scores; section 11; the host's settle writes; A8 and the console read |
| N2 | run_id, date, test_id, url_key, arm, arm_identity, changed_inputs | the pair, and the change: one input or a named bundle (the summarizer how-to, section 1.2) |
| N3 | primary and held_out: instrument_id, sentences, unsupported, probability_sum | the metric and its guard |
| N4 | coverage: instrument ids, key_facts, covered | against the one shared list |
| N5 | extractiveness, verbatim_run, unsupported_numbers, hedges dropped and added, summary_support score | guards, by the eval row's own code |
| N6 | summary_words, summary_sentences, article_words, generation_seconds, failure_code | lengths recorded only (Q62); article_words at most a continuous covariate |
| N7 | Key | run_id, date, test_id, url_key, arm |

Table O - contract: slot decisions and assignment

| # | Field | Meaning |
| --- | --- | --- |
| O1 | Kind; version; writer; readers | `SlotDecision`, a door row per slot, candidate and look (proposed slot-decisions); `SlotAssignment`, one flat JSON file with an entry per slot, the current reading (proposed slot-assignments, outside the door); section 11; only the host's settle writes; prepare, the cell plan, the work step and the draw read the assignment, the summarizer only under T1 |
| O2 | run_id, date, judge_id, slot, test_id, look | which test and look |
| O3 | incumbent, candidate: id and instrument_id, or arm_identity | what was compared |
| O4 | comparisons: name, kind, estimate, bound, units, passed | every guard of Table F or G; names a closed set |
| O5 | decision (continue, promote, reject, fall_back, retire), applied, held_by, effective_from | no settings copied (Q61): the envelope's commit names the config |
| O6 | Assignment entry: incumbent, instrument_id, standings, since, decided_by | a fixed-size read (Guardrail #12), rebuilt nightly from the last file and applied decisions, so a dead settle is repaired |
| O7 | Key (decisions) | run_id, date, slot, test_id, look |

Table P - contract: the metrics record other judges read

| # | Field | Meaning |
| --- | --- | --- |
| P1 | Kind; version; writer; readers | row #41's record extended as Q61 asks, in summary-failures-by-source (QQ32): a door row per date, source, feed, series, metric and instrument; section 11; the drift judge's settle writes a date once its verdicts exist (no settle order assumed); the feed-quality, feed-reliability and content-similarity judges, the drift judge and the console read it |
| P2 | run_id, date, source_id, feed_id, model_id | whose summaries |
| P3 | metric | sentence_unsupported, sentence_unsupported_held_out, key_fact_covered, sentence_carries_key_fact, summary_under_gate_line, unsupported_numbers, extraction_flagged, withheld_by_gate: only metrics with a reader (Q61) |
| P4 | instrument_id, or metrics_version for code counts | the metric's own scorer |
| P5 | units, flagged, weighted_units, weighted_flagged, summaries | additive; a night holds few sampled summaries per source, so readers pool nights |
| P6 | catch_rate, catch_units, control_pass_rate, control_units | to correct: $\hat p = (q - (1 - Sp))/(Se + Sp - 1)$, with its wide interval (research Q2) |
| P7 | verdicts_counted, recorded_changes, points_docked | false leaves flagged null (fail closed); changes named (Q61); row #41's count kept |
| P8 | Key | run_id, date, source_id, feed_id, model_id, metric, instrument_id |

**Every new ledger owes** `ledger-registry.md`'s list: family, `LedgerName`, `LEDGER_NAMES`, `_JUDGE_DOOR_SHAPES` (loaded on first use: the council's import closure does not grow), `REGISTRY` and a live-retention compaction. The flat assignment file joins the named JSON ledgers outside the door and asks `accepts_new_rows`.

## 6. Runtimes

Table Q - runtimes

| # | Runtime | Models; how a cell gets one; how a call runs | Measure first |
| --- | --- | --- | --- |
| Q1 | llama_server | Granite, the lister (open decision B), candidate summarizers. model-server fetches the `serves` file, checks sha256 and serves it on the pinned build; `server.py` renders with the model's own turn markers, article first, prompt cache on, a grammar-held answer and first-token probabilities (`grammar_completion_payload`) | fetch seconds for 4.94 GB uncached; server and process peak memory against 16 GB; seconds per claim, article cached and not |
| Q2 | in_process | HHEM; the encoder (Table U). Loaded once per cell or work shard, on CPU, from the pinned revision, hashes checked; no server | fetch and load seconds; peak memory; seconds per window-claim pair at 4 threads |
| Q3 | The measurement | one dispatch per scorer file on committed `corpus/` pairs (row #40's, generalized); numbers only; the runtime advisor reads it | it sets slot budgets and widths |

At 10,000 summaries a day the sampled stages stay flat (research Q6: 370 of 10,000 give plus or minus 3 points on a 10 percent rate). Only A1 grows, to about 6.3 hours a day (estimate); a cheaper every-summary scorer can qualify on the sample.

## 7. What changes in plan 65

Table R - rows for 65.2

| # | Row | Change | What | Level |
| --- | --- | --- | --- | --- |
| R1 | #29 | changed | sample size from a precision target and measured accuracy (Q61); Table K's fields; storage stays open decision A | 5 |
| R2 | #30, #31 | changed | completeness as two slots, listing (open decision B) and coverage (any checker); per-unit rows in key-fact-scores; planted omissions become the coverage exam | 5 |
| R3 | #35 | changed | hosts sentence_support and its held-out slot with Granite, the encoder (Q66) and candidates; Tables L, M, O; QQ16's 40 minutes stays Granite's budget | 5 |
| R4 | #36 | replaced | by Table Q's measurement; work-step sentence cost is moot after Q61 | 3 |
| R5 | #37 | changed | only what Q61 kept: the every-summary scorer named by a scorer file (chunk settings move in) and one appended, derived eval-row stamp, faithfulness_instrument; the column stays hhem | 5 |
| R6 | #38 | changed | the drift judge's faithfulness members read Table P on the sentence_support instrument | 3 |
| R7 | #39, #23 | changed | the gate's independent check reads the sentence_support incumbent since `effective_from`, counted nights only; the line waits for open decision C | 5 |
| R8 | #40, X8.4, X8.6 | changed, replaced | Granite stays pinned; the encoder gets a scorer file; X8.4 becomes the cell plan, X8.6 the cache rule | 5 |
| R9 | #41 | changed | becomes Table P | 5 |
| R10 | #8 | changed | the library also builds scorer exams | 3 |
| R11 | new | added | tidy first: ModelsConfig's entry renamed `model` (D7); `ClaimChecker` with HHEM's adapter behind today's call sites, same scores; then scorer files and encoder adapters | 3 |
| R12 | new | added | the cell plan, `serves`, the model-server input | 3 |
| R13 | new | added | scorer-health, slot-decisions, slot-assignments, `auto_promote_scorers` | 5 |
| R14 | new | added | the bench: A5 cells, paired-summary-scores, decisions; a summarizer switch waits for Table T | 5 |

**Sequence.** Structural first: R11 (Rename with the old key refused by name; Extract Interface, Branch by Abstraction, Move Field for the chunk settings); then R12; R3 with R13 for the first seating; R9, R6, R7; R2; R14. More than three structural commits make this Level 4, so this table is the breakdown (CLAUDE.md section 6). Tests: a contract fixture per row contract; unit tests that each part of C1 to C5 moves the id and C6 does not; recorded completions and readings, no mocks (Guardrail #7).

## 8. Rejected alternatives

Table S - rejected, with the cost of taking each

| # | Alternative | Why not; cost to take it |
| --- | --- | --- |
| S1 | One council judge per model | the code path per model the owner wants gone; a package, family and registration per model; no shared night |
| S2 | X8.4 as proposed | one model per judge, a role inside a weights file; GGUF candidates on other nights, so nothing is paired |
| S3 | Scorer classes named in config by import path | config would choose the code that runs, not three reviewed loaders |
| S4 | Train or calibrate a scorer | Q67; a calibrator needs labels this project lacks |
| S5 | A nightly anchor panel (research Q5(d)) | expects an exact repeat (plan 65 C10) on a fixed set the 31-day window deletes (plan 65 D3, B10); the derived id already catches a changed instrument; taking it reverses B10 |
| S6 | Agreement as the selector | errors correlate, so it rewards the incumbent's blind spots |
| S7 | One weighted health score | research Q3: constraints, not a sum; a gain would hide a loss |
| S8 | Exams from sentences a scorer judged supported | the incumbent writes its own exam and wins on controls |
| S9 | Thresholds recalibrated nightly | a new instrument nightly; no series holds |
| S10 | Rates only in Table P | few summaries per source per night; readers could neither pool nor correct |

## 9. Open decisions for the owner

**Situation.** Plan 65 names the scorer in config (P38, kept by Q61), approves two second models on a sample (Q66) and trains nothing (Q67; plan 65 E3 pending). This design promotes council-only slots by itself, inside guards. Open decisions A, B and C stand; rows A2, A4 and R7 here show where this design touches them.

**Problem.** Plan 65 B2 says a model entry never moves by itself (P15), and the summarizer how-to keeps adoption a person's; Q66 approved one encoder without choosing which; two judges (QQ11, QQ16) would share one pipeline.

**Impact.** Without the first ruling a person still moves the summarizer, a regular human step (plan 65 A7); without the second the held-out slot has no model; without the third the design works, with two prepares, two cell plans and two writers. The tables are independent.

Table T - may code switch the summarizer?

| # | Option | Benefit | Cost | Gives up |
| --- | --- | --- | --- | --- |
| T1 | **Recommended**. Automatic among committed, pinned candidates: an applied decision moves the summarizer in slot-assignments, which the digest reads; switch `auto_promote_summarizer`, no default | the North Star and Q67 with no person; each candidate is still a reviewed diff (Guardrail #11) | lifts plan 65 B2's model-entry clause for this path; the digest reads a council record to pick its model (Level 5); config alone no longer says what runs | the person's adoption step |
| T2 | Record-only; a person moves `models_file` | no ruling changes | a regular human step | unsupervised model moves |
| T3 | The save job commits the pointer | config stays the whole truth | automation writes config, against X5.6 (first ruled in QQ27) | config written only by people |

Table U - which encoder?

| # | Option | Benefit | Cost | Gives up |
| --- | --- | --- | --- | --- |
| U1 | **Recommended**. Both as candidates for the first window; the one that seats stays | 70.1 against 69.9 on CNN (research Q5(a)) is inside noise; the candidate path runs on day one | one more cell for about 14 to 28 nights (estimate) | a choice today |
| U2 | FactCG-DeBERTa-L now | half the size (0.4B) | its authors prefer per-dataset thresholds, so the exam sets it anyway | a measured choice |
| U3 | MiniCheck-Flan-T5-L now | ahead on XSum (74.3 against 73.9) | twice the size, about twice the seconds (estimate) | a measured choice |

Table V - one judge for the sampled pipeline?

| # | Option | Benefit | Cost | Gives up |
| --- | --- | --- | --- | --- |
| V1 | **Recommended**. One judge hosts every sampled slot and the bench (proposed name summary-source-judge: it judges summaries against their source); the ruled ledger names stay | one prepare, sentence rule, cell plan and record set: "the judge itself as a pipeline" | reverses the split of QQ11 C1 and QQ16 C1, in plan text only | pausing grounding and completeness apart |
| V2 | Two judges; shared ledgers in one family both write | no ruling changes | two prepares that must segment alike | one pipeline in one place |
| V3 | Two judges with their own copies | self-contained families | six ledgers for three records | one record per question |

**Recommendation.** T1: the owner's stated intent, bounded by the held-out judge, the A/A test, the fresh-article check and the off switch, once plan 65 E3 is confirmed. U1: the published gap is inside noise, and measuring it costs one cell a night for a few weeks. V1: one pipeline belongs in one judge, and before any row starts a merge costs only plan text.
