# Fine-tune a summarizer

**Last Updated**: 2026-08-29

How the training corpus is built, what maintains it, and what a person does with
it. Training itself does not happen here: the runner has no GPU, 4 vCPU and a
6-hour job ceiling, so a training step in a workflow is a project-level non-goal
(`CLAUDE.md` section 0a). Using a fine-tuned model is not - it enters through the
same qualification as any other candidate.

## What exists today

| Piece | Where | Who runs it |
| --- | --- | --- |
| The row shape | `backend/idhazh/contracts/corpus.py` | nothing; it is a contract |
| The window's census and schedule state | `corpus/corpus.meta.json` | written by the harvest and the prune |
| The harvest and the roll | `backend/idhazh/corpus.py` | a step in the digest run |
| The four operator verbs | `backend/utilities/data_wrangler.py` | a person, on demand |
| The history prune | `.github/workflows/prune.yml` | a schedule |

## The corpus

`corpus/corpus.jsonl` is a rolling window of `finetune.corpus_rows` training
samples, one JSON object per line. Every line is one article's exchange, and no
line holds two articles.

```json
{"messages":[{"role":"system","content":"..."},{"role":"user","content":"..."},{"role":"assistant","content":"{\"title\": ...}"}],"url_key":"3f1a9c...","date":"2026-08-27","model_id":"qwen3-5-9b-q4-k-m","vertical":"energy","version":"2026-08-28"}
```

**It trains on its own.** No sidecar, no lookup, no join. `messages` is the
OpenAI chat format, which TRL, Unsloth, Axolotl and LLaMA-Factory all read with
no converter, and `datasets.load_dataset("json", data_files="corpus/corpus.jsonl")`
loads it directly. The extra columns are metadata every one of those loaders
ignores.

That is why the system prompt is written inline on every row rather than
referenced. Measured 2026-08-27 against `state/scores.csv` on `origin/main`
(2,459 scored rows over 6 days) and the 114 published items of that day: a row is
11.5 KB raw and 2.9 KB compressed, and repeating the prompt costs 1.95 MB raw per
500 rows but only 98 KB once git compresses it. Portability is worth 98 KB.

### The five columns, and the three that were cut

| Column | Why it is on the row |
| --- | --- |
| `messages` | The training column. The only one a trainer reads |
| `url_key` | Deduplication, and the holdout is a set of these |
| `date` | Drives the roll's eviction and the date-based holdout split |
| `model_id` | A distilled corpus mixes rows from two teachers |
| `vertical` | The one taxonomy field present on every item, so the only one a quota can act on |

`prompt_fingerprint` was cut because it is `sha256(messages[0])`.
`source_words` was cut because it is `len(messages[1].split())`. `written_by` was
cut because which file a row lives in already says whether a person wrote it - a
stored copy of a derivable value is a second thing that can disagree with the
first.

### The assistant turn is the published output, re-validated

Not the model's raw reply. It is rebuilt through `summarize.draft_model`, the
same shape the constrained decoder is held to, and dumped in that model's field
order - `title`, `summary`, `key_points`. Field order is decode order under a
grammar, so a target written in sorted order would teach a sequence the decoder
is not allowed to emit.

A row is dropped, never degraded, when the summary has no title, when the item
was not scored, or when it fails one of the deterministic counterweights below.

### What never selects a row

`hhem`, the faithfulness score. It is the alarm this project reads a run by, and
a corpus filtered on it trains a model against its own monitor - after which the
monitor is measuring something it helped shape. The filter uses only the measures
a model cannot improve by copying: `hedge_dropped`, `unsupported_numbers`,
`coverage`, `extractiveness`, `compression`, `extraction_suspect` and
`determinism_violation`.

## The three verbs

| Verb | Who | When |
| --- | --- | --- |
| Harvest | CI, a step in the digest run | every `finetune.harvest_every_days` |
| Roll | CI, the same step, the same commit | the same moment |
| Prune | CI, `prune.yml`, wired to nothing | every `finetune.prune_every_days` |

### The harvest runs inside the digest job, and it has to

It reads the article the scorer actually read, and the only place that text
exists is the machine that just read it. `backend/var/run/<date>/items/` is
gitignored and leaves the runner as a one-day artifact, so a scheduled workflow
of its own would check out a fresh tree, find an empty directory and harvest
nothing - silently, every week, until somebody went looking.

