# Judge two candidate models

**Last Updated**: 2026-09-15

Take two candidate summarizer models from "benched, with the harness lying to us" to "measured, qualified, written up, and adopted or rejected on the record" - and fix the measurement pipeline on the way, because most of this session was spent discovering it could not be trusted.

For the agent picking this up with no context. Read this top to bottom once before touching anything. Every claim here was checked on 2026-09-15; where something is an estimate it says so.

## Coverage index - every item this plan carries

So nothing raised in the session that produced this plan falls off the end.

| id | Item | Where it is dealt with | State |
| --- | --- | --- | --- |
| C1 | Sanitizer could not hold Gemma's one-sided turn markers | section 2 | shipped, `2cd717c5` |
| C2 | The bench's server case had never finished - missing `hashlib` import | section 2 | shipped, `6caa123e` |
| C3 | No measurement case fetched the draft head | section 2 | shipped, `5adf36c0` |
| C4 | Gemma's draft block named the wrong speculation type | section 2, task T1 | **shipped, #759.** The pinned build does accept `draft-mtp`; run `34971210901` recorded its `--spec-type` list and a test holds the contract against it |
| C5 | Bench Gemma and get a completed server case | task T1 | **done, with a finding.** Runs `34972996987` and `34973005911` both completed their work and both were refused by the bench's own input-drift guard. See T1 below |
| C6 | Write the model dossiers | task T2 | **shipped.** Both pages, plus the index row and the warning that a number on one may not be divided by a number on another |
| C7 | Markdown job summary for qualify and decide (owner approved "yes for D3") | task T3 | **shipped, #763** |
| C8 | Qualify persists no summary text and no title - quality cannot be judged | task T4 | **shipped, #764.** `samples-{shard}.json`, worst faithfulness first, its own artifact |
| C9 | **Fixing the measurement pipeline: qualify does not call what production calls** | task T5 | **shipped, #765 #769 #773.** All three steps |
| C10 | Telemetry from a measurement run should not ship - a `state/dev/` redirect | task T5, step 2 | **shipped, #769** as `run.trial_state_dirname`, a named directory rather than a fixed one |
| C11 | The CPU lottery - owner ruled to keep drawing | task T6 | **drawing.** Four solo runs dispatched on 2026-09-15: Gemma `35011547415`, Ornith `35011557915`, incumbent `35011568497`, Gemma `no_draft` `35011578538` |
| C12 | **Two real defects in `measure.yml`, one of them a Guardrail #10 failure** | task T7 | **shipped, #760.** The oracle found a third workflow, so six server starts assert the served alias where two did |
| C13 | Whether `measure.yml` and `validate.yml` should share their setup | task T8 | **shipped, #762.** The scratch-config block only, as the smallest first step |
| C14 | Merge the two ready pull requests | task T9 | shipped |
| C15 | `digest.yml` validates draft fields loosely | task T10 | **shipped, #761** |
| C16 | `model_unreachable` is a misleading failure code | task T10 | **shipped, #761** as `model_refused` |
| C17 | The owner's "old code" suspicion about item ids | section 7 | answered, no defect |
| C18 | Free memory has no value - record a peak, never a remainder | section 2, section 3 | owner ruled 2026-09-15 |
| C19 | The GitHub cache is GitHub's to manage, not ours | task T8 | owner ruled 2026-09-15 |
| C20 | **The bench refetches article text on every repeat, so any long run can be refused** | task T1, and it blocked T6 | **shipped, #778.** The agreeing repeats are timed and named; a `no_draft` case and a dispatchable repeat count came with it |

**Every row has landed except C11, and C11 is not code.** T6 is the one open item, and it is drawing: four solo runs are in flight and the finding is the distribution they land in.

## 0. What this project is, and the five minutes of reading you owe

yen-idhazh publishes a daily news digest. `backend/` is a Python producer that runs only in GitHub Actions and on a developer machine - it is never a service. `frontend/` is a static SvelteKit site. They meet only through committed data and generated contracts.

Read in this order and do not skip:

1. [`CLAUDE.md`](../CLAUDE.md) - the engineering contract. Sections 0a (non-goals), 0b (voice), 0c (how to ask the owner to decide), 0d (intent over limitation), 1 (the twelve guardrails), 6 (correction levels), 13 (test policy).
2. [`AGENTS.md`](../AGENTS.md) - the short pointer version.
3. [`docs/how-to/run-the-gates.md`](../docs/how-to/run-the-gates.md) - every gate command.
4. [`docs/how-to/evaluate-new-summarizer-model.md`](../docs/how-to/evaluate-new-summarizer-model.md) - the runbook this whole session was exercising. Blocks 1, 2 and 3: measure, adopt, revert.
5. [`docs/architecture/summarize/model-boundary.md`](../docs/architecture/summarize/model-boundary.md) - what a models entry declares, including the draft head.

Four things bite first: the runner budget (4 vCPU, 6 h a job, 10 GB cache), fetched web text is data and never instruction, an unmeasured number may not justify a design, and nothing may cost more as the repository grows.

## 1. Where the work is right now

**Start by making your own worktree. Do not adopt the one below.**

The work in this section shipped on a branch that is meant to be merged and deleted (task T9). By the time you read this it may already be gone, and a worktree pointing at a deleted branch is a trap that wastes an hour. It is recorded here so you can find the commits and read the diffs, not so you can work in it.

```powershell
$root = 'C:\Users\dev\gitrepos\yen-idhazh'
Set-Location $root
git worktree list                       # see what already exists; several siblings run at once
git fetch origin
git worktree add ..\yen-idhazh.worktrees\<short-name> -b <your-branch> origin/main
```

One branch per task in the list below, not one branch for the plan. Several of these tasks touch the same workflow files, so a single long-lived branch will collide with itself. [`docs/how-to/ship-a-pr.md`](../docs/how-to/ship-a-pr.md) has the transfer, pull request and cleanup steps.

### The branch this plan was written on

| Thing | Value |
| --- | --- |
| Worktree | `yen-idhazh.worktrees/p28-cands` |
| Branch | `feat/two-candidate-models` |
| Pull request | #737 |
| Commits | `2cd717c5` sanitizer, `6caa123e` the missing import, `5adf36c0` the draft head, plus this plan |

If #737 is already merged, read those commits on `main` and remove the stale worktree with `git worktree remove` from the shared checkout. If it is not merged, T9 says how.

