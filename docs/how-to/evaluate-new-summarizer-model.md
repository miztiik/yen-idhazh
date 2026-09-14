# Swap the Summarizer Model

**Last Updated**: 2026-09-14

The swap is one line in `config/idhazh.json`:

```json
"models_file": "models/qwen3.5-9b-q4km.json"
```

Point it at another file in `config/models/` and everything follows it: the
daily run, the qualification arm and the bench all read the entry that file
holds. **The revert is the same line back.**

The rest of this page is what to do before you write that line and what to check
after. It covers the build-time summary model, which also decides the picture.
The faithfulness scorer and the browser search model have their own contracts
and are not changed here.

## What is one command, and what is not

| | |
| --- | --- |
| The swap | one line in the committed config |
| The revert | the same line back |
| The bench | one dispatch. It says how fast |
| The qualification | one dispatch, hours of runner time, eleven gates on a frozen corpus. It says how good |
| The decision | a person's, and it stays one |

**Qualification will never be one command.** Eleven gates on a frozen corpus is
the price of knowing whether a model is good, and no arrangement of the harness
makes that cheap. What the harness buys is that the price is paid the same way
every time.

Adoption is a Level 5 decision ([../../CLAUDE.md](../../CLAUDE.md) section 6).
The gates inform it; they do not make it.

Three blocks follow: **measure the candidate**, **adopt**, **revert**.

---

## Block 1 - Measure the candidate

### 1.1 Write the candidate's model file

A candidate is a file under `config/models/` before it is a dispatch. Copy the
incumbent's file, rename it for the new weights, and change every field that is
a fact about them.

| Field | Why it is there |
| --- | --- |
| `id` | the alias published summaries and the ledger carry |
| `repo`, `revision` | the repository and the 40-character commit. A branch name is not a pin, because `main` moves |
| `file`, `quantisation` | two files from one model are two candidates |
| `sha256` | the runtime opens bytes, not a model-card name |
| `hf_base_repo` | the base an adapter is trained against, which the fine-tuning notebook checks |
| `arch` | the architecture name inside the GGUF |
| `inference` | every runtime knob, including the window and the sampler |
| `turns` | where the system text goes, what opens and closes a turn, and which keyword turns thinking off |

**`inference.declared_for` and `turns.declared_for` are the safety catch, and
they both hold this model's own digest.** Config load refuses an entry whose
block is declared for one set of weights while the entry names another, and it
says which repair it wants: re-derive the numbers, because every one of them was
measured against one model on one runner, or re-record the markers, because
every one of them was read off the server that renders those turns. So a
half-finished candidate cannot run - not in the bench, not in qualification, and
not in a daily run.

The sanitizer reads `turns` too. It proves it strips every marker the entry
declares and **refuses an entry whose control tokens it does not recognise**, so
a model from an unknown template family is a refused config rather than a silent
hole in Guardrail #11.

Do not point `models_file` at the new file yet. Nothing below needs it, and
keeping the pointer still means the adopt arrives later as a one-line diff a
reviewer can read at a glance.

### 1.2 Hold the control

One changed input a run, or the run measures a bundle. Hold constant:

- the llama.cpp build;
- the prompt template and the rendered band values;
- the output schema;
- the extraction and sanitization versions; and
- the truncation cap.

The candidate's own `inference` block is not a control - it is part of the
candidate. If a model needs a different sampler to work at all, that is a second
candidate configuration and it is measured separately. Do not adopt a vendor
default silently.

### 1.3 Bench it - how fast

One dispatch, two arms, one candidate typed once:

```bash
gh workflow run measure.yml \
 -f target=bench \
 -f candidate_repo='<publisher>/<name>' \
 -f candidate_revision='<40-character commit>' \
 -f candidate_file='<weights filename>' \
 -f candidate_sha256='<digest those bytes must have>' \
 -f candidate_id='<alias the server answers to>' \
 -f candidate_quantisation='Q4_K_M' \
 -f threads='4'
```

Leave every `candidate_*` box empty and the bench measures the model config
already names. That is the calibration dispatch: the page it emits has to
reproduce that model's committed dossier inside the spread both sides declare.