The body can be obtained a second way, from the address rather than from the
artifact, and that is what `refill` below does. It is not an option for the
scheduled step: it costs a network round trip per item, and it returns whatever
the page serves now rather than what the scorer read.

It is still a stage that runs alone with a file in and a file out
(`CLAUDE.md` section 4):

```bash
python -m idhazh harvest --date 2026-08-28            # respects the cadence
python -m idhazh harvest --date 2026-08-28 --force    # harvest now
```

### The cadence is a number, not a cron line

`finetune.harvest_every_days` defaults to 7. Changing it to 35 is one edit and
nothing else moves.

It cannot be cron, and that is mechanical rather than a preference. GitHub
Actions takes standard 5-field cron, which has no every-N-days field: `0 8 */7 * *`
fires on the 1st, 8th, 15th, 22nd and 29th and then again on the 1st, a 3-day gap
in a 31-day month. Above 31 it cannot be written at all. The harder fact, which
covers the prune too: **`on.schedule` is parsed before any step runs, so no value
in `config/` can ever reach it.** Any config-driven cadence is a due-check in a
step, and a due-check needs durable state - which is what `harvested_date` and
`pruned_date` in `corpus/corpus.meta.json` are.

A missed day therefore self-corrects on the next wake, and the answer does not
depend on which clock the job read.

### The roll

`finetune.corpus_rows` in, oldest out. Three properties, each one a way the naive
version loses data:

- **Oldest-first eviction** pairs with a date-trailing holdout, so a held-out row
  is by definition among the newest and can never be evicted while it is still
  held out. Without that pairing the window would quietly shrink the test set
  every week, and a comparison would run on fewer articles each month with
  nothing anywhere saying so.
- **An article already in the window keeps its original row.** A re-run of a day
  would otherwise rewrite every row it touched, and a corpus that changes when
  nothing changed cannot be reviewed by diff.
- **Order is by date then address**, never by arrival, so two runs that harvest
  the same items in a different order write the same file.

### The prune rewrites history, and that costs something

`prune.yml` wakes daily, reads `pruned_date` out of a shallow checkout, and on 29
days out of 30 exits without doing anything. When
`finetune.prune_every_days` have passed it takes a full clone, squashes every
commit older than `finetune.prune_keep_days`, stamps the meta file and
force-pushes `main`.

**This is the only force-push in the repository** and the single exception
`CLAUDE.md` section 8 carries. It exists because the corpus commits article text
and git history is append-only: deleting a row from the window does not delete
its bytes, so the only way to bound the repository is to rewrite the range those
bytes are in. Left alone the history grows about 2.96 MB per harvest commit,
which is 154 MB a year at `harvest_every_days: 7`.

What it costs, said rather than implied:

- A squash boundary is per-commit, not per-path. The range it collapses carries
  `backend/`, `docs/` and `state/` as well as `corpus/`.
- `git blame` and `git bisect` reach back `prune_keep_days` to
  `prune_keep_days + prune_every_days` and no further. At the committed 60 and 30
  that is 60 to 90 days.
- A commit SHA older than the boundary stops resolving, so a link to one dies.
- A clone taken before a prune has to be re-fetched.

Owner decision, 2026-08-28, taken over the alternative of keeping the corpus on a
branch nobody works from.

**No data is lost, only deltas.** `git checkout --orphan` at the boundary
produces a root commit holding a complete copy of the tree, and the tip holds
another - so two whole datasets are always recoverable and no `keep_generations`
knob is needed.

At 30 and 60 the history holds 9 to 13 weekly harvests: 25 MB to 38 MB, flat
forever. Set both to 90 for "prune quarterly, keep a quarter"; the mechanism does
not change.

## Looking at the corpus

`backend/utilities/data_wrangler.py` has six verbs and no seventh. Routine data
movement is deliberately not among them: the harvest and the roll run on a
schedule where a failure has an alarm on it, and a local utility has none.
`backfill` and `refill` are not routine - they are replays a person runs
deliberately, through the scheduled harvest's own function.