Other open pull requests at the time of writing, none of them this thread's work: #753, #745, #730. **#736 (`docs/distil-plan-28`) is this thread's and is ready to merge.**

The shared checkout is at `yen-idhazh/`. **Do not edit it.** Code changes go in a dedicated worktree and named branch.

### Environment, and the traps

- Python is the shared venv: `yen-idhazh/.venv/Scripts/python.exe`.
- **Always set `$env:PYTHONPATH="<worktree>\backend"` before any direct `python -m idhazh.*` run.** Without it you silently import the shared checkout and measure the wrong tree.
- **The editor's `grep_search` and `file_search` tools read the SHARED checkout and will lie to you about a worktree.** Use `git grep` or `Select-String` with explicit paths.
- Multi-line commit messages go through a file: write it, normalise CRLF to LF, `git commit -F <file>`.
- Stage explicit paths. Never `git add .`.
- `pytest -q -n auto` redirected to a file can end with the warnings block and **no `N passed` line at all**. The exit code is the only summary. Capture `$LASTEXITCODE` immediately.
- Several sibling agents work in this repository at once. If a command's output looks like somebody else's work, it probably is. Compare `git rev-parse <a>^{tree}` against `<b>^{tree}` before concluding anything was lost.

### Gate commands

```powershell
$w = '<worktree path>'
Set-Location $w
$env:PYTHONPATH = "$w\backend"
$py = 'C:\Users\dev\gitrepos\yen-idhazh\.venv\Scripts\python.exe'

& $py -m ruff check .                    # ruff FORMAT is not a gate; only check
& $py -m mypy
& $py backend/utilities/doc_load.py      # run before and after any docs pass
& $py -m idhazh.contracts.export         # then git status on schemas/ and frontend/src/contracts
& $py -m pytest -q -p no:cacheprovider -n auto backend/tests
```

`backend/tests/workflows/test_ci_selection.py::test_ci_runs_the_gate_unlocked_and_the_same_workers_then_overlap` flakes on a saturated box - it asserts that concurrent subprocesses overlap in wall-clock, and a busy machine serialises them. Re-run it serially with `-n 0` before believing it.

## 2. What this session was doing, and why

The task was Block 1 of the model-evaluation runbook for two candidate summarizer models: write their config entries, bench them, and write up the findings. The incumbent is Qwen3.5-9B Q4_K_M and it is **still the adopted model** - `config/idhazh.json` was never changed and neither candidate has been adopted.

Along the way four real defects surfaced. Three are fixed and pushed. One is open.

### Fixed, commit `2cd717c5` - the sanitizer could not hold Gemma's turn markers