The digest is not optional. Without it the harness benches whatever the
repository holds today and says nothing about it, and a number filed under a
model that never ran is worse than no number (CLAUDE.md Guardrail #10).

**Those six boxes repeat fields the candidate's model file already holds - seven
in the qualification dispatch, which also takes the byte count - and that is a
step this page should not need.** Both dispatches were written before a model
was one file. The change that removes the step is one input naming the file, the
same string the swap itself writes, and it is not built. Until it is, copy the
values out of the file you wrote in 1.1 rather than typing them from a model
card, so the bench and the adoption cannot disagree about which bytes are the
candidate.

**Arm one, artifact `bench-raw`** - raw prefill and decode with nothing else in
the process:

- `hardware.txt`: CPU topology, cgroup limits and runtime identity;
- `weights.txt`: exact GGUF size and SHA-256;
- `llm.json`: prefill and decode rates with spread;
- `resources.json`: wall time, CPU pressure, throttling and memory events.
 Cgroup `memory.peak` can be absent or cumulative; it is not a per-model RSS
 comparison; and
- `bench/raw-arm.json`: the same numbers as readings, which is what arm two
 folds into the page.

**Arm two, artifact `bench-server-<runtime_candidate>`** - a real llama-server,
real fetches, real summaries over a fixed five-article corpus:

- `runtime-summary.json`: per-repeat startup, work and per-item timings, the
 resident-set samples, and the input and output drift verdicts;
- `cache-state.txt`: whether the weights were already on the machine, and the
 digests of the binary and the weights that ran;
- `readings.json`: every quantity the page carries, machine-readable; and
- `dossier.md`: **the page body, numbers already in it.** Paste it into
 `docs/reference/models/<model>.md`. It is also printed to the run summary, so
 the numbers are readable without downloading anything.

The bench never writes the committed config, never publishes, and never grades a
summary. It says how fast, not how good.

Two readings are cold on purpose. The **first download** is what a cache miss
costs, which is what the first run after a swap draws on every shard at once.
The **first server start of the job** is the model load with the page cache
holding none of the weights; every start after it is warm. Averaging the two
would hide the one that hurts.

What the resident-set rows do not say is how much of the peak is anonymous and
how much is file-backed pages the kernel can drop, so they cannot answer how
much headroom a second process has. `Rss_Anon` and `Rss_File` from
`/proc/<pid>/smaps_rollup`, sampled by the same thread that already samples
`VmHWM`, would settle it. It is unmeasured today and nothing gates on it.

To compare one dispatch against another, compare the readings rather than the
prose:

```bash
python backend/utilities/measure_llm.py compare \
 --observed <new>/readings.json \
 --declared <baseline>/readings.json
```

A quantity reproduces when the two values are closer than the two spreads added.
A reading taken once carries no spread, so it is printed rather than judged.

A laptop result is a laptop result. It can reject a candidate quickly and cannot
select production.

### 1.4 Retake the three readings a vocabulary sizes

Token counts do not transfer between model families, and three constants in
`backend/idhazh/measured.py` are sized by a tokenizer: the taxonomy definition
block, the empty encoding roles, and tokens a word at the truncation cut. Every
window sum in the project is spent at that last one.

```bash
gh workflow run measure.yml -f target=budgets \
 -f candidate_repo='<publisher>/<name>' \
 -f candidate_revision='<40-character commit>' \
 -f candidate_file='<weights filename>' \
 -f candidate_sha256='<digest those bytes must have>' \
 -f candidate_id='<alias the server answers to>' \
 -f candidate_quantisation='Q4_K_M'
```

The run summary carries a paste block: the three values, their subject and their
date, ready for `measured.py`, plus the dossier section they belong in. On any
box already serving the candidate, the same print is
`python backend/utilities/measure_budgets.py read --runner <where you ran it>`.

Do not paste them while the candidate is still a candidate. **The readings go in
with the swap, not before it**, because a reading names the weights it was taken
against and the repository holds one current reading of each. What tells you
they are due is:

```bash
python backend/utilities/measure_budgets.py check
```

It exits 1 and names every constant whose subject is not the configured model's
digest. After a swap it is red until the paste lands; that is the point of it.

### 1.5 Qualify it - how good

```bash
gh workflow run validate.yml \
 -f candidate_repo='<publisher>/<name>' \
 -f candidate_revision='<40-character commit>' \
 -f candidate_file='<weights filename>' \
 -f candidate_sha256='<digest those bytes must have>' \
 -f candidate_bytes='<byte count the target declares>' \
 -f candidate_id='<alias the summaries will carry>' \
 -f candidate_quantisation='Q4_K_M' \
 -f shards='3' \
 -f corpus_per_shard='10' \
 -f repeats='3' \
 -f job_budget_minutes='330'
```

The arm builds a candidate config under gitignored
`backend/var/candidate-config`, checks the SHA-256 and the byte count **before
the server starts**, freezes each shard's slice and hashes the model-visible
bytes before the first inference call, replays those bytes, interleaves the
repeats so none lands on a warm prompt cache, runs every injection canary on
live candidate calls, and counts every failed call in the denominator. It never
touches the committed config.

Then read the verdict:

```bash
python -m idhazh qualify-decide
```

The eleven gates and what each one refuses are in
[../concepts/evaluation.md](../concepts/evaluation.md). Three of them are hard
in a way worth repeating here, because they are the ones a fast model fails:

- **every injection canary survives**, all of them, not most (Guardrail #11);
- **no reasoning text reaches the reply** - no non-empty `reasoning_content`, no
 inline `<think>` block, and the parser reads every block, so an empty opening
 one cannot hide a second that reasoned; and
- **a repeat is identical** - same title, same summary, same key points, same
 `output_digest` at the deterministic sampler.

**Do not raise a timeout or lower a threshold to make a candidate pass.** Find
the cause or reject the candidate.

### 1.6 Decide

**Register the rule before you look at the outputs.** For every deterministic
hard metric, write down the direction, the paired statistic and the tolerance
first. No generic "no regression" threshold exists, and one invented after the
numbers are visible is a description of the numbers.

Compare: summarize success rate and failure codes; mean HHEM and HHEM-full;
unsupported numbers; dropped hedges; lead coverage; extractiveness and longest
verbatim run; compression; word-band compliance; generated-title fallback rate;
brief, abstract and truncated handling; and a human blind review of the same
source-summary pairs. Compression is a recorded diagnostic and never a
pass/fail.

**HHEM alone is insufficient.** A model can raise faithfulness by copying more
or by writing less. It is the production alarm, so it screens and does not
select:

- fewer than `evaluation.validation_articles` scored outputs -> no verdict;
- gain below `evaluation.validation_switch_margin` -> no automatic switch; and
- gain at or above the margin -> `switch_and_pause`.

**A model swap is a new series, not a new point on the old one.** Segment every
model-dependent metric by `model_id` and do not recompute a long run's date
between plan, model runs and decision.

What the decision still cannot have: the human label queue records one summary's
support verdict and cannot record paired informativeness, title quality or
key-point correctness. Until a typed pairwise label shape and a human-paced CLI
exist, a blind human review can describe a trade and cannot name a winner.

**The owner can approve a model for reasons outside the automated margin**
([../../CLAUDE.md](../../CLAUDE.md) section 0). Record the approval and the
measured trade in the pull request and in the living docs. A failing gate stays
failing and stays written down - do not re-score a run or move a threshold to
make an approval look automatic. That has happened once, and what it left is in
[../concepts/evaluation.md](../concepts/evaluation.md).


---

## Block 2 - Adopt

### 2.1 The line

```json
"models_file": "models/<candidate>.json"
```

That is the swap. No workflow changes: `digest.yml`, `validate.yml` and
`measure.yml` each follow the pointer and read the entry it names, and a test
refuses a model repository, a weights filename or a moving revision written into
any of them.

### 2.2 The two status lines

What is in force is printed by two commands, and they are the check that the
edit did what you meant:

```text
git grep -n '"models_file"' -- config/idhazh.json
git grep -n -E '"(id|file|sha256)"' -- config/models/
```

The first names the active file. The second prints the id, the weights filename
and the SHA-256 the runtime checks the downloaded bytes against.

### 2.3 What else the swap carries

| | |
| --- | --- |
| The three tokenizer readings | paste them now. `measure_budgets.py check` is red until you do, and every window sum is spent at one of them |
| `docs/reference/models/<candidate>.md` | the dossier. Paste the `dossier.md` the bench emitted; do not transcribe numbers by hand |
| Two status words | the candidate's dossier becomes `incumbent`, the model it replaced becomes `superseded`. They live in one place, so those two edits are the whole lifecycle change ([../reference/models.md](../reference/models.md)) |
| Docs and diagrams that name the configured model | search for the old id |
| Tests that assert the configured model | leave fixture ids that are deliberately historical or generic alone |

**The readings are the one source edit a swap costs, and that is deliberate.**
They sit in `backend/idhazh/measured.py` rather than in `config/` because they
are not tunable: each one is a measurement of a specific set of weights, it
carries the subject and date it was taken on, and `check` refuses the pair when
they disagree. A knob a person may turn and a reading a person may only retake
are different things (Guardrail #6).

Do not change historical payloads or historical measurement rows. A value-only
model change does not change a JSON shape; if the work also retypes a field or
adds one, the contract, its `version`, its changelog, the migration, the
generated schema and the drift gate move together
([../../CLAUDE.md](../../CLAUDE.md) section 11).

### 2.4 The fine-tuning check

**A base swap invalidates every adapter trained on the old base.** An adapter
loads onto a mismatched base without raising anything, and the damage arrives as
a quality drop nobody can attribute to it. The notebook's fourth step resolves
the teacher's base weights and stops when they are not the ones production
serves, so the refusal is where the adapter is loaded rather than where the base
is chosen ([fine-tune-a-model.md](fine-tune-a-model.md)).

**A swap also makes the training corpus mixed-teacher, and that is recorded
rather than prevented.** Every corpus row carries the `model_id` that wrote it
and `corpus/corpus.meta.json` holds the census. Read it before training, not
after:

```bash
python -c "import json;print(json.load(open('corpus/corpus.meta.json'))['models'])"
```

It already reads two ways: 1,015 rows from the retired `qwen3-8b-q4-k-m` and 429
from `qwen3-5-9b-q4-k-m` of 1,444, so a model trained on that corpus today is
learning mostly from a teacher that no longer serves.

### 2.5 What the first day costs

**The first run after a swap is cold on every shard at once**, because the
weights cache key carries the file and its revision. A cache miss is 5.29 GiB in
118 s (`n = 1`, spread unavailable, GitHub-hosted `ubuntu-latest`, 2026-08-23),
and each shard pays it - a warm-box bench figure is not the first real day. The
bench reports a cold arm for exactly this reason; read that one.

The steady-state cache holds one model. The transition can hold two and cross
the 10 GB ceiling, so before the first production run:

```bash
gh cache list --limit 100
```

and after the new commit is ready, delete only the outgoing summary model's
entry:

```bash
gh cache delete <old-summary-cache-id>
```

**Measure the cache, do not derive it.** The key names the model file and the
pinned llama.cpp build, so the outgoing model may already have aged out and
there may be nothing to delete
([../reference/github-actions.md](../reference/github-actions.md#the-cache-across-the-model-swap-measured-2026-08-27)).

Production derives the worker count as
`min(ceil(items / run.shard_size), run.max_parallel)`, so a full day at
`run.safety_ceiling_per_run` gives a worker 20 items. Do not size a timeout from
a five-item shard.

### 2.6 One identity gap to know about before you trust the rollout

The fingerprint records the GGUF file the runtime opened, the llama.cpp build,
the chat template and the runner class. A stamp built on an absent or
placeholder weights digest now raises rather than publishing, and the
qualification path digests the file it is about to run. **Production `stage_work`
still passes `ModelRef.sha256` - what config expected - and leans on the `work`
job's own `sha256sum` of the file on disk to make the two agree.** Until the
observed digest and runtime build are passed into `work` and compared there, a
swap leaves the new model recorded as an expectation nobody verified at the
point of use
([../architecture/contracts/determinism.md](../architecture/contracts/determinism.md)).

### 2.7 Before the first production run

1. Run the full local gates ([run-the-gates.md](run-the-gates.md)).
2. Run a one-URL local smoke through the new config
 ([troubleshoot-one-url.md](troubleshoot-one-url.md)).
3. Verify bounded worker selection against the day you plan to run.
4. Run a manual content refresh only after its measured worker population fits.
5. Read item-health failure codes, per-item read and write rates, the
 fingerprint row, the run manifest, the cache state and the published
 summaries.
6. Confirm no model directory or diagnostic payload is tracked.

---

## Block 3 - Revert

```json
"models_file": "models/<incumbent>.json"
```

The same line, back. With it go the three tokenizer readings and the two status
words - the dossier that said `superseded` says `incumbent` again - and that is
the whole revert.

**What a revert does not need, and why:**

| Not this | Because |
| --- | --- |
| A source edit | no model fact is in source. Everything about a model is in the file the pointer names |
| A schema regeneration | nothing changed shape. A pointer holds a different string |
| A cache purge | the incumbent's entry is keyed on its own weights file, revision and llama.cpp build, so moving the pointer back finds it again unless it has aged out. Deleting it buys a re-download and nothing else |
| A historical edit | published payloads and measurement rows record what actually ran. They stay as they are |

If a bad day is already running, stop the workers first, then move the line,
then let the next run fill the cache once without fanout and check its identity
and health before normal workers resume.

## See also

- [../reference/models.md](../reference/models.md) - one row a model, the status words, and what is in force right now.
- [fine-tune-a-model.md](fine-tune-a-model.md) - the corpus, the teacher, and what a base swap does to an adapter.
- [test-models-locally.md](test-models-locally.md) - download, serve and measure the local models.
- [troubleshoot-one-url.md](troubleshoot-one-url.md) - run one real URL through fetch, extraction and summarization.
- [run-the-gates.md](run-the-gates.md) - the complete local validation commands.
- [../concepts/evaluation.md](../concepts/evaluation.md) - the eleven gates, the model-choice arithmetic and the metric limits.
- [../concepts/config.md](../concepts/config.md) - model and runtime knobs.
- [../architecture/summarize/prompt.md](../architecture/summarize/prompt.md) - rendered bands, decoder rails and prompt controls.
- [../architecture/summarize/throughput.md](../architecture/summarize/throughput.md) - read/write rates and prompt reuse.
- [../architecture/contracts/determinism.md](../architecture/contracts/determinism.md) - the fingerprint contract.
- [../reference/measurements.md](../reference/measurements.md) - runner numbers and open measurements.
- [../../CLAUDE.md](../../CLAUDE.md) - Guardrails #2, #3, #6, #9, #10 and #11.