```bash
python backend/utilities/data_wrangler.py stats
python backend/utilities/data_wrangler.py split --holdout-days 14
python backend/utilities/data_wrangler.py verify
python backend/utilities/data_wrangler.py verify --tokens
python backend/utilities/data_wrangler.py backfill --items-dir <dir>
python backend/utilities/data_wrangler.py refill --limit 200
python backend/utilities/data_wrangler.py remove --url-key <sha256> --yes
```

`backfill` and `refill` both exist to stop a corpus starting empty and filling at
one run a week. They differ in where the article body comes from, and that is the
only way they differ:

| | `backfill` | `refill` |
| --- | --- | --- |
| body comes from | a downloaded `items-*` artifact | re-fetching the source address |
| reaches back | as far as artifact retention (7 days) | every day the repository remembers |
| body is | the exact text the scorer read | whatever the page serves today |
| network | none | one round trip per item |

- **`backfill`** replays a finished run's item payloads through the same harvest
  the schedule runs - same function, same bytes, and a test asserts a backfilled
  row equals a harvested one.

  ```bash
  gh run download <run-id> --repo miztiik/yen-idhazh --pattern 'items-*' --dir /tmp/items
  python backend/utilities/data_wrangler.py backfill --items-dir /tmp/items
  ```

  Repeat per run; the roll deduplicates by `url_key`, so replaying the same run
  twice is harmless. Rows are dated by their own eval row, so one session can
  replay several days and each row still lands on the day it was produced.

  **How far back it reaches is set by `items-*` artifact retention, which is
  seven days.** Measured 2026-08-29: one run's four shards are 555,842 bytes, so
  a week of five runs a day is 18.6 MB against the 500 MB Rule #2 allows.
- **`refill`** reaches everything older than that, because the committed ledger
  and the committed digest hold between them every half of a training row except
  the article body - and the body has an address. `state/scores.csv` names the
  canonical URL, the model and the fingerprint; the day payload under
  `frontend/public/digest/` holds the title, the summary and the key points.

  ```bash
  python backend/utilities/data_wrangler.py refill --limit 0    # the plan, no network
  python backend/utilities/data_wrangler.py refill --limit 200  # then do 200 of them
  ```

  With no `--limit` it queues however many rows the window still has room for.
  `--limit 0` fetches nothing and prints the plan, which is how to read what a
  session would cost before spending it.

  **Three checks are what make re-fetching safe**, and none of them is a
  guess:

  1. **The join is proved, not assumed.** `output_digest` is taken over exactly
     the title, the summary and the key points, so a published item is paired
     with a ledger row only when it recomputes to the value that row recorded. A
     later run that re-summarized the same article is dropped rather than
     mismatched. Measured 2026-08-29 over the 2,791 committed ledger rows: 89 of
     them are exactly this case.
  2. **Nothing about the page is reconstructed.** The body goes through the same
     extractor a run uses, so `brief`, the source form and the length band are
     computed from the bytes that came back. This is what a rebuild from an
     expired `evidence-*` artifact could not do: `EvidenceItem` carries no
     `brief`, and reconstructing it from the two recoverable terms disagrees with
     the recorded value on 3 of 229 items (measured 2026-08-29) - a guessed
     length band, which is the failure this corpus exists to prevent.
  3. **Every counterweight is measured again** against the body that came back,
     never read off the ledger. An article edited past its summary now fails the
     same gate a live run applies, so it is dropped instead of taught.

  An address that has moved, gone behind a paywall or started refusing robots is
  dropped and counted by failure code. Re-running picks up whatever is still
  missing, so a long fill can be done in chunks, and the window is committed
  every 25 items so an interruption costs at most the last few fetches rather
  than the whole run.

  **What one full fill cost, measured 2026-08-29** on the 2,791-row committed
  ledger, at 1.36 s per address:

  | | |
  | --- | --- |
  | queued after the four skip rules | 1,768 |
  | bodies re-fetched | 1,729 (97.8 percent) |
  | dropped, page gone or paywalled | 39 |
  | dropped by re-measurement against the new body | 43 |
  | rows before / after | 166 / 1,852 |
  | wall clock | 26 minutes |

  The 43 are the safety argument paying for itself: pairs the original run
  passed, whose article no longer supports the published summary.

  **Size, measured on the same 1,852 rows.** 19.2 MB raw, 10,851 bytes a row;
  4.3 MB once git compresses it, 2,444 bytes a row, a 4.4x ratio. The compressed
  figure is the one that matters, because it is what each commit that rewrites
  the window adds to history, and it is what `finetune.prune_every_days` bounds.
