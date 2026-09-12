# 09 - The runtime stops guessing which model it was tuned for

**Last Updated**: 2026-09-09
**Level**: 4 (structural: the settings block every stage inherits, and the window every later plan is sized against)

**Chain**: previous [`20260905-08-element-table-plan.md`](20260905-08-element-table-plan.md) | next [`20260905-10-visual-plan-contract-plan.md`](20260905-10-visual-plan-contract-plan.md).
**Reference**: [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - O22, O24, O38, sections 11.0, 11.2, 11.2a, 13.3, C19.

Execute per docs/how-to/execute-a-plan.md: orchestrator dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity; AUTO-merge on green gates; parallel N = 1; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | `ModelsConfig` carries two model roles and **one shared** `InferenceConfig`. Change which weights a role names and the new model silently inherits the previous one's window, cache types, batch shape and attention flags. Nothing raises. The run comes back slower, or out of memory, or with different words, and the config diff shows one repository string. Separately, the two-call design does not fit today's 8,192-token window at all - its worst case is 105 percent of it |
| Hard scope - in | Six memory numbers the job already collects and discards; ending the silent inheritance; `n_ctx` to 16,384 with flash attention on; one measured run that prices the runtime change alone |
| Hard scope - out | **Retiring the small model** - plan 11 does that, in the same commit as the flag flip, because it is what draws a chart today. Any prompt change. Any second call. Any cache-type change - `q8_0` moves the words and is a separate measurement |
| ESCALATE triggers | 1. The measured peak resident memory at 16,384 leaves less than 1.0 GiB free on the runner. **Read `MemAvailable`, not machine-minus-resident-sets** - the weights are memory-mapped and a resident-set sum counts them as committed. `MemTotal` measures 15.61 GiB, not the 14.90 GiB this trigger was first written against. 2. Flash attention does not report as active in the server's own startup line. 3. Any setting in section 11.2a is proposed without the model entry, runner and date it was derived against |
| Chosen strategy | Measure the memory first so the window raise can be judged, then close the inheritance, then raise the window, then price it. Every intermediate state ships |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 1.` |

**The distinction this plan exists to write down.** The **pipeline** is model-neutral and stays so - the weights are named in one config entry and no module, class, field, telemetry value or schema stem carries a parameter count or a vendor. The **runtime settings are not neutral**, and pretending otherwise is the hazard. Every number in section 11.2 was derived from one model's architecture on one runner. A model swap re-derives the whole block, not only the window.

---

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Six numbers the job already has and throws away | - | A | DONE #525 (three of six) | yi-h01-memory | #525 | worker |
| 2 | A model swap can no longer inherit in silence | - | A | DONE #528 | yi-h02-inherit | #528 | worker |
| 3 | The window doubles and flash attention pays for it | 1, 2 | B | DONE #547 - trigger 1 CLEARED by measurement | yi-h06-window | #547 | worker |
| 4 | One run prices the runtime and nothing else | 3 | C | DONE #552 - run `34379502244` read out; trigger 1 clears at 6.84 GiB | yi-h08-readout | #552 | orchestrator |
| 5 | The article cap doubles to 10,000 tokens | 3 | B2 | DONE #548 | yi-h07-cap | #548 | worker |

### Trigger 1 is CLEARED. The window fits, and here is the reading that settles it

**Run `2026-09-09-34323771996`** - Content refresh, scheduled, 4 shards, 601 memory
samples over the work jobs, `n_ctx` 8,192 throughout. The `/proc/meminfo` capture
landed by PR #541 is what answers it.

| Reading | Value | What it is |
| --- | --- | --- |
| `MemTotal` | **15.61 GiB** | the whole runner, constant |
| llama-server `VmHWM` | **12.68 GiB** | worst shard; ledger `peak_rss_bytes` 13,612,503,040 B |
| python | **1.76 GiB** | ledger `python_peak_rss_bytes` 1,893,068,800 B |
| the model file | **5.29 GiB** | memory-mapped, so it sits INSIDE llama-server's 12.68 as evictable pages rather than on top of it |
| **`MemAvailable`, tightest instant** | **5.63 GiB free** | shard 0 at 08:01:32Z; never lower across 601 samples |

Per-shard low-water marks: shard 0 **5.63 GiB**, shard 3 5.95, shard 1 7.64,
shard 2 7.84. The two heavier shards ran hotter and still left over 5.6 GiB.

**Why the earlier 0.59 GiB reading was wrong, in one sentence.** It summed two
processes' resident sets and subtracted from the machine, which treats the
memory-mapped weights as committed. They are not committed - they are
file-backed and the kernel can drop and reload them, which is why it reports
them as available. At the tightest instant llama and python held 13.96 GiB
resident while `MemAvailable` stood at 5.63 GiB, and the 5.29 GiB model is the
difference.

**The raise costs +0.25 GiB and it clears on both framings.** Per full-attention
layer per token the cache is 4 KV heads x 256 head dim x 2 for K and V; across 8
attention layers at f16 that is 32 KiB a token, so 0.25 GiB at 8,192 and 0.50 at
16,384. Kernel framing: 5.63 - 0.25 = **5.38 GiB spare**, 5.4 times the 1.0 GiB
the trigger asks for. Pessimistic framing, machine minus llama peak:
15.61 - 12.68 - 0.25 = **2.68 GiB**, still 2.7 times the bar. **The answer does
not depend on which framing is accepted**, which is the strongest thing that can
be said for it.

**One instrument caveat, stated rather than buried.** `cgroup_peak_bytes` is
empty and the cgroup memory files read `unavailable` on all four shards, as the
schema warned. So the container limit is not readable and `/proc/meminfo` - the
whole virtual machine - is the reading we have. On a GitHub-hosted runner the job
owns the machine, so the two are the same thing; if that ever changes,
`MemAvailable` would overstate what the job may have and this calculation needs
redoing.

### Row 3 decision 1's REASON is now false, and its conclusion still holds

Decision 1 says the two changes belong in one commit "because flash attention
removes the term that scales with `ubatch` times `n_ctx`". **Flash attention is
already on**: `null` emits no flag, no flag means `auto`, and `auto` resolved to
enabled on every no-flag run (PR #530). So there is no saving still to come - it
is already inside the 12.68 GiB, and the raise pays the full 0.25 GiB.

One commit is still right, for a different reason: **`n_ctx` and
`flash_attention` are both fingerprint-digested**, so `n_ctx` moves
`pipeline_fingerprint` anyway and pinning the flag in the same commit costs
nothing extra. Split, the tree pays two comparability breaks for one change.

And pinning is worth doing even though it is behaviourally a no-op on this
processor: `auto` is a runtime autodetect that can resolve differently on other
silicon, so writing `on` removes a silent dependency. That is the opposite of
decision 5's `n_threads_batch` case, where `4` and `null` mean the same thing
everywhere.

### 32,768 is still refused, and its surviving reason is now much thinner

The memory objection is dead - 32,768 costs 1.00 GiB and still fits. The other
objection was that the two-call worst case is about 8,580 tokens, so 16,384 was
1.9 times headroom. **That 8,580 was measured under the 5,000-token cap and is
superseded**: at the 10,000-token cap row 5 landed, the two-call worst case is
15,889 tokens - 97 percent of 16,384. See the row 5 findings below. 32,768 is
still refused because nothing today needs it, but the phrase "it buys nothing"
no longer describes the margin. **The next plan that adds a call or raises the
cap has to re-derive this**, not inherit it.

### Row 5 shipped, and it corrected four of the numbers that authorized it (#548)

**The article cap went from 5,000 to 10,000 tokens**
(`extract.truncation_cap_tokens`), by owner instruction 2026-09-09. The
dependency on row 3 was real and the arithmetic that stated it was right in
direction and light in size. Measured on the real prompt rather than estimated:

| | tokens | share of 16,384 |
| --- | --- | --- |
| The estimate that authorized the row | 880 + 10,000 + 900 = 11,780 | 72 percent |
| Typical article, measured at 1.306 tokens a word | 997 + 10,046 + 900 = **11,943** | 73 percent |
| Worst article the ledger holds, at 1.585 tokens a word | 997 + 12,192 + 900 = **14,089** | **86 percent** |

**The constant overhead is 997 tokens, not 880**, and the tokenizer expansion has
a spread the single figure hid. Margin falls from 1.9 times to **1.16 times**.
Against the 8,192 window of the day before, 14,089 is 172 percent - so the row
was impossible until #547 landed, which is what the dependency was for.

**An article can overrun the budget its own cap gave it.** `truncate_to_tokens`
spends the cap as `int(cap / 1.3)` **words**, so prose that tokenizes harder than
1.3 tokens a word comes back over. The worst one overran by **21.9 percent** -
this said 16.8 percent until row 4 re-derived it, and the working is at the end
of section 5 - and that is the whole difference between 11,943 and 14,089.

**The number plan 11 must be sized against.** On a typical article the two-call
worst case is 13,580 tokens, 83 percent, margin 1.21 times - the estimate holds.
On the worst article the ledger holds it is **15,889 tokens, 97 percent of the
window, a margin of 1.03 times.** A second call at this cap has nothing left.
Plan 11 either sizes itself against 15,889 or raises the window with it.

**How often the cap actually bites**, from `state/item-health/2026-09.csv` - one
month shard, 4,556 rows over 2026-09-01 to 09, of which 4,117 are published
items, written on stock `ubuntu-latest` runners. `source_words_before_cap` counts
the body BEFORE the cut, so it is not censored by the cap the way `input_tokens`
is:

| Reading | Value |
| --- | --- |
| Cut at 5,000 tokens | 36 of 4,117 = **0.87 percent**, about four a day |
| Still cut at 10,000 | 9 of 4,117 = **0.22 percent**, about one a day |
| Cut articles, pre-cap words | 3,864 to 11,399, median 5,089 |
| Extra prefill a cut item gains | 23 to 5,000 tokens, median 1,616 |
| Prefill rate | median **9.85 tokens a second**, min 8.25, max 44.71 |
| Cost of 5,000 more tokens | **8.5 minutes**, 10.1 at the slowest rate |
| A summarize call today | median **114.6 s**, p95 **312.7 s**, longest 800.9 s |

That 9.85 independently re-derives the 9.84 the 2026-08-23 sweep took. A
five-item shard of worst cases goes from about 67 minutes to about **109**,
against a 200-minute timeout - inside it, and an all-five-cut shard is unlikely
at a 0.87 percent cut rate.

**"The largest prompt ever seen is 5,516 tokens" is WITHDRAWN on both counts.**
It was measured under the cap, so it recorded what the cap allowed rather than
what articles wanted; and it is stale, because the largest `input_tokens` on this
shard is 7,093. It appears in row 3 decision 2 below, which is superseded with
it.

**Still unmeasured and labelled so:** what the extra text does to summary
quality. It needs eval rows written at the new fingerprint, which cannot exist
until the pipeline has run - row 4.

**A new gate holds the pair.** `test_the_longest_article_the_cap_allows_still_fits_the_window`
reads the cap, the output budget and the window from `config/` and fails on any
later pair that does not fit. Nothing in the tree held that pair before; a doc
said it, and a doc does not fail.

### Two knobs the cap raise moved that row 5 did NOT touch

`finetune.sequence_length` has since been settled; `elements.max_per_article`
still needs an owner decision, and neither is a runner question.

| Knob | Value | What the cap raise did to it |
| --- | --- | --- |
| `finetune.sequence_length` | 8192 -> **16384, landed 2026-09-09** | The worst training row is now about 11,900 typical and 14,088 worst, both above 8,192. The wrangler DROPS an over-length row and counts it - it never truncates - so the training set silently lost its longest rows: every article past about 5,500 words, while production went on summarizing them. Settled by raising the window to `models.summarize.inference.n_ctx` rather than by truncating, because a truncated target teaches the model to stop mid-summary. One sum now sizes both windows and `test_the_training_window_covers_the_longest_row_the_cap_allows` fails on any later pair that does not fit. The cost is GPU memory on the machine that trains, which is not the runner, and it is unmeasured because nothing has trained yet - `SEQUENCE_LENGTH_OVERRIDE` in the notebook is the per-session way down |
| `elements.max_per_article` | 256, **unchanged** | Was above the densest article's candidate count of about 211; now below it at about 420. **A bound that did not bind now binds.** The densest long article keeps its first 256 quantities in article order and `candidates_found` records what the pass matched. News prose front-loads and the planner reads at most 16 by index, so the loss is small and recorded - but it is no longer theoretical |

One more question was recorded open rather than answered, in
`docs/architecture/summarize/prompt.md`: **whether the summary band ladder earns
a sixth rung.** The whole-read range doubled from 3,846 words to 7,692, so the
top rung now covers a span twice as wide as the one it was cut for - a
3,000-word piece and a 7,692-word piece share an ask, at 20 to 1 and 51 to 1.
Every rung floor still sits below the cut point, so nothing is broken. Editor's
call, then the owner's.

### Row 4 now prices three changes, and that is a deviation with a reason

Its decision 1 wanted one suspect rather than three. It now carries the window,
the pinned flag and the article cap together. Written up with the four questions
the dispatch settles, in section 5.

---

### SUPERSEDED - "the window does not fit", and the reading that was incomplete (#539)

**Everything under this heading down to the rows 1-and-2 summary is WRONG about
its conclusion and right about its method.** It subtracted two processes'
resident sets from the machine, which counts the memory-mapped weights as
committed; they are not. The correct reading is the `MemAvailable` capture at the
top of this section, and the window shipped at 16,384 in #547. Kept rather than
deleted because the process detail below - which python is the job's, when the
two peaks coincide, why the ONNX encoder is absent - is still accurate and still
useful. Read the conclusions as retracted and the observations as good.

**16,384 does not fit, and the raise does not have to be priced to say so - the
deficit exists at 8,192, before the change, and doubling the window can only add
to the KV cache.** Every question that was open about the figure is now shut.

**The recorded python is the job's, not the instrument's.** The sampler is a
bash loop calling `awk`, `cat` and `date`, and it matches a `comm` beginning
`python`, so none of its own processes is counted. Of the three python processes
seen at every peak, **two are the host's** - already running at the first sample,
taken before `python -m idhazh work` starts, holding 63,432 to 69,780 kB between
them, about 4 percent of the recorded figure. A fourth appears in 6 of 1,261
samples, holds under 28 MB, and is never present at a peak. **The job's own
python is 1.49 to 1.55 GiB, in one process.** Taking the host's two out moves the
worst shard from 0.59 GiB free to **0.66 GiB**, which is still under the 1.0 GiB
the trigger asks for.

Two readings matter more than the peak. The job's python is at about 1.2 GiB
**within fifteen seconds** - four fifths of it is a load cost paid before the
first article is fetched. And the two peaks coincide: llama-server's high point
and the sum's high point are the same sample on all four shards, with python at
76 to 88 percent of its own peak then. So the two do not cancel.

**The ONNX encoder is not resident in a work shard at all** - `stage_work` never
constructs an `Embedder`, the three callers are `stage_plan`, `stage_assemble`
and `backfill-vectors`, and `embed.py` imports `onnxruntime` inside the functions
that need it. **The faithfulness scorer is resident**, and is used from inside the
summarize loop, so `torch` and `transformers` are alive at llama-server's peak by
design. How much of the 1.5 GiB they hold is **not measured and was not guessed** -
the shared venv has neither package, and a laptop figure for a resident set is
not a runner figure.

**No reduction was proposed, and the reason is in the readings.** llama-server
starts before the work step, is killed at job end, and climbs from 8.68 GiB to
its peak across the whole shard. A scoring pass moved after summarizing would
still run beside a server holding its maximum. The concurrent peak falls only if
the server stops first, which means moving the `/metrics` scrape ahead of it and
reordering five steps - a pipeline-shape decision with an owner, not a worker's
call.

**The next run can answer better.** The sampler now writes `python-procs.tsv`
beside `rss-samples.tsv`: one row per python process per sample with pid, `comm`,
both memory marks, the executable and three argv fields - three rather than the
whole command line, because `comm` is `python3` for every one of them and names
nothing, while the executable plus argv 1-3 separates the job from a distribution
daemon and stops before anything a command line might carry further along
(section 1b). Cost: about 113 kB a shard in a two-day artifact.

### The owner's choice, and nothing else is waiting on a measurement

1. **Raise the window anyway** and accept a margin under 1.0 GiB on three of four
   shards. That is overriding trigger 1, not clearing it.
2. **Find the 1.5 GiB first.** One dispatch with `faithfulness: false` prices the
   scorer's share on the runner with no code change. If it is most of the 1.5 GiB,
   stopping llama-server before a separate scoring pass returns roughly that much.
3. **Leave `n_ctx` at 8,192.** The two-call design's 8,580-token worst case is
   105 percent of it, so this also holds plan 11.

---

### What rows 1 and 2 changed under the plan

**Row 1 shipped three of its six fields and withheld three, with evidence.**
`python_peak_rss_bytes`, `cgroup_peak_bytes` and a corrected `python_vmhwm_kb`
sampler column landed. `kv_cache_bytes`, `compute_buffer_bytes` and
`model_buffer_bytes` did not, because the lines section 13.3 sources them from
do not exist. Eight captured logs were searched - the four committed fixtures
under `tests/fixtures/runtime/` and four raw logs of run `32742672105`, 75 to
98 KB each - for `KV self size`, `kv_cache`, `compute buffer`, `CPU_Mapped`,
`model buffer` and `buf size`. Zero matches in any of them. At llama.cpp
`b10598` the server prints twelve startup lines at its default verbosity of 3
and the whole model-loader block is absent: no `llama_model_loader:`, no
`print_info:`, no `load_tensors:`, no `system_info`. Three columns empty on
every row for ever is speculative generality, so they were refused rather than
minted (Fowler).

**Row 2 chose the per-entry block over the qualification gate, and added a
witness.** `models.inference` is gone; each `models.<role>` carries its own
block, and the block carries `declared_for`, the SHA-256 of the entry it is set
for. `ModelsConfig` refuses a config where the two disagree. The qualification
gate was refused because `validate.yml` builds a scratch config whose
`models.summarize` is the candidate and whose every other control is the
committed one - that pairing IS the experiment, so a gate refusing an unmeasured
pairing would refuse the measurement and leave the daily path silent. Moving the
block alone was also not enough: the confirmed red state edits five strings in
place, which a per-entry block still accepts. `pipeline_fingerprint` was proved
unmoved - the same 14 digested knobs stamp `2b9be483...` on both trees.

---

## 1a. Why rows 3 and 4 are held - two ESCALATE triggers, both measured

**Trigger 1 - memory - is already breached at today's window, before the row
runs.** Section 11.2 sized the raise against 13.29 GiB peak and 1.61 GiB free.
That figure is llama-server's high-water mark ALONE, which is the whole point of
row 1 decision 1. Adding llama-server and python at the same instant, sample by
sample, over the four committed captures of run `2026-08-29-3` (291 to 383
samples a shard, 15 s apart, GitHub-hosted `ubuntu-latest`, 4 vCPU, 16 GB,
captured 2026-08-29, recomputed 2026-09-08):

| Shard | llama-server alone | Both at one instant | Free of 14.90 GiB |
| --- | --- | --- | --- |
| 3 | 13.16 GiB | **14.31 GiB** | **0.59 GiB** |
| 2 | 12.94 GiB | 14.15 GiB | 0.75 GiB |
| 0 | 12.57 GiB | 13.93 GiB | 0.97 GiB |
| 1 | 12.65 GiB | 13.86 GiB | 1.04 GiB |

Spread 0.45 GiB. Three of four shards are already under the 1.0 GiB the trigger
asks for, at `n_ctx` 8,192. The independent second instrument agrees: the widened
`state/runtime-counters.csv` now holds 225 rows over 56 runs, worst
`peak_rss_bytes` 13.82 GiB - 0.64 GiB above the 13.18 GiB
`docs/reference/measurements.md` recorded on 2026-09-01, with no model or window
change in between.

**Trigger 2 - the instrument - is RESOLVED, by PR #530.** It was raised because
no captured log carries a flash-attention line, a KV-buffer line or a
compute-buffer line. The cause was the verbosity, not the build. Measured
2026-09-09 on a Windows developer box against `llama-server` `b10444`
(`5f754ea0e`) and the 8B weights, three runs an arm, zero spread on every
figure:

| Reading, at `-lv 4` | no flag, as committed | `-fa on` | `-fa off` |
| --- | --- | --- | --- |
| `llama_context: flash_attn` | `auto` | `enabled` | `disabled` |
| `resolve_fused_ops: Flash Attention enabled` | present | absent | absent |
| `sched_reserve: CPU compute buffer size` | 112.01 MiB | 112.01 MiB | 572.01 MiB |
| `/props` and `/metrics`, whole documents | identical | identical | identical |

Three consequences, and the third is the one that changes the plan.

1. **The instrument is the log at `-lv 4`, not `/props`.** `/props` and
   `/metrics` are byte-identical between the two arms, so neither can answer the
   question. `/props` remains the right reader for the effective `n_ctx` and the
   build string, and needs no verbosity change for those.
2. **The check has three states, not two.** `llama_context: flash_attn` prints
   what was ASKED for, so with no flag it says `auto` - which is exactly the
   non-answer the oracle exists to refuse. `resolve_fused_ops` is the decision
   and prints only when there was one to make. Absent means the verbosity was
   not raised, and that fails the CHECK rather than attention. Corroborate with
   the compute-buffer size, which is a physical consequence where a log string
   is grammar that moves between builds. `-lv 4` costs 1,085 bytes a start
   rather than 16,011 - 206 lines against 12.
3. **The committed config already resolves to flash attention ON.** `null` emits
   no flag, no flag means `auto`, and `auto` resolved to enabled on all four
   no-flag runs. So row 3's flash-attention half may be a no-op on this
   processor, and O22's "flash attention pays for the doubling" may already be
   priced into the 13.29 GiB baseline rather than being a saving still to come.
   Whether `auto` resolves the same way on a runner's processor is untested and
   one CI run with `-lv 4` settles it.

Build gap, stated rather than hidden: `digest.yml` pins `b10598` and the box
tested `b10444`, 154 builds apart. Half the gap is closed by evidence -
`tests/fixtures/runtime/2026-08-29-3-shard-0.server-head.txt` is a real `b10598`
runner capture and opens with the same eleven startup lines in the same order,
`verbosity = 3` among them. So the startup grammar matches across both builds
and both machines, and the absent loader block was never a CI artefact.

**Trigger 1 still stands, and row 4 still has no memory instrument.** Row 4
decision 2 closes the 7.7 GiB gap from the KV-buffer and compute-buffer lines,
which `-lv 4` does now produce - but the arithmetic that gap sits in was written
against llama-server alone, and the concurrent figure above is what a raise has
to clear.

---

## 2. Row #1 - Six numbers the job already has and throws away

- **Scope:** `kv_cache_bytes`, `compute_buffer_bytes`, `n_ctx_configured`, `model_buffer_bytes`, `python_peak_rss_bytes` and `cgroup_peak_bytes` added to the runtime counters row, all from data the job already collects.
- **Files touched:** `backend/idhazh/contracts/runtime_counters.py`, `schemas/runtime-counters-row.schema.json`, `backend/idhazh/llm/**` (the server-log reader), `.github/workflows/digest.yml`, `tests/fixtures/contracts/runtime-counters-row/*.json`, `state/runtime-counters.csv` (widened), `backend/tests/test_contracts.py`, `docs/reference/measurements.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite; one dispatch writing the new cells.
- **Oracle:** The widened ledger re-parses every existing row with the new values absent, and the byte delta equals exactly the new commas plus the new header characters - counted, not estimated. A widening that moved a cell would fail that arithmetic.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `peak_rss_bytes` is llama-server's high-water mark **alone**, so every headroom figure quoted today is an upper bound on headroom - the unsafe direction. `cgroup_peak_bytes` is the number the runner counts against the limit and is the only authoritative one | Section 13.3 |
| 2 | The sampler reads `VmHWM` for llama-server and `VmRSS` for python. `VmRSS` is instantaneous, so a 15-second sampler can miss a spike and the recorded python peak is a **lower** bound. Read `VmHWM` for both | Section 13.3 |
| 3 | Append at the end. A new optional column is null on every row written before it existed, so report on the **data**, never on the column list | Recorded trap |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Raise the window and measure afterwards | Arithmetic accounts for only about 5.6 GiB of the 13.29 GiB measured, so no pure extrapolation is trustworthy. Only the delta is, and only two terms move with the window | Carmack |

---

## 3. Row #2 - A model swap can no longer inherit in silence

- **Scope:** End the shared `InferenceConfig`, so a settings block is bound to the model entry it was derived against.
- **Files touched:** `backend/idhazh/contracts/app_config.py`, `config/idhazh.json`, `schemas/app-config.schema.json`, `tests/fixtures/contracts/app-config/tuned.json`, `backend/idhazh/llm/server.py`, `backend/idhazh/evals/qualify.py`, `frontend/src/lib/server/config.ts`, `backend/tests/test_contracts.py`, `backend/tests/test_qualify.py`, `docs/concepts/config.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite.
- **Oracle:** A config that names a different model without supplying settings for it **fails validation with a message naming the missing block**. Whether that is achieved by moving the block onto the model reference or by a qualification gate that refuses an unmeasured pairing is the row's call; what is not open is leaving it silent.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Every llama-server setting quoted anywhere carries the model entry, the runner and the date it was derived against. A bare `n_ctx: 16384` in a doc is an unmeasured number justifying a design | O38, Guardrail #10 |
| 2 | The design's neutrality is preserved: the fix binds settings to an entry, it does not put a model's identity into a name | O38, section 15.4a |
| 3 | `flash_attention` **already exists** as a key set to `null`. O22 is a value change, not a new knob | C19, verified 2026-09-05 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | A comment warning that settings are model-specific | A comment is not a gate. The failure is silent and produces a plausible run | Fowler |

---

## 4. Row #3 - The window doubles and flash attention pays for it

- **Scope:** `n_ctx` 8,192 to 16,384 and `flash_attention` on, in **one** commit.
- **Files touched:** `config/idhazh.json`, `backend/idhazh/llm/server.py`, `backend/idhazh/contracts/app_config.py`, `schemas/app-config.schema.json`, `tests/fixtures/contracts/app-config/tuned.json`, `frontend/src/lib/server/config.ts`, `backend/tests/**`, `docs/reference/measurements.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite; one dispatch reading the server's own startup lines.
- **Oracle:** Flash attention is asserted **active from the server's own startup line**, not from the flag having been passed - and the measured worst peak stays at least 1.0 GiB below the 14.90 GiB usable. A flag that was accepted and ignored is the failure this oracle exists to catch.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | One commit, because flash attention removes the term that scales with `ubatch` times `n_ctx` - which is exactly what the larger cache costs. Split, the intermediate state pays a bill it need not | O22, section 11.2 |
| 2 | ~~**32,768 is refused even though it fits.** The largest prompt ever seen is 5,516 tokens and the truncation cap is 5,000, so a 32K window is more than five times what the pipeline can put into it, and it would spend 1 GiB of a 1.61 GiB margin doing so~~ **SUPERSEDED by row 5.** Both numbers in this reason are dead: the cap is 10,000 and 5,516 was measured under the old cap. The conclusion stands on the thinner reason recorded in section 1 | Section 11.2, superseded 2026-09-09 |
| 3 | 131,072 fails on wall clock before memory: filling it once at 9.84 tokens a second takes 222 minutes for a single article, against a shard timeout of 200 | Section 11.2 |
| 4 | Cache types stay `f16`. `q8_0` halves the cache and **changes how partial sums accumulate**, so it changes the words - a separate measurement, not this commit | Section 11.2a |
| 5 | `--ubatch-size` stays 512 and `--threads-batch` stays unset. The first exists only to pay for a window this pipeline cannot fill; writing `4` where `null` sits invalidates every prior work identity for zero change in output | Section 11.2a |
| 6 | The candidate table from plan 08 is **not** in the 8,580-token worst case and must be added before the number is final. It is bounded by construction, so this is arithmetic, not an estimate | Section 11.2 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Raise the window without flash attention | Works, and pays about 0.25 GiB it need not | Carmack |
| 2 | Take `--jinja` in the same commit | Highest-value item on the settings list and it needs its own digested config field. It moves the words and deserves its own measurement | Andre, section 11.2a |

---

## 5. Row #4 - One run prices the runtime and nothing else

- **Scope:** One frozen-set run after rows 1 to 3, recording what the runtime change alone did to memory, wall clock and the words.
- **Files touched:** `docs/reference/measurements.md`, `state/fingerprints.csv` (a new stamp lands naturally)
- **Acceptance gates:** the full suite; one dispatch with nothing else in flight.
- **Oracle:** The recorded numbers carry the model entry, the runner, the date and the spread, and the `pipeline_fingerprint` moved - which is free, external evidence that the config change actually ran rather than being merely committed.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The boundary is here so that if a summary metric moves at plan 11 there is **one** suspect rather than three. Retiring the model, raising the window and adding a call each invalidate comparability on their own | Andre, 2026-09-05 |
| 2 | Take the memory reading with nothing else in flight. The KV-buffer and compute-buffer lines from the server log are what close the 7.7 GiB gap between arithmetic and measurement | Carmack, section 13.1 |
| 3 | Comparability of `summary_faithfulness` across this boundary is **not** claimed. Flash attention moves float accumulation order, so it moves the words | Section 11.2a |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Fold this measurement into plan 11's cutover | Then three changes land together and no test separates them | Andre |

### What row 4 has to answer, as it now stands (2026-09-09)

Rows 1, 2, 3 and 5 are merged, so the dispatch is unblocked and `main` carries
`n_ctx` 16,384, `flash_attention` `on`, `log_verbosity` 4 and a 10,000-token
article cap. Four things this run settles, and the last one is new:

1. **The KV-buffer question, from the first real runner log at `-lv 4`.** The
   projection says the raise costs 0.25 GiB. A KV buffer near 512 MiB confirms
   it; near 2,304 MiB says the head-dimension card was read wrong and the raise
   actually cost about 1.1 GiB. Either way the window still clears the trigger -
   this decides how much margin plan 11 inherits.
2. **Whether `auto` resolves to enabled on a RUNNER's processor.** Every arm of
   the 2026-09-09 measurement was a Windows developer box. `resolve_fused_ops`
   is now the reader and `flash_attention: on` is now the ask, so the run either
   prints the decision or fails the check.
3. **Memory at the doubled window**, against the 5.63 GiB `MemAvailable` low-water
   mark this section's opening table recorded at 8,192.
4. **What the cap raise cost in wall clock**, against the predicted 8.5 minutes
   for a cut item and about one cut item a day at the new cap.

**The deviation, stated rather than taken silently:** decision 1 wanted one
suspect and this run carries three - the window, the pinned flag and the article
cap. The alternative was a second three-hour dispatch to separate a window raise
from a cap raise. Plan 11 can still tell them apart because they move different
metrics: the window moves memory, the cap moves prefill seconds and the words of
long articles. `pipeline_fingerprint` moves once for both, because `n_ctx` and
`truncation_cap_tokens` are both digested, so **no summary written before today
is comparable with one written after** - which is correct rather than a cost, as
the text the model read is not the same text.

Dispatch: `gh workflow run digest.yml -f shards=4`, nothing else in flight.

### The dispatch, and what to read when it lands

**Run `34379502244`**, `workflow_dispatch`, 4 shards, faithfulness on, started
2026-09-09 16:53Z on `0d49b61f`. Nothing else was in flight, and
`concurrency: group: digest` with `cancel-in-progress: false` means the 18:20Z
cron queues behind it rather than overlapping.

**The baseline it is read against is run `2026-09-09-34323771996`** - the 07:25Z
scheduled run, same day, same 4 shards, `n_ctx` 8,192, 5,000-token cap, 601
memory samples. Same-day is deliberate: it holds the source set and the news
volume roughly still, so the delta is the runtime rather than the calendar.

**Not a frozen article set, and that is a second deviation.** The `date` input
would re-run a past day, which overwrites that day's published digest, so it was
not used. The article set therefore differs between the two runs. It does not
weaken what row 4 is for: memory at a doubled window, the KV-buffer line and the
prefill rate are properties of the runtime, not of which articles arrived.
It does mean **no summary-quality comparison may be drawn from this pair** - and
decision 3 already refused that claim for a different reason.

| What to read | Where | What each answer means |
| --- | --- | --- |
| KV buffer at `-lv 4` | the shard's server log, first real runner capture at raised verbosity | near 512 MiB confirms the 0.25 GiB projection; near 2,304 MiB says the head-dimension card was read wrong and the raise cost about 1.1 GiB |
| `resolve_fused_ops: Flash Attention enabled` | same log | present means `on` was honoured on a runner's processor; absent means the verbosity did not take, which fails the CHECK rather than attention |
| `MemAvailable` low-water mark | the `/proc/meminfo` capture PR #541 added | against 5.63 GiB at 8,192. Under 1.0 GiB fires ESCALATE trigger 1 |
| `peak_rss_bytes`, `python_peak_rss_bytes` | `state/runtime-counters.csv` | the second, independent instrument |
| prefill seconds on cut items | `state/item-health/2026-09.csv`, `source_words_before_cap` | against a predicted 8.5 minutes for a cut item and about one cut item a day |
| `pipeline_fingerprint` | `state/fingerprints.csv` | it MUST have moved. `n_ctx` and `truncation_cap_tokens` are both digested, so a stamp that did not move means the config change did not reach the run |

Every number written from this run carries the model entry, the runner, the date
and the spread (Guardrail #10), and lands in `docs/reference/measurements.md`.

### The six readings, against the six predictions above (2026-09-09)

Full working, hardware and spread in
[`../docs/reference/measurements.md`](../docs/reference/measurements.md), section
"What the doubled window and the doubled cap cost". Five predictions held. One
was wrong, and it is named as wrong below.

| # | Reading | Prediction | What came back |
| --- | --- | --- | --- |
| 6 | `pipeline_fingerprint` | must have moved | **MOVED.** `22f44b21...` replaced `30d96862...` at 16:59:26Z, for exactly the three settings dispatched |
| 1 | KV buffer | 512 MiB or 2,304 MiB | **512.00 MiB, all four shards, no spread.** 32 KiB a token, exact |
| 2 | flash attention | `resolve_fused_ops` line present or absent | **Enabled** - but on `llama_context`, not `resolve_fused_ops`. **The prediction named the wrong line** |
| 3 | `MemAvailable` low | against 5.63 GiB; under 1.0 GiB escalates | **6.84 GiB**, 1.21 GiB HIGHER. Trigger 1 does not fire |
| 4 | `peak_rss_bytes` | second instrument | **12.16 GiB against 12.68**, i.e. it fell. The instrument cannot resolve 0.25 GiB |
| 5 | prefill on cut items | 8.5 min a cut item, about one a day | **Zero items cut.** The rate behind the prediction is re-confirmed at 9.86 tok/s |

**Reading 1 settles the plan's most valuable question and the answer is exact.**
All four shards printed `llama_kv_cache: size = 512.00 MiB ( 16384 cells, 8
layers, 1/1 seqs), K (f16): 256.00 MiB, V (f16): 256.00 MiB`, and
`n_embd_head_k_all = 256` confirms the head dimension the projection was built
on. 512 MiB over 16,384 cells is 32 KiB a token, which is the projected number
to the byte. **The window raise cost 0.25 GiB and the 1.1 GiB alternative is
dead.**

**Reading 2's prediction was wrong, in those words.** It said the absence of
`resolve_fused_ops: Flash Attention enabled` would mean the verbosity did not
take. The verbosity took - `resolve_fused_ops` printed nine lines for other
fused ops - and that string does not exist in build 10598. Flash attention
reports on `llama_context: flash_attn = enabled` instead, on all four shards, so
`on` was honoured on a runner's processor. The check passed; the plan looked in
the wrong place. **What `log_verbosity: 4` actually bought is reading 1**: the
baseline at verbosity 3 wrote 342 to 404 log lines with no KV line among them,
and the priced run wrote 1,306.

**Reading 3 went the other way and the reason is the runner, not the window.**
The baseline's tight 5.63 GiB came from its two Intel Xeon 8573C shards, which
committed about 2 GiB more than the same job on EPYC; the priced run drew no
Intel shard. Matched on the same processor the window's cost does appear and it
is the projected size: `Committed_AS` peak on EPYC 9V74 went 10.52 to 10.84 GiB,
**+0.32 GiB against +0.25 projected**, the rest being the longer prompts the cap
admits. **Not measured: the doubled window on an Intel shard.** The KV buffer is
512 MiB whatever the processor, so 5.63 - 0.25 = 5.38 GiB carries the arithmetic,
but no run has observed it.

**Reading 5 could not be taken, because the event did not happen.** Zero of 75
items ran past the 7,692-word cut point. At about 0.22 percent of items and
roughly six runs a day, a single 70-item run expects 0.17 cut items - so zero is
what the prediction implies rather than a contradiction of it. The 8.5-minute
figure stands unexercised. Its ingredient is re-confirmed and did not move:
prefill ran at a median 9.86 tokens a second at 16,384 against 9.97 at 8,192 on
the same processor, down 1.1 percent.

**What nothing predicted, and it is the most useful finding here.** One item on
this run reached **8,741 input tokens** - the largest prompt in the whole
4,187-row month shard, and the only one ever over 8,192. It was not cut. **Under
the old 8,192 window it would not have fitted, and under the old 5,000-token cap
it would have been cut before it could grow that large.** The window raise and
the cap raise are load-bearing as a pair and were exercised on the day they
landed, not at some later margin. Largest KV occupancy was 9,082 cells, 55
percent of the window.

**The wall clock did not pay.** 1h42m43s against 1h45m05s - 142 seconds faster,
2.3 percent - and the slowest shard 18 seconds slower, 0.5 percent. Different
article sets, so neither attributes cleanly; jointly they rule out a large
regression. **A second thing the pair did not predict:** the processor a shard
draws sorts its prefill rate 4.2 times harder than any setting in `config/`
does - Intel Xeon 8573C ran at 41.00 tokens a second against 9.86 on EPYC 9V74.

### What plan 11 inherits, now that the KV reading is in

**The margin is unchanged, because the reading confirmed rather than moved the
projection.** [Plan 11](20260905-11-two-call-planner-plan.md)'s two-call worst
case at the current cap is still **15,889 tokens, 97 percent of 16,384, a margin
of 1.03x**. Reading 1 came back at the confirming end, so nothing about that
arithmetic changes.

**What did change is that a wider window is now cheap on evidence rather than on
a guess.** At a measured 32 KiB a token, `n_ctx` 32,768 costs 1,024 MiB of KV -
512 MiB more than today - and the measured low-water mark is 6.84 GiB, so the
further doubling would still leave about 6.3 GiB, 6.3 times the trigger's bar.
**If plan 11 decides its second call needs more window, memory is not what stops
it.** The standing objection to 32,768 was always that nothing needed it; that
is now the only objection left, and plan 11 is the plan that may retire it.

**One caution plan 11 must carry:** a real 8,741-token prompt now exists in the
ledger, so the worst case it sizes against is no longer a paper number waiting
for an article to justify it. The largest prompt seen has gone 7,093 to 8,741 in
one run, and the 14,089-token worst article is what the cap permits rather than
what has yet arrived. Plan 11 sizes against 15,889, as row 5 already ruled.

### The 16.8 percent figure in row 5's findings is corrected to 21.9 percent

Row 5's write-up above, and the section it landed in
`docs/reference/measurements.md`, said `truncate_to_tokens` overran "by 16.8
percent" on the worst article. **That figure is not reproducible from the
numbers beside it and has been corrected.** The working:

- `truncate_to_tokens` spends the cap as `int(cap / 1.3)` words. At 5,000 that
  is 3,846 words, and all 36 cut rows sit exactly on it.
- Their `input_tokens` ran 5,582 to 7,093. The section's own least-squares
  intercept for the constant prompt is **997 tokens**, corroborated by 3-word
  items measuring 980 to 985.
- So the article alone measured 4,585 to 6,096 tokens: **1.192 to 1.585 tokens a
  word**. The cap asked for 5,000 and the worst article delivered 6,096.
- `(6096 - 5000) / 5000` = **21.9 percent**, and the same 1.585 at the
  10,000-token cap gives 7,692 x 1.585 = 12,192, over by the same 21.9 percent.

**16.8 percent comes from subtracting 1,255 instead of 997**, which lowers the
worst ratio to 1.518. The section used 1,255 for the overrun sentence and 997
for the worst-case table two paragraphs down - **one section, two constants, two
worst-case ratios.** 997 is the one the evidence supports, so **21.9 percent is
correct and the 14,089-token worst case the table already carried was right all
along.** Nothing downstream moves: 14,089, the 1.16x margin and plan 11's 15,889
were all computed at 1.585.

---

## See also

- [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - the decision record this group executes.
- [`20260905-08-element-table-plan.md`](20260905-08-element-table-plan.md) - the previous plan.
- [`20260905-10-visual-plan-contract-plan.md`](20260905-10-visual-plan-contract-plan.md) - the next plan.