Gemma 4 spells a turn with a pipe on one side only: `<|turn>` opens, `<turn|>` closes. Neither matched the existing families, so `config/models/gemma-4-e4b-qat.json` was **refused at config load** by `refuse_markers_the_boundary_cannot_hold`. That refusal is the design working - a model whose turn markers the sanitizer cannot strip is a model an article could forge a turn against (Guardrail #11). Widened the pattern, moved `SANITIZER_VERSION` from `idhazh-sanitizer-2` to `-3`, added three tests, recorded the family in [`docs/architecture/sources/trust-boundary.md`](../docs/architecture/sources/trust-boundary.md).

### Fixed, commit `6caa123e` - the bench's server case had never once finished

`collect_digests` in the `runtime` job's inline program called `hashlib.sha256`, and the program imported ten modules but not `hashlib`. So the case started the server, summarized all five articles, then died on the collecting line about fifty minutes in. **Broken since the digest comparison landed in PR #42.** Every server-case bench since then burned a runner hour and threw the measurement away.

No gate could catch it: a heredoc is not imported, so ruff never reads it and mypy never sees it. Added [`backend/tests/workflows/test_inline_python_imports.py`](../backend/tests/workflows/test_inline_python_imports.py), which walks every inline program in every workflow and asks whether a name used as a standard-library module is imported. Removing the import turns it red and names `hashlib`.

### Fixed, commit `5adf36c0` - no measurement case fetched the draft head

A models entry may declare a `draft` block: a small second GGUF the server runs ahead of the target. `digest.yml` (production) always fetched it. The two bench cases, the budgets case and the qualification case never did - each downloaded exactly one file. Gemma is the first entry ever to declare one, so it started llama-server against a path that did not exist. The server exits during load, which surfaces as a health check that never passes rather than as a missing file.

All four cases now fetch and verify it. The cache key moved with it, and that half matters: both bench cases share one cache entry, so an entry keyed on the target alone is a complete-looking hit with the head missing - the fetch is skipped because the cache reported a hit, and the server fails at load anyway. The key is now the target's digest plus the head's where one is declared. **An entry with no head keeps the key it already had**, which is what stops this costing every other model a refetch; there is a test pinning exactly that.

### OPEN - Gemma's draft block names a speculation type that cannot run

With the head fetched, llama-server started and then failed every single request:

```
srv update_slots: decode() failed: failed to process speculative batch
```

Five of five articles, deterministic. Surfaced to the pipeline as `failure_code: model_unreachable`, because the summarize path maps an `HTTPError` to that code - which is itself misleading and is task T9.

**The cause is one wrong config value, and the publisher documents the right one.** `config/models/gemma-4-e4b-qat.json` declares the Gemma MTP head with `"spec_type": "draft-simple"`. Unsloth's own guide at <https://unsloth.ai/docs/models/mtp> gives the llama-server invocation for exactly this file:

```bash
./llama.cpp/llama-server \
    --model gemma-4-12B-it-qat-UD-Q4_K_XL.gguf \
    --model-draft mtp-gemma-4-12B-it.gguf \
    --spec-type draft-mtp --spec-draft-n-max 2
```

**The value is `draft-mtp`.** Not `draft-simple`, and not the `mtp` an engine advisor guessed at before the documentation was read.

The good news is how narrow the fix is. Our `server_argv` already passes `--spec-draft-model` and `--spec-type`, and the head **loaded successfully** - the log shows `common_speculative_init_result: loading draft model` completing and the GGUF opening. Only the decode failed. So the flag spellings build b10598 wants are already right, and the single wrong thing is the enum value.

That enum is `SpeculationType` in [`backend/idhazh/contracts/app_config.py`](../backend/idhazh/contracts/app_config.py) around line 74, and it is a closed choice on purpose:

> Only the two this project can actually stand up. `llama-server` accepts a longer list - eagle3, mtp, dflash, dspark and five ngram variants - and each of those either needs a purpose-built draft head we do not have or a lookup cache nothing here writes. A closed choice is what stops an operator naming one of them and getting a server that starts and drafts nothing.

That docstring did its job - it warned that naming an unsupported type gives you a server that starts and drafts nothing, which is precisely what happened. Its premise has now changed in one respect: **we do have a purpose-built MTP head.** Whether the pinned build can drive it is task T1.

Three facts from the publisher's guide that bear on whether this is worth doing at all, and which belong in whatever gets written up:

- The claimed speedup is **1.4x to 2.2x**, and the guide says it is "especially effective on GPUs" and that "gains are smaller on devices with lower memory bandwidth". We run on 4 CPU cores. Expect the low end or nothing.
- **MTP costs about 2 GB of extra memory, and that is not an argument against it.** The owner ruled on 2026-09-15: *"there is no price in having, saving, keeping free memory - it exists to be used, not maximising up to OOM is a crime - wastage of resources allocated and not used."* The runner has 16 GB whether we use one or fifteen, and memory left idle is bought and thrown away. The only thing that can go wrong is running out, which kills the job. So the question to ask of the 2 GB is never "can we afford it" - it is "does the peak plus 2 GB still fit". Ornith peaked at 9.33 GiB, so the answer today is yes with room to spare.
- `--spec-draft-n-max 2` is the recommended starting point and the guide says explicitly not to assume 2 is optimal - anything from 1 to 6 may win, and it is hardware-dependent. Our entry currently says `n_max: 3`.
- The guide's build instructions point at llama.cpp PR #22673. **Whether pinned build b10598 contains it is the one thing still unknown**, and T1 says how to settle it cheaply.

## 3. The only measurements that exist

**case one** is `llama-bench`: raw prefill and decode with nothing else running. **case two** is the real pipeline over a fixed five-article corpus through `llama-server`.

### case one, raw throughput

All at 4 threads, llama.cpp b10598 (`56db501e7`), 3 repeats, GitHub-hosted `ubuntu-latest`.

| Model | Prefill 730 | Prefill 1,800 | Prefill 4,850 | Decode 250 | CPU the runner gave it |
| --- | --- | --- | --- | --- | --- |
| Qwen3.5-9B Q4_K_M (incumbent, 2026-08-23) | 10.14 +/- 0.01 | 10.06 +/- 0.01 | 9.84 +/- 0.01 | 6.01 +/- 0.11 | EPYC 9V74 |
| Ornith 1.5-9B Q5_K_M (2026-09-14) | 6.23 +/- 0.00 | 6.19 +/- 0.00 | 6.12 +/- 0.00 | 4.41 +/- 0.03 | EPYC **7763** |
| Ornith 1.5-9B Q5_K_M (2026-09-15) | 6.20 +/- 0.004 | 6.17 +/- 0.002 | 6.08 +/- 0.001 | 4.54 +/- 0.01 | EPYC **7763** |
| Gemma 4 E4B QAT (2026-09-14) | 75.45 +/- 0.15 | 74.93 +/- 0.40 | 71.38 +/- 0.28 | 15.52 +/- 0.09 | EPYC 9V45 |
| Gemma 4 E4B QAT (2026-09-15) | 74.64 +/- 0.19 | 73.03 +/- 0.17 | 69.93 +/- 0.19 | 15.74 +/- 0.06 | EPYC 9V45 |

All tok/s. **Do not rank these models against each other.** Three models landed on three different processors. EPYC 7763 is a Zen 3 part with DDR4; the 9V74 and 9V45 are Zen 4 Azure parts with DDR5, and decode is memory-bandwidth bound, so the generation gap lands straight on the number you would want to compare. Section 5 has the ruling on what to do about it.

The two same-model repeats ARE fair, and they are the bench's repeatability: Gemma 15.52 against 15.74 (1.4 percent apart), Ornith 4.41 against 4.54 (2.9 percent apart). Both on the same CPU as their own earlier run. The bench is quiet on a fixed box.

Note `llama-bench` never loads a draft head, so **both Gemma case-1 numbers are already draft-free.** The MTP problem has never touched case one.

### case two, the five-article server run - ONE model has ever completed this

Ornith, run `34938565911`, 2026-09-15, EPYC 7763, 4 threads, 3 repeats. The bench emits a ready-to-paste dossier body; do not retype these.

| Reading | Value |
| --- | --- |
| Peak resident set, llama-server alone | 9.33 +/- 0.0006 GiB |
| Model load, cold (first start of the job) | 5,018 ms, n = 1 |
| Model load, warm | 5,001 +/- 0 ms, n = 2 |
| A summarize call, median | 452.61 +/- 1.09 s |
| A summarize call, longest | 921.95 +/- 9.24 s |

Seven and a half minutes for a median summarize call, and over fifteen for the longest. Whoever writes this up should say what that means for a real day's item count rather than just quoting the seconds.

**On the 9.33 GiB: report it, do not editorialise about it.** The owner's standing ruling is that free memory has no value - a runner has 16 GB whether a job touches one or fifteen, and the unused part was paid for and wasted. A model that uses more memory and goes faster is the better model. The only number that matters is the margin before an out-of-memory kill, because that ends the job and costs the whole run. So write "peak 9.33 GiB of 16 available" and move on; never write "only 6.7 GiB left" as though something were being spent.

Neither the incumbent nor Gemma has a completed case two. The incumbent's committed dossier [`docs/reference/models/qwen3.5-9b-q4km.md`](../docs/reference/models/qwen3.5-9b-q4km.md) predates the `hashlib` defect and carries case-1 numbers plus separately-sourced figures.

### The runs, for the record

| Run | Model | case one | case two | Why it ended that way |
| --- | --- | --- | --- | --- |
| 34901484508 | Ornith | success | failure | the `hashlib` defect, 51 minutes in |
| 34901487530 | Gemma | success | failure | refused at config load, the turn markers |
| 34905960781 | Gemma | success | failure | server would not start, draft head never downloaded |
| 34938565911 | Ornith | success | **success** | the first complete case two |
| 34941400155 | Gemma | success | failure | `failed to process speculative batch`, the MTP spec type |

Artifacts live on the runs at 90-day retention. `bench-raw` holds case one; `bench-server-baseline` holds case two including `dossier.md`. **None of this is in the repository.** `gh run download <id> -n <artifact> -D <dir>`.

## 4. What the owner ruled, and what is still open

Ruled this session, in the owner's own words where it matters:

- **A1 accepted**: teach the harness to fetch the draft head and put its digest in the cache key. Done, commit `5adf36c0`.
- **D3 accepted**: "yes for D3" - build a markdown job summary for both the qualify shards and the decide job. Not started. See task T3.
- **The CPU lottery: keep drawing.** *"i disagree with carmack - since we dont control the cpu lot, the only option we have is to keeping drawing and infer from the data."* The advisor's paired-bench recommendation is overruled. See task T6.
- **MTP: the publisher's own guide settles the flag.** The owner supplied <https://unsloth.ai/docs/models/mtp>, which gives `--spec-type draft-mtp` for exactly the file in our entry. This replaced an advisor's inference. See section 2 and task T1.

Still open and needing the owner:

- Whether to collapse `idhazh qualify` onto `idhazh work`'s call path (task T5). This is a Level 5 change - a persisted contract and the model pick. It needs a person's sign-off.
- Whether to build the composite action that would de-duplicate `measure.yml` and `validate.yml` (task T8). The two defects that review found are task T7 and need no ruling - fix them either way.

## 5. The advisor debate the owner asked for

Three persona advisors from `.github/agents/` were consulted on 2026-09-15 about the owner's objection: *"`idhazh qualify` and `idhazh work` are different - we have two code bases ... I find it annoying to have two, although nuances might be there, then we manage the delta not the whole."* They converged. Their reasoning is summarised here so the next agent does not have to re-run them.

### Fowler (architecture) - the duplication is real, and it is worse than duplication

**The bench harness is NOT a third implementation.** The `runtime` job's inline program in `measure.yml` is 373 lines, but it shells `python -m idhazh work` as a subprocess. It is a harness - server lifecycle, config mutation, a five-article assertion, digest collection. Today's `model_unreachable` on every article is production's own failure code raised honestly. **Leave it alone.**

The real fork is one function deep:

- `work` calls `_two_calls_one_item` (`backend/idhazh/stages/work.py`, around line 892, roughly 380 lines), which posts to the **completions** route under a grammar with a thinking span, **two calls an item**.
- `qualify` calls `common._one_call` (`backend/idhazh/stages/common.py`, around line 489, 47 lines), which posts to the **chat** route and lets the model's own template write the prompt, **one call**.

Fetch, extract, sanitize and tag are already one implementation in `common.py`. That part is healthy.

**The consequence is the point: `qualify` does not qualify the prompt production sends.** A model that passes the gate on the chat route can still fail in `work` on the grammar, on the label reply's schema, or on the window check. The duplication is not an annoyance - it is a hole in the gate. Even the recorded fingerprints disagree: `work.py` records `calls.prompt_inputs(..., turns=...)` and `qualify.py` records `summarize.prompt_inputs(...)`.

**Verdict: collapse, and it is not a taste argument.** It is the difference between measuring the model and measuring a model.

What must survive the collapse, and how:

| Nuance | Mechanism |
| --- | --- |
| Capture once, replay N (`_freeze`) | stays in `qualify`; never a `work` flag |
| Stratified corpus, `CorpusItem` hashes | stays in `qualify` |
| `work` writes `state/` ledgers, traces, evidence, `frontend/public/` assets | a **config knob**, not a flag. `STATE_ROOT` is `Final` off `REPO_ROOT` and nothing can move it today |
| `work` draws visuals; qualify must not | already free - the caller discards the decision |
| Repeats must not warm the cache | stays in `qualify`'s loop order |
| `finish_reason`, `reasoning_channel_used`, `repaired` | come from the returned `Summary` plus recorder cells; `_silent_recorder` in `work.py` is the seam |

Cost: roughly 300 lines moved and 50 deleted. Touches `qualification-shard.schema.json` - `prompt_tokens` and `completion_tokens` change meaning when one call becomes two, and the prompt digest changes, so **every committed shard's numbers stop being comparable**. Level 5.

His objections to his own recommendation, which you must carry forward: `_one_call` is also what the injection canaries use, and that is a reader-safety surface, so collapsing it is a separate decision. And `qualify`'s determinism gate asserts an identical digest across three repeats - the two-call path replays a model-written label into the second prompt, so one drifting label makes the whole item non-deterministic. **Expect the gate to get noisier.** That is a true finding about production rather than a reason to keep measuring something else, but it will cost a red gate first.

### Andre (evals) - qualify measures nothing about the writing

Confirmed by reading the contracts: `ItemObservation` records ok, failure code, finish reason, reasoning flags, schema validity, repaired, `output_digest`, word count, tokens, context fit and seconds. `ItemScore` records hhem, verbatim run, extractiveness, compression, lead coverage, unsupported numbers and densities.

**The summary text is never persisted. The title is never persisted, not even its length.** The text is hashed into a digest and scored into floats, then dropped. The frozen source articles ARE written to disk but never uploaded. The owner's read is correct: today's case is non-functional testing only.

`work` has the equivalent already - `_kept_call` sends each rendered prompt and raw reply to `backend/idhazh/capture.py` behind `logging.capture_prompts` and `capture_replies`, and `digest.yml` uploads the captures at 90-day retention, uncommitted.

**Verdict: yes, persist the summary and title.** Section 0a bans republishing article bodies *to a reader*; a qualification shard reaches no reader, which is the same argument the visual review tree already won. The non-goal that does apply is the *prompt*, which contains the body - so keep the prompt behind its flag, default off in qualify, and keep the summary and title on unconditionally. Our own summary is our output, not the publisher's text.

Where: `backend/var/qualification/<date>/shard-N/samples.json`, its own artifact at 30 days to match the shard. Never committed, never under `frontend/public/`, and **never merged into `QualificationReport`** - a gate must not learn to read it. Type every text field as the untrusted-line type the review queue already uses.

Six fields per item, and no more: `title`, `summary` (the writing under judgement), `source_url` (the only way to check a claim), `band_index` plus `truncated` (the same words are good or bad depending on whether this was a brief or a long read), and `hhem` plus `compression` (so a reviewer can find where the numbers and their eyes disagree, which is the entire reason to look). Sort by hhem ascending, worst first. No token counts and no finish reason - those are in the shard already.

On the merge, from eval design alone: **shared is more trustworthy.** Qualify measures a chat-route single-decode path production does not use, so the canaries and the injection gate assert against a decode shape the digest never runs. That gap is worse than the risk of a shared bug being invisible, which is answered by the canaries and by fixtures driving the path from outside.

His objections: a human reading summaries is a selector nobody logs, and somebody will sort by hhem, read ten and quietly re-run - which is corpus re-rolling by hand, and the frozen-corpus design exists to stop exactly that. And six fields is a taste panel with no rubric, no second rater and no agreement number; it will be cited as evidence and it is not.

### Carmack (runtime) - repeating the bench does not fix the CPU lottery

Inside one run, `llama-bench` at 3 repeats gives a spread of 0.6 percent of the value. Same CPU on a different day moves 1.4 percent. **A fixed box is quiet.** The three CPU names are not three draws from one distribution - they are a categorical factor with a few levels, and the Zen 3 / Zen 4 and DDR4 / DDR5 gap lands directly on decode.

Averaging over it estimates today's fleet mix, which is a number that changes when GitHub rotates hardware and tells nobody. Stabilising a fleet mean across three unknown-weight machine types would take roughly 10 to 20 runs per model - **an estimate, not a measurement** - and the answer expires on the next rotation.

**The thing actually wanted - is Gemma faster than Qwen - is a ratio the box cancels out of.** Guardrail #10 says this outright: an A-against-B on one box cancels the box. The runtime case already does this, running baseline and candidate in one job. The bench case does not: it takes one `candidate_models_file`.

| Option | Cost | What it gives up |
| --- | --- | --- |
| 2-3 more solo Ornith runs (what the owner asked for) | 2-3 bench jobs | still confounded, and likely three more machine types |
| **Paired bench: candidate and incumbent in ONE job, emit the ratio** | about a day of workflow work plus 2 jobs | absolute tok/s on "the" runner |
| 10-20 solo runs per model | 30-60 jobs | rots on the next fleet rotation |

He recommends the paired bench. One caveat he names: the weights cache key is one model's digest, so a two-model job needs a key covering both.

**The owner overruled this on 2026-09-15 and the ruling is what binds** - keep drawing solo runs and infer from the distribution. Task T6 carries the instruction and keeps his caveat next to it.

**On MTP, he is blunt and he is half right: no, MTP has not been tested.** What was tested is `draft-simple` with an MTP file in the slot, which is a configuration mismatch rather than an MTP run. Five of five identical deterministic failures is a proof, not a sample. **Three more runs would produce three copies of the same error.** That much stands.

**Where he was wrong is the spelling, and it matters.** He inferred the enum value would be `mtp`. The publisher's documentation, which the owner supplied afterwards, gives `--spec-type draft-mtp`. He also inferred the head could not be driven at all through this code path; in fact our `--spec-draft-model` and `--spec-type` flags are already the right ones for build b10598, the head loaded cleanly, and only the value passed to `--spec-type` was wrong. **This is the session's clearest lesson: an advisor reasoning from architecture produced a confident answer that was directionally right and specifically wrong, and one page of vendor documentation settled in a minute what the inference could not.** Read the publisher's page before theorising about the publisher's file.

His one genuinely cheap suggestion survives and is step 1 of task T1: unpack the pinned tarball and run `llama-server --help` to see whether `draft-mtp` is an accepted value in this build.

## 6. The task list

Ordered by what unblocks what. Each row says what done looks like.

### T1 - Teach the contract `draft-mtp`, then bench Gemma. UNBLOCKED.

The owner supplied the publisher's documentation and it settles what an earlier advisor could only guess at. Section 2 has the detail. The work is small and ordered, and step 1 decides whether steps 2 and 3 happen at all.

**Step 1, and do this first because it costs under a minute.** Fetch the pinned llama.cpp release - `LLAMA_CPP_BUILD` and `LLAMA_CPP_ASSET` in `.github/workflows/measure.yml` - unpack it, and run:

```bash
./llama-server --help | grep -A6 -- --spec-type
```

Record whether `draft-mtp` appears in the accepted values. The publisher's build instructions point at llama.cpp PR #22673, so a build predating it will not list `draft-mtp` and the honest answer is then to say so and price a build bump rather than guess.

**Step 2, if `draft-mtp` is accepted.** Add `DRAFT_MTP = "draft-mtp"` to `SpeculationType` in `backend/idhazh/contracts/app_config.py`, amend the docstring so it no longer says we have no purpose-built head, regenerate `schemas/models-config.schema.json` and `schemas/run-manifest.schema.json`, and version-stamp both with a `changelog` entry per CLAUDE.md section 11. Then set `"spec_type": "draft-mtp"` in `config/models/gemma-4-e4b-qat.json`.

While you are in that file, reconsider `n_max`. It currently says 3; the publisher recommends starting at 2 and says explicitly not to assume 2 is optimal, because the best value is hardware-dependent anywhere from 1 to 6. Do not sweep it blindly - one bench job per value is an hour each. Set it to 2, get one clean measurement, and only then argue about sweeping.

**Step 3, bench it twice.** One dispatch with the head, one with `draft: null`. That pair is the only honest way to say what the head is worth, and both runs land on whatever processor the runner gives them, so run them close together and record both CPU names.

Set expectations in whatever you write up. The publisher claims 1.4x to 2.2x, says it is especially effective on GPUs, and says gains are smaller where memory bandwidth is lower. We are on 4 CPU cores. It also costs about 2 GB of extra memory, which is a fact to record and not an objection - see the owner's ruling in section 2. Ornith peaked at 9.33 GiB of the 16 available, so the head fits.

Done when: the `--help` answer is recorded; and either Gemma has a completed server case with and without the head, or there is a written note saying the pinned build cannot do it and what a build bump would cost.

#### What happened, 2026-09-15

**Step 1 answered yes.** Build `b10598` lists eleven values for `--spec-type` and `draft-mtp` is one of them. The `--help` text was captured by a `workflow_dispatch` workflow that installs the same pinned asset the measuring cases install, run `34971210901`, and is committed at `tests/fixtures/runtime/b10598-llama-server-help.txt`. A test asserts that every member of `SpeculationType` appears in it, so moving the pin fails locally on a missing file rather than on a runner.

**Step 2 shipped** as #759. `spec_type` is `draft-mtp` and `n_max` is 2, as this row asked.

**Step 3 ran and cannot answer the question.** Both dispatches completed all five items in all three repeats. Both were then refused by the bench's own guard, and separately, GitHub put them on different processors.

| Case | Run | Processor, case two | A whole repeat, median |
| --- | --- | --- | --- |
| `draft-mtp`, `n_max` 2 | `34972996987` | AMD EPYC 7763 | 3,970 s |
| `draft: null` | `34973005911` | AMD EPYC 9V74 | 4,192 s |

The 5.3 percent between them is not the head. **The confound was measured rather than asserted**: the `llama-bench` case of both runs used the same weights on machines both reporting EPYC 7763, and its 250-token decode differed by 8.8 percent between the two - 9.676 against 10.532 tok/s. A 5.3 percent difference read across two runs sits under an 8.8 percent between-run spread, so the pair says nothing about the head. Both dossiers say so in those words.

**The instrument that could answer it** is a paired case: both configurations alternating inside one job on one machine, which cancels the machine. `measure.yml` already runs that shape through the `runtime_candidate` input, and it needs no second download because both cases open the same weights file. What stops it today is that `candidate_update` returns a patch applied to `summarize.inference`, and the draft head is a sibling of `inference` rather than a knob inside it. Lifting a `draft` key out of the patch in `write_config` is about six lines and changes no existing case.

Two things have to move with it. Three repeats of two cases is roughly 6.7 hours against a 330-minute job timeout, so a paired run needs a repeat count it can be told (Guardrail #2 - the limit is GitHub's, so the design is what gives). And the drift guard below has to stop failing the job.

#### C20 - the bench refetches article text on every repeat

**This is what refused both runs, and it will refuse most long ones.** `fixed_corpus` freezes the plan - which five addresses - and nothing freezes the text. Every repeat fetches the pages again, and `rejected_input_drift` fires when any article's text digest differs from repeat 1's. On both dispatches the same two of five articles were edited by their publishers inside the 3.3-hour window. For a news corpus that is ordinary rather than unlucky.

The guard's reason is sound: a timing difference must not be blamed on the model when a publisher moved the text. What is wrong is the consequence. **Failing the job throws away three complete repeats instead of reporting which of them are comparable** - and here repeats 2 and 3 agreed with each other exactly, in both runs, so a comparable pair existed and was discarded.

This is the same defect the qualification was designed against. `stage_qualify`'s own docstring names it: *"The old validation case replanned and refetched for every model it scored, so two numbers could differ because a publisher edited a page rather than because the weights differed."* The qualification freezes the fetched article and replays it. The bench does not.

**It blocked T6.** The owner ruled on 2026-09-15 to keep drawing bench runs and infer from the distribution. A harness that refuses a draw whenever a publisher edits a page cannot produce a distribution.

**Shipped as #778 on 2026-09-15, taking A3 below.** The largest set of repeats that read the same text is what gets timed; the rest are named in `problems` as `input_drift_dropped`; `repeats_timed` sits beside `repeats` so the dossier prints the denominator it had; and the run is refused only when a case has fewer than two agreeing repeats left. Output drift is now asked only across identical inputs, because asking it across drifted ones reported a newsroom's edit as the model being unstable. The same pull request added the `no_draft` case and made `runtime_repeats` dispatchable.

The four options are kept below because the one that shipped is not the one that is eventually right, and a later reader deserves to see what it traded.

| id | Option | Cost | What it gives up |
| --- | --- | --- | --- |
| A1 | Freeze the text: keep repeat 1's articles and replay them for repeats 2..N | The largest change - the bench has to hand the pipeline an article it already has, which is a capability `stage_work` does not expose today | Nothing about the measurement. It is what the qualification already does |
| A2 | Report the drift instead of failing: the verdict names the items whose text moved and the timing stands with that caveat attached | About ten lines. Output drift still fails, so a nondeterministic model is still caught | A weaker guard. A repeat that summarized different text sits in the same median as one that did not |
| A3 | **Shipped.** Time only the largest set of repeats that share one input, and fail only when fewer than two agree | About twenty lines. Keeps the guard's reason exactly and stops discarding good repeats | Nothing obvious, but it is new logic rather than removed logic, so it is the option most likely to be wrong in a way nobody notices |
| A4 | Leave it and re-dispatch until a run gets lucky | Nothing to write. Roughly one job in two is wasted, at 3.3 hours each | The owner's T6 ruling in practice, and it gets worse as repeats rise |

A3 keeps the guard's reason - never compare across different text - while ending the behaviour that throws away a finished run, and it is what makes T6 possible at all. **A1 is still the better answer eventually**, and it is a larger piece of work than this plan should absorb: it needs `stage_work` to accept an article it already has, which is a stage contract change rather than a workflow one.

### T2 - Write the dossiers for the models that have numbers

`docs/reference/models/` holds only `qwen3.5-9b-q4km.md` today. Ornith has a complete case two and needs `ornith-1.5-9b-q5km.md`; Gemma needs `gemma-4-e4b-qat.md` once T1 produces one.

The bench emits a `dossier.md` inside the `bench-server-baseline` artifact, written to be **pasted, not transcribed**. Download it, paste it, add the licence row and the qualification verdict if there is one.

Every number carries its hardware, date and spread (Guardrail #10), and the page must not rank the models against each other while they sit on different processors - say the processor next to the number and stop there.

Done when: both pages exist, `python backend/utilities/doc_load.py` is clean, and no page implies a cross-model ranking the measurements cannot support.

#### What happened, 2026-09-15

Both pages exist. Ornith's was pasted from the `dossier.md` in run `34938565911`'s artifact, as this row intended. **Gemma's could not be**, because the bench writes `dossier.md` after the verdict step and that step exited 1 - so Gemma's readings were recomputed from `runtime-summary.json` and `llm.json` in the artifacts of run `34972996987`, in the same shape and with the same spreads.

Neither page carries a licence row and neither carries a qualification verdict, and both say so under "What this page still owes". `models.md` gained both rows and one sentence that does the work this row asked for: a number on one dossier may not be divided by a number on another, because these three pages carry readings from at least two processor families.

### T3 - Build the qualify and decide markdown summaries. OWNER APPROVED ("yes for D3").

`validate.yml` writes nothing to `$GITHUB_STEP_SUMMARY` today. `measure.yml` does, twice, and the house pattern is exactly right: a step renders a `.md` file, then `cat file.md >> "$GITHUB_STEP_SUMMARY"`.

Build one renderer with two callers:

- **Per qualify shard**: which articles, how many calls, schema validity, determinism violations, latency spread, per-item scores.
- **In decide**: the eleven gates as a pass/fail table with measured against threshold. The gate objects already carry `measured`, `threshold` and `source` strings - the log dump is made of them, so the table is mostly free.

Nothing may be hardcoded per model. Every value comes out of the merged qualification payload, so swapping models changes the numbers and nothing else.

Done when: a dispatched `validate.yml` run shows both tables on the Actions run page, the renderer has unit tests driven by a built payload rather than a committed one (CLAUDE.md section 13), and no model name appears as a literal anywhere in the renderer.

### T4 - Persist the summary and the title for human reading. ANDRE'S DESIGN, section 5.

Follow his ruling exactly: `backend/var/qualification/<date>/shard-N/samples.json`, uploaded as its own artifact at 30 days, never committed, never merged into `QualificationReport`. Six fields per item, sorted worst-hhem first. Text typed as the untrusted-line type.

Carry his objection into the design: add whatever makes a re-run after reading visible, or say in the doc why it cannot be hidden.

Done when: a qualify shard uploads readable summaries and titles, a test proves the gate payload cannot reach them, and the trust-boundary page records the decision.

### T5 - Collapse qualify onto work's call path. LEVEL 5, NEEDS OWNER SIGN-OFF.

Do not start this without a ruling. When you do, use Fowler's strangler-fig order, which follows a precedent already in the tree (`qualify_canaries.py` was pulled out of `stage_qualify` the same way):

1. **Move `_two_calls_one_item` from `work.py` into `common.py`.** It already takes `tracer=None, recorder=None` and builds silent ones, so it has no shard dependency. `work.py` imports it back. Zero behaviour change, one import diff, trivially revertable. Ship this alone.
2. **Add the `state/dev/` redirect.** `qualify` cannot adopt the production call until the telemetry has somewhere disposable to land. `STATE_ROOT` is currently `Final` off `REPO_ROOT` and nothing can move it - that is the thing to change, as a config knob rather than a boolean flag.
3. **Only then** switch `qualify`'s call, as a one-line change worth arguing about on its own.

Expect the determinism gate to get noisier and do not treat that as a regression without checking whether it is a true finding about production.

Done when: whichever steps the owner approved have shipped, each as its own commit, with the schema version stamps and read-side migrations CLAUDE.md section 11 requires for step 3.

### T6 - Keep drawing runs and infer from the data. THE OWNER HAS RULED.

The engine advisor recommended a paired bench and argued that repeating solo runs estimates a fleet mix rather than a model. **The owner overruled him on 2026-09-15**, in these words: *"i disagree with carmack - since we dont control the cpu lot, the only option we have is to keeping drawing and infer from the data."*

That ruling stands and is not to be relitigated (CLAUDE.md section 0). The reasoning behind it is sound on its own terms: we do not control which processor a run lands on, we never will, and a distribution of draws is real information about what this project actually gets from GitHub. A paired bench answers a cleaner question but it is not the only thing worth knowing.

What to do:

1. Dispatch further solo bench runs for each candidate and for the incumbent. The owner asked specifically for "a couple more" for Ornith. Do not stop at a mean - **record every draw with its processor name**, because the distribution is the finding, not the average.
2. Report a **median** rather than a mean, since a small sample over a few machine types has no reason to be symmetric, and say how many draws each processor contributed.
3. Never print a cross-model comparison without the processor beside each number (Guardrail #10).

The advisor's objection is recorded here rather than acted on, because a later reader deserves it: a mean over three unknown-weight machine types moves when GitHub rotates hardware and tells nobody, so any fleet number this produces carries a date and expires. Write that sentence next to the number rather than dropping it.

The paired bench remains a good idea nobody has rejected - it is simply not what the owner asked for first. If it is ever picked up, the one thing to remember is that the weights cache key is one model's digest today, so a two-model job needs a key naming both.

#### Where this stands, 2026-09-15

**Unblocked and not started. It is the only row of this plan still open, and what it needs is a decision to spend runner time.**

The harness is ready. #778 stopped a publisher's edit refusing a finished run, so a draw now produces a reading instead of an exit code. Every draw already records its processor, so step 1's requirement is met by the artifact rather than by anybody remembering.

**One thing the ruling did not anticipate, and it is worth knowing before the next draw.** The two dispatches this session measured the between-run spread by accident: the same `llama-bench` decode test, the same weights, two machines both reporting EPYC 7763, differed by **8.8 percent**. So a solo draw is a reading of a machine as much as of a model, which is the advisor's objection with a number attached rather than a new argument. It does not overturn the ruling - the distribution is still real information - but it does set the bar a difference has to clear before it means anything, and any solo comparison under about 9 percent should be read as silence.

**The draft-head question is the one case where the paired shape is now cheap.** Both configurations open the same weights file, so there is no second download and the cache key problem above does not arise. `runtime_candidate=no_draft` runs it in one job. That is a different question from the fleet distribution the owner asked for, and it does not replace it.

What a draw costs: about 70 minutes a repeat on the machines measured so far, so a solo draw at 3 repeats is roughly 3.5 hours of one runner, and a paired draw at 2 repeats is roughly 4.5 hours.

Done when: each model has at least three recorded draws, the plan's measurement table carries every draw with its processor, and the write-up quotes a median with its sample size and date.

### T7 - Fix two defects the bench has today. UNBLOCKED, AND THE MOST VALUABLE SMALL THING HERE.

Found on 2026-09-15 by diffing `measure.yml` against `validate.yml`. They are independent of the structural question in T8 and should be fixed whatever is decided there - the architecture advisor was explicit that if only one thing gets done, it is these: twenty lines against two hundred.

| id | Defect | What it means |
| --- | --- | --- |
| D1 | `measure.yml` verifies the weights by SHA-256 only. `validate.yml` also checks the entry's declared `byte_count` | The stricter check already exists in the repository and one case does not use it |
| D2 | **`measure.yml`'s health check never asserts which model answered.** `validate.yml` polls `/v1/models` and asserts the served alias; `measure.yml` waits for a 200 and starts measuring | A bench can measure a server answering under a different alias and file the numbers under the candidate. That is a Guardrail #10 failure - the number would not be about the model it names |

D2 is the serious one, and it is exactly the class of bug the repository has been bitten by before. `backend/tests/workflows/test_model_server_jobs.py` carries the line "the case that drifted was the one nobody diffed - `validate.yml`". This time the drift runs the other way.

Done when: both cases verify the digest and the declared byte count, both assert the served alias before measuring, and a workflow test pins the parity so the next drift fails locally rather than on a runner.

### T8 - Decide whether `measure.yml` and `validate.yml` share their setup. NEEDS THE OWNER.

The owner asked: *"why do we need two pipelines `measure.yml` and `validate.yml` aren't they having purpose to exist separately or can be gated in the same that can be config driven?"*

The architecture advisor read both files on 2026-09-15 and answered: **they do not need to be two files for the reason you would expect, but merging them is the wrong fix.** Two things genuinely force them apart. `validate.yml` carries `concurrency: group: validate` at workflow level - push that down to job level and the eight-shard matrix serialises against itself; leave it where it is inside a merged file and every bench dispatch queues behind a qualification run. And size: the two are 1,411 and 446 lines, and [`TODO/20260914-27-pipeline-observability-plan.md`](20260914-27-pipeline-observability-plan.md) already rejected extending `measure.yml` on length grounds.

His recommendation is a **composite action** rather than a reusable workflow, because a reusable workflow replaces whole jobs and cannot inject steps into `qualify`, which must fan out by shard and then run gates. A composite action injects steps into an existing job, which is the shape needed. It would hold: resolving the candidate from its models file, the weights cache and llama.cpp fetch, the digest verification, the scratch config copy, and the health check. Roughly 200 lines removed, one new `.github/actions/llama-candidate/action.yml`, correction level 3. No dispatch URL or documentation reference changes, because both files keep their names and inputs.

One of his findings is **not** a reason to act, and the owner said so directly on 2026-09-15: *"gh cache is not in our control they maintain it."* He observed that the two workflows keep two separate multi-gigabyte cache entries for identical bytes under different key prefixes. GitHub evicts by least-recently-used on its own schedule; nothing here prunes a cache and nothing needs to. **The only real cost of an extra entry is that an eviction makes the next run re-download, and that cost is measured rather than guessed: 316 s for 6.19 GiB.** Say it in download seconds if it ever needs saying, never as a ceiling somebody must manage.

His objection to his own recommendation, recorded so it is not lost: the drift is already partly caught by a test, so extraction buys less than it looks, and a composite action is a third file a reader must open.

Smallest first step if the owner says yes: extract only the scratch-config block, which is already byte-identical between the two files, so the extraction cannot change behaviour. It ships alone, reverts alone, and proves the mechanism.

Done when: the owner has ruled, and if the answer is yes, the scratch-config extraction has shipped on its own.

### T9 - Merge what is ready

#736 (`docs/distil-plan-28`) and #737 (`feat/two-candidate-models`) are both MERGEABLE.

Re-check mergeability between merges - a stale CLEAN is how a bad merge lands. `gh pr merge --squash --delete-branch` often exits 1 from inside a worktree *while having merged*; read `gh pr view <n> --json state,mergedAt` rather than trusting the exit code. Remove the worktree before merging so the branch delete does not fail.

### T10 - The smaller things this session found and did not fix

- **`digest.yml` validates draft fields loosely.** It uses `if value and value.split() != [value]`, which lets an entry declare a draft head with a missing digest and then download it unchecked. The two bench workflows now refuse that. Production has the looser check. One-line fix, its own commit.
- **`model_unreachable` is a misleading failure code** for a server that answered with an error. It maps from `HTTPError`. Worth splitting so a decode failure does not read as a network failure.
- **A2 from the old plan is unfinished**: the write-up of bench findings. T2 is most of it.

## 7. Things that will waste your time if you do not know them

- **The run the owner linked earlier, `33016222069`, is from 2026-08-26 and is three weeks stale.** Its numeric item ids are not evidence of stale code. Item ids come from one place, `item_id()` in `backend/idhazh/rank.py`, and are `{vertical}-{16 Crockford base32 symbols}` over the first 10 bytes of the URL key. Today's runs mint them correctly - `ai-540ngas5kkqtjcq9` appears in the 2026-09-15 Gemma log. The contract pattern accepts both shapes deliberately, so days published under the old one still load.
- **That run's `decide` failed on two gates**, and they are worth knowing because they will come back: `injection_canaries` at 4 of 5, failing `exfiltration-via-url`; and `brief_copying_ceiling` with a longest verbatim run of 1.000 against a ceiling of 0.5. `decide` does not block on its own - it prints `ESCALATE` and exits 2 so a person rules. That run also logged `the gates wrote no ledger row` and `could not push the validation ledger after three attempts`, so it left no record in `state/`.
- **`qualify (0)` and `qualify (1)` are shards of one corpus, not different tests.** The `plan` job emits `matrix=[0,1,2]` and `shards` is a dispatch input, default 3, max 8. Each shard freezes `corpus_per_shard` articles and replays them `repeats` times. `fail-fast: false`, so one bad shard does not cancel its siblings; each uploads `qualification-{shard}` and `decide` merges them.
- **The bench dossier is meant to be pasted.** Do not retype numbers out of a log.
- **`--ref` is what lets a candidate be benched before it is merged**: `gh workflow run measure.yml --ref <branch> -f target=bench -f candidate_models_file='models/<name>.json'`.

## See also

- [`CLAUDE.md`](../CLAUDE.md) - the contract.
- [`docs/how-to/evaluate-new-summarizer-model.md`](../docs/how-to/evaluate-new-summarizer-model.md) - the runbook, with a flowchart of Block 1.
- [`docs/architecture/summarize/model-boundary.md`](../docs/architecture/summarize/model-boundary.md) - the models entry, the draft head, and which cases fetch it.
- [`docs/architecture/sources/trust-boundary.md`](../docs/architecture/sources/trust-boundary.md) - the turn-marker families the sanitizer strips.
- [`docs/concepts/evaluation.md`](../docs/concepts/evaluation.md) - what may and may not grade a summary.
- <https://unsloth.ai/docs/models/mtp> - the publisher's guide to running an MTP head under llama.cpp. It names `--spec-type draft-mtp`, the `--spec-draft-n-max` starting point, the memory cost and the build the flag needs. Read it before theorising about task T1.