- **`stats`** prints the row count against the window, the date range, the word
  and target spreads, the counts per vertical and per model, how many rows a
  session would really draw, and a warning when the live prompt no longer matches
  the digest the window was harvested under. Run it before spending a session:
  the two ways a session is wasted are training on 400 rows while believing there
  were 4000, and training on rows the prompt has moved out from under.
- **`split`** writes `corpus/holdout.txt`, by date and never at random.
  Production always runs on tomorrow's news; a random split puts the same story
  from three feeds on both sides of the line and reports memorisation as success.
  Only `url_key` values are written, so no article text leaves the window.
- **`verify`** checks the escaping rule of the format offline: one physical line
  per row, every line loading, no CRLF, a final newline, no duplicate address,
  and the file re-serializing to the bytes it already holds.
- **`verify --tokens`** additionally measures tokens per row against
  `finetune.sequence_length`, using the tokenizer named by
  `models.<role>.hf_base_repo`. With `refill` it is one of the **two commands
  here that reach the network**, which is why both are operator tools and not
  tests (Rule #7).
- **`remove`** prints what it would delete and stops. `--yes` does it, and it
  refuses either way to take the window below `finetune.min_rows`, saying how far
  below it would land.

## The reference set

`finetune.reference_rows` ideal summaries, written by a person in their editor
with whatever expert model they have, committed as fixtures under
`tests/fixtures/reference/`. They are primarily **training targets**: a corpus
made only of our own accepted output can copy our own model's habits, including
its mistakes, and the hand-written rows are what that is corrected against.
`finetune.reference_test_rows` of them are held back and read line by line by a
person, because a test reference nobody read is not a reference.

`backend/utilities/reference_set.py` has two verbs and writes no summaries:

```bash
python backend/utilities/reference_set.py queue          # sample the articles
python backend/utilities/reference_set.py check          # refuse what a run would refuse
python backend/utilities/reference_set.py check --write  # emit reference.jsonl
```

- **`queue`** samples articles out of the committed corpus, stratified on the two
  things the prompt branches on - the word-count band and the source form - plus
  vertical, the one diversity column that is fully populated. It is deterministic
  and it extends rather than replaces, so running it again after the corpus rolls
  tops the queue up instead of discarding an afternoon of authoring. The test
  slice is a proportional share of every stratum, not the tail: measured
  2026-08-29 over 500 rows, the 100 held back span all five bands (10, 36, 37,
  12, 5) and all five verticals.
- **`check`** holds each answer to the two rails production uses - the shape the
  constrained decoder is allowed to emit, and the word range the row's own system
  turn asked for - then refuses a `url_key` on both sides of the train/test line,
  and refuses an article the training window also holds.

**The queue never carries the system prompt.** It carries the band, and `check`
re-renders the prompt from it when it builds the row. That is the same
identity-by-construction rule the corpus follows: a copy of the prompt on 500
lines is 1.9 MB and can outlive a prompt edit, where a band cannot.

**One article gets one target.** The reference set and the training window must
share no `url_key`. Left overlapping, the notebook concatenates both files and
trains one article twice against two different answers - ours and the better one.
`check` fails on the overlap and prints the `data_wrangler.py remove` command
that resolves it.

The authoring session has its own brief:
[`TODO/20260829-reference-set-handover.md`](../../TODO/20260829-reference-set-handover.md).

## The knobs

All in the `finetune` block of `config/idhazh.json`.

| Knob | Default | What it costs |
| --- | --- | --- |
| `teacher` | `summarize` | a key in `models`, never a model name |
| `student` | `route` | a key in `models` |
| `corpus_rows` | 2000 | storage and history: 2.9 KB compressed per row |
| `train_rows` | 1000 | GPU hours. A **ceiling**, not a demand |
| `min_rows` | 500 | nothing trains below it, and a repair refuses to cut past it |
| `harvest_every_days` | 7 | one commit each time it fires |
| `prune_every_days` | 30 | one force-push each time it fires |
| `prune_keep_days` | 60 | storage, and how far `git blame` reaches |
| `holdout_days` | 14 | rows that never train |
| `reference_rows` | 500 | human hours, once. About 2 min a drafted row |
| `reference_test_rows` | 100 | human hours, once. About 5 min a read row |
| `epochs` | 2 | GPU hours |
| `sequence_length` | 4096 | free-tier memory, quadratically in attention |

`train_rows` and `corpus_rows` are two knobs because they price differently: the
window costs storage, the sample costs wall-clock. Window 2000 with sample 1000
is strictly better than window 1000 with sample 1000 - the same training time,
twice the pool to sample a diverse 1000 from, at 154 MB of history a year instead
of 77 MB.

**Where 1000 came from, plainly.** It is derived, not measured, and from one
constraint only: a free T4 session has to finish. Estimated 1.8 h for 1000 rows
over 2 epochs. No training job has run here yet, so the figure gets corrected the
first time one does (Rule #10).

`hf_base_repo` sits on the `models` entry and not in `finetune`, because training
reads the safetensors repository while the pipeline reads the GGUF one. Held in
two blocks a model swap moves one string and leaves the other, and a LoRA adapter
loads onto a mismatched base without raising - so the damage would arrive later
as a quality drop nobody could attribute.

**The committed `hf_base_repo` values are unverified.** `Qwen/Qwen3.5-9B` is the
expected upstream for an `unsloth/*-GGUF` repository; nobody has confirmed it
exists or that its architecture matches. The first cell of any training notebook
resolves it and must stop loudly if it does not.

## Training a model

[`../../notebooks/finetune.ipynb`](../../notebooks/finetune.ipynb) trains a LoRA
adapter on the corpus above. Open it in Colab, set the runtime to a GPU, and run
all. It clones this repository, reads `config/idhazh.json`, and resolves
`finetune.teacher` to a base - **no model is named in it**, so a config swap
moves the notebook with it.

Four things it refuses to train on, and each one raises rather than warns:

| Refused | Why a warning would not be enough |
| --- | --- |
| The corpus holdout | Held out by date, so the model trains on the past and is measured on the future. Training on it produces a model that measures well and is worthless. |
| The reference set's test slice | The one honest measurement of the work. `reference.jsonl` carries no slice, so the notebook joins `queue.jsonl` on `url_key` to recover it. |
| A row whose assistant turn carries an injection marker | That turn is our own model's output on a stranger's web page. If an attack ever landed, the row teaches the tuned model the injected behaviour. |
| A row longer than `finetune.sequence_length` | Dropped and counted. A truncated target teaches the model to stop mid-summary. |

**The cell that matters most asserts the loss mask before a step runs.** The
median article is about six times the length of its summary, so training on the
whole sequence puts most of the gradient into learning to write other people's
news articles. The notebook builds the mask by length, decodes the span it will
learn from, and stops if that span is not the assistant turn's JSON.

**The merge and the quantise happen on your machine, not in Colab.** Merging
loads the whole model at 16-bit and wants about 16 GB of ordinary RAM against
the free tier's 12, so training would succeed and the save would die. The last
cell gives the `llama-export-lora` and `llama-quantize` commands.

`backend/tests/test_notebooks.py` holds the notebook's gates - that it parses,
that it names no model, that a leak raises, and that the mask is asserted. None
of it runs the notebook; that needs a GPU and a network.

## What is not built yet

The weights upload, the second scorer and the blind read. They are rows 7
through 10 of [`../../TODO/20260827-summarizer-fine-tuning-plan.md`](../../TODO/20260827-summarizer-fine-tuning-plan.md).
Adopting a tuned model is a Level-5 change and needs explicit approval
(`CLAUDE.md` section 6).

## See also

- [`../../CLAUDE.md`](../../CLAUDE.md) - section 0a for the corpus carve-out, section 8 for the force-push exception.
- [`../concepts/config.md`](../concepts/config.md) - the tunable surface.
- [`../concepts/evaluation.md`](../concepts/evaluation.md) - what the counterweights measure and why the faithfulness score may only veto.
- [`run-the-gates.md`](run-the-gates.md) - the commands behind the Definition of Done.
