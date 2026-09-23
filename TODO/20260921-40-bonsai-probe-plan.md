# Two calls against a 27B ternary model, and what the machine did

**Last Updated**: 2026-09-21

**Level**: 4 (a new model entry, a new runtime, a workflow that grows a fan-out, and a decision about what a test run keeps - reverting after a dispatch costs more than writing it)

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 3 rows in flight - the entry, the workflow and the telemetry are the three lanes - refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

## Section 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | A 27B model packed at under two bits a weight would be three times the incumbent's parameters inside a similar memory footprint, which is the only way a model that size reaches a four-processor machine with no graphics card. Nobody knows whether it works here: the publisher's own figures are all from graphics cards and Apple hardware, and there is no published throughput figure for an ordinary x86 processor at any packing. It also cannot run on the build this project pins, because the packing needs a transform that is not in the upstream runtime yet. The question is narrow - point it at named articles, read the summaries, and read what the machine did - and the machinery to answer it already exists in three places that have never been pointed at one job. |
| Hard scope - in | A model entry for the 27B at the two-bit packing, naming its own runtime; a dispatch input that takes named addresses instead of drawing from a fixed list; one plan job so a fan-out agrees on what it is summarising; the fan-out itself, which the work and record stages already support; the eight telemetry steps the nightly run already takes, lifted into the test workflow; a trial state root so nothing lands in the production ledgers; a committed collection holding the summary each article produced, so a model's writing can be read again months later against another model's; one dispatch, and the readings written up. |
| Hard scope - out | See the table below. |
| ESCALATE triggers | (1) Row #1: if the model's turn markers are not recognised by any pattern family the sanitizer already carries, stop. Adding a family moves the trust boundary (Guardrail #11), which is a person's decision taken on its own. (2) Row #1: if the declared context window cannot be set small enough for the weights to fit the runner's memory, stop and report the arithmetic rather than reducing how much of an article is read - article length and candidate counts are not this plan's to trade. (3) Row #6 adds a committed collection, so it needs a prune rule before its first file lands (Guardrail #12) - pause for sign-off on the path and the retention window before the commit step is written. (4) Any row that would raise a runner budget figure (Guardrail #2). (5) If a dispatch exceeds the job timeout, the next move is a smaller fan-out or a smaller window, reported with what it traded. |
| Chosen strategy | Extend the existing two-article test workflow rather than writing a new one, because it already performs the real fetch, the real extraction, the real two calls and the real server start, and publishes nothing. Carmack rules the runtime and the fit, Andre rules the entry's prompt surface, Fowler rules the contracts. Owner ruling 2026-09-21. |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 3.` Three, because the dependency chain leaves at most three rows ready at once. |

### Hard scope - out

| What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- |
| Any work on a developer machine | The first reading waits for a dispatch rather than an afternoon | Nothing. Owner ruling 2026-09-21: this runs in continuous integration only |
| Adopting the model | The nightly run keeps the incumbent whatever this says | A verdict, which is the qualification workflow's job and not this plan's. This plan produces readings, not a decision |
| The three-case comparison the test workflow runs today | The visual-plan decode and the two-slot case are not measured against this model | They stay dispatchable, unchanged, at the default fan-out of one. Measuring them against a new model is a second dispatch |
| Comparing this model against the incumbent on throughput | No number here says which is faster | Prefill speed spans more than four times between machines this project runs on, so a fan-out reports the machines it drew, not one model against another. A comparison needs both models on one machine, which is a separate dispatch of the sequential path |
| Lowering how much of an article is read, or how many articles run | Nothing - it is not a cost, it is a refusal | Nothing in this plan. If the window will not fit, the window moves or the packing moves |

### What is already built, and is not to be rebuilt

| Capability | Where it lives |
| --- | --- |
| Building a configuration that differs from production in one line | `.github/actions/candidate-config/action.yml` |
| Cache, fetch, digest check, server start, health and alias check | `.github/actions/model-server/action.yml` |
| Splitting a plan across workers, by position | `shard_of` in `backend/idhazh/stages/common.py`, used by the work, record and qualify stages |
| A plan built from named addresses | `plan` in `backend/utilities/pipeline_draw.py`, which already accepts addresses, feeds and an execution id |
| The processor, core count and memory of the machine | `idhazh fingerprint --job work` |
| What the model server and the Python process each held | `.github/scripts/sample-rss.sh` and the whole-job peak under the control group |
| Prefill and decode speed per call | `idhazh record`, which derives them onto the item health row |
| Keeping a test run out of the production ledgers | `run.trial_state_dirname`, which redirects every state collection at `backend/idhazh/cli.py:519` |

### The arithmetic this plan starts from

| Reading | Value | Provenance |
| --- | --- | --- |
| Weights at the two-bit packing | 7.21 GB | The publisher's model card, read 2026-09-21 |
| Weights at the one-bit packing | 5.95 GB | The same card, which names it the choice wherever memory is tightest |
| The card's own memory table for a 27B at two bits | about 8.1 GiB at a 32,768-token window, about 13.7 GiB at 100,000 | The same card. Text only, weights plus key-value cache plus overhead |
| The machine | four processors, 16 GB, no graphics card | Guardrail #2. This is the machine, not a line to stay under |
| What the incumbent's server actually peaks at | to be read from the committed item health ledger as row #1's first task | Not quoted here: a figure pasted from memory is an estimate wearing a measurement's clothes (Guardrail #10) |
| Throughput on an ordinary x86 processor | unmeasured, at any packing | The card publishes graphics-card and Apple figures only. This is the reading the plan exists to take |
| What a failed two-address dispatch costs | 40 to 50 minutes | Owner estimate 2026-09-21, and the reason the two-bit packing is tried first rather than argued about. It is cheap enough that measuring beats predicting |

## Section 1 - Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The model entry, and whether it fits | - | A | PENDING | - | - | - |
| 2 | The test workflow takes named addresses | - | A | PENDING | - | - | - |
| 3 | One plan job, so a fan-out agrees what it is reading | 2 | B | PENDING | - | - | - |
| 4 | The fan-out | 3 | C | PENDING | - | - | - |
| 5 | The eight telemetry steps move across | - | A | PENDING | - | - | - |
| 6 | A trial state root, and what the run keeps | - | A | PENDING | - | - | - |
| 7 | One dispatch, and the readings written up | 1,4,5,6 | D | PENDING | - | - | - |

**Depends-on outside this plan:** two things come first. Row #1 here needs the model file as a plain mapping, so a new entry needs no typed field - merged as #1036 - and it needs the generated contract layer gone, which **landed on 2026-09-23 as #1086**: `schemas/` and `frontend/src/contracts/` are deleted, and four tests under `backend/tests/contracts/` hold the frontend's hand copies against their models. Both are satisfied. **Row #1 here also absorbs the installer resolving a build the model names**, which was the last unbuilt piece of the scaffolding plan closed on 2026-09-23. That is a generic interface - any model file may name a build - and this plan is only the first file to use it; it owes one guard, stated in row #1 decision 6. Rows #4 and #5 here needed the workflow row that deletes the closed-world tests refusing a new job that stands a model server up, which merged as #1037. Nothing in this plan starts before all of those are `DONE`.

## Section 2 - Row #1 - The model entry, and whether it fits

- **Scope:** A model entry for the 27B at the two-bit packing, naming its own runtime, its own turn envelope and a context window the machine can hold - and the installer change that lets a named runtime resolve, absorbed from plan 39 row 5.
- **Files touched:**
  - `config/models/bonsai-2-27b-pq2.json` (new)
  - `.github/scripts/llama-cpp-pin.sh`, `.github/scripts/fetch-model-runtime.sh` (the installer resolves a release from whatever repository it is handed, defaulting to the repository-wide pin)
  - the qualification gate, for the build-identity refusal in decision 6
  - `docs/reference/ci-model-runtime.md`
- **Acceptance gates:** local - `python -m pytest backend/tests/contracts -q`, and `python -c "from idhazh import config; config.load('config')"` against a pointer set to the new file; CI - full suite. ESCALATE triggers 1 and 2 apply.
- **Oracle:** the entry loads through `idhazh.config.load`, which runs the marker check against the sanitizer's pattern families, and the architecture the entry declares equals the architecture in the weights' own header. **And the release address the installer resolves is byte-identical to today's for every model that names no runtime, and is the fork's address for the one that does** - both arms assert a string and download nothing. All three are answerable without the model server. What it cannot settle: whether the summaries are any good, or how fast it decodes - those need row #7.
- **Tasks, in order:**
  1. Read the incumbent's peak server memory from the committed item health ledger, so the fit arithmetic starts from a measurement rather than a recollection.
  2. Pin the weights: repository, revision, file, digest and byte count, taken from the published file rather than from the card's prose.
  3. Read the architecture string out of the weights' own header and declare it.
  4. Record the turn envelope from the weights' own chat template, and check every marker against the sanitizer's families before writing the entry. A marker no family recognises is ESCALATE trigger 1.
  5. Set the context window from the card's memory table and step 1's reading, leaving headroom for the Python process on the same machine.
  6. Name the runtime: the fork's repository, release tag, asset and digest. Make the installer read those four from the entry's `<role>.runtime` block through the environment, never as a pasted argument (Guardrail #11), and fall back to the repository-wide pin when the block is absent - which is every model today.
  7. Set the sampling values the card publishes for this model, and the answer budget for a model that reasons before it answers.
  8. Add the build-identity refusal in decision 6 before any dispatch runs.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | The two-bit packing ships first. A two-address dispatch costs 40 to 50 minutes to fail, which is cheaper than the argument about whether it will. If it does not fit or does not run, the one-bit packing is a second entry file and a second dispatch, not a redesign | Owner ruling 2026-09-21 |
 | 2 | The context window is what moves to make the weights fit, never the article truncation cap or the number of articles | Owner ruling 2026-09-20, restated here because this is where the pressure lands |
 | 3 | The entry names its own runtime rather than moving the repository-wide pin. Production keeps the build it ships, so nothing this plan measures can change what the nightly run decodes on | Carmack |
 | 4 | Every number this entry records is about the fork's build, and the write-up says so. A reading taken on a binary production does not ship is a reading about that binary | Carmack, Guardrail #10 |
 | 5 | This model reasons before it answers and its lowest reasoning setting is unsupported, so the entry declares a thinking envelope and a separate thinking budget. `config/models/qwen3.5-9b-q4km-thinking.json` is the template, not the plain entry | Andre |
 | 6 | **A per-model build opens a hole this row closes in the same change.** A fork binary loads a stock model file happily, and `validate.yml` job `qualify` decides publication, so a verdict could be measured on one binary and reported under another (Guardrail #10). The refusal is one assertion in the gate that publishes: **a qualification whose recorded build is not the build the qualified model entry declares** does not produce a verdict, and `UNRECORDED_BUILD` is refused outright. Not "not the repository pin" - that would pass a stock binary qualifying a model that declared a fork. `backend/idhazh/fingerprint.py:103` already records the build, so the reading exists | Carmack and Fowler, agreed 2026-09-21 |
 | 7 | The repository-wide pin stays the default, so every current model resolves exactly the release it resolves today. **The interface is generic, not a fork special case**: any model file may name a build, and this plan is only the first file to use it | Carmack |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Ship both packings as two entries in one row | Doubles the download and the dispatch before anything is known about either | One extra entry file and one extra dispatch. Take it if the first dispatch is inconclusive rather than failed | Carmack |
 | 2 | Keep the incumbent's declared context window | The card's own table puts a 27B at two bits near 13.7 GiB at a large window, against 16 GB shared with the Python process. The projected peak does not fit | Nothing to take - it is arithmetic, and row #1 task 1 re-checks it against a real reading | Carmack |
 | 3 | Run it on the pinned upstream build | That build refuses this packing outright, and silently produces unusable text for the neighbouring one | Nothing to take. It is why the fork exists | Carmack |
 | 4 | A second pin file for the fork | Two files holding a build with nothing tying either to the model that needs it, and a fork binary loads an ordinary model file happily - a green run measured on a binary production does not ship | About 10 lines, and drift | Carmack |

## Section 3 - Row #2 - The test workflow takes named addresses

- **Scope:** An optional dispatch input naming the addresses to summarise, which bypasses the fixed-list draw, and the one lookup that refuses an address the configuration does not already carry.
- **Files touched:**
  - `.github/workflows/idhazh-pipeline-tests.yaml` (the inputs block, and the step that draws from the fixed list)
  - `backend/utilities/pipeline_draw.py` (the headline lookup in `plan`)
  - `backend/tests/workflows/test_pipeline_tests_workflow.py`
  - `docs/how-to/run-the-gates.md`
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows -q`, and `pipeline_draw.py plan` run against two addresses absent from `config/pipeline-tests.json`; CI - full suite.
- **Oracle:** `plan` builds a valid run plan from two addresses that appear nowhere in `config/pipeline-tests.json`, and with the input empty the workflow draws exactly what it draws today. The first arm fails on the base tree, which is the defect the row exists for. What it cannot settle: whether the named addresses are fetchable - a dead address degrades that item and records why, which is the pipeline's existing behaviour.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | The input is optional and empty means today's behaviour, byte for byte. The workflow keeps serving its existing purpose | Fowler |
 | 2 | The headline comes from the fetched page when the configuration does not name one, rather than refusing. A title is a convenience for the plan, not a fact the plan depends on | Fowler |
 | 3 | Addresses are data and never reach a shell argument, a file path or an outbound fetch URL unvalidated. Item identity is recomputed from the canonicalised address, as it already is (Guardrail #11) | Andre |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Add the addresses to `config/pipeline-tests.json` | Turns every probe into a committed configuration change, and grows a file that exists to hold a stable draw | About 8 lines a dispatch, forever | Fowler |
 | 2 | A separate utility for named addresses | `plan` already does this. A second entry point is a second thing to keep in step | About 60 lines and a second path to test | Fowler |

## Section 4 - Row #3 - One plan job, so a fan-out agrees what it is reading

- **Scope:** Move the planning step into a job of its own that uploads the plan, so every worker in a fan-out reads one plan rather than building its own.
- **Files touched:**
  - `.github/workflows/idhazh-pipeline-tests.yaml`
  - `backend/tests/workflows/test_pipeline_tests_workflow.py`
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows -q`; CI - full suite.
- **Oracle:** every worker in a dispatch reads a plan whose item order is identical, proved by the plan's digest being the same in every worker's log. This matters because the split is by position: two workers disagreeing on order would overlap on some articles and drop others, silently. What it cannot settle: whether the plan is the right one - that is row #2's question.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | The plan is built once and uploaded, matching the nightly run and the qualification workflow. Planning per worker is what makes a position-based split unsafe | Fowler |
 | 2 | At a fan-out of one this changes nothing observable, so it lands before the fan-out rather than with it | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Let each worker plan, and sort the result | A sort makes the orders agree only while the sort key is stable across workers. The upload makes them the same bytes | About 3 lines, and a failure mode that appears only under a fan-out and only sometimes | Fowler |

## Section 5 - Row #4 - The fan-out

- **Scope:** A worker count input and a matrix, with the work and record stages given their worker number, so a dispatch can carry more than a handful of articles.
- **Files touched:**
  - `.github/workflows/idhazh-pipeline-tests.yaml`
  - `.github/scripts/run-pipeline-test-case.sh`
  - `backend/tests/workflows/test_shard_fan_out.py`
  - `backend/tests/workflows/test_pipeline_tests_workflow.py`
  - `docs/reference/github-actions.md`
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows -q`; CI - full suite. ESCALATE trigger 5 applies.
- **Oracle:** the union of the articles the workers take is the whole plan, and no article is taken twice - asserted over the split function for a range of worker counts against a fixture plan, not against a dispatch. What it cannot settle: whether the workers finish inside the job bound; that is row #7's reading, and the bound is the thing that fails first.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | The default is one worker, so the three-case comparison this workflow already serves is unchanged | Fowler |
 | 2 | The workflow's file header says the fan-out is for a probe over many addresses, not for the case comparison. Cases compared across workers are cases compared across machines, and prefill speed spans more than four times between the machines this project draws | Carmack |
 | 3 | The worker count is a dispatch input rather than derived from `run.shard_size`. A probe names what it wants; the nightly run derives it because nobody is watching | Carmack |
 | 4 | Each worker records its own machine, so a reading is always attributable. The item health row already carries the worker number and the processor | Carmack |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | A new workflow shaped like the nightly run, minus publication | About 250 lines, and a second workflow answering a question this one already answers | The 250 lines, plus rows in whichever closed-world workflow tests survive plan 39 | Fowler |
 | 2 | Derive the worker count from configuration | Hides the fan-out from the person dispatching it, who is the only one who knows how many addresses they named | About 10 lines, and a probe whose width is decided somewhere else | Carmack |
 | 3 | Keep the job bound as the literal it is today | The nightly run derives its per-worker bound from configuration; this one does not. Going wide is what makes the difference bite | About 6 lines to wire. Worth taking if row #7 finds the bound is the limit | Carmack |

## Section 6 - Row #5 - The eight telemetry steps move across

- **Scope:** Lift the nightly run's measurement steps into the test workflow so a dispatch reports what the machine, the model server and each call actually did.
- **Files touched:**
  - `.github/workflows/idhazh-pipeline-tests.yaml`
  - `backend/tests/workflows/test_pipeline_tests_workflow.py`
  - `backend/tests/workflows/test_telemetry_cli.py`
  - `docs/architecture/sources/item-health.md`
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows -q`; CI - full suite.
- **Oracle:** after a dispatch, every one of the five readings the probe exists to take is present and non-null in the uploaded artifacts - the machine's processor and memory, the server's peak memory, the Python process's peak memory, prefill speed per call and decode speed per call. What it cannot settle: whether the readings are right; they are the same instruments the nightly run uses, and this row moves them rather than changing them.
- **The eight steps, and what each answers:**

 | Step | Reading |
 | --- | --- |
 | `idhazh fingerprint --job work`, before the server starts | The machine: processor model, core count, memory |
 | The runner census: processor line, core count, the server's own start-up report, binary and weights digests | What actually ran |
 | `sample-rss.sh` against the server's process id | The server's peak memory, sampled, and the Python process's alongside it |
 | The control group's peak | What the whole job held at once |
 | The server's counters, scraped at job end | Prompt tokens and prompt seconds, from the server itself |
 | `idhazh job-clock` against the server log and those counters | The run's clock reconciled against the server's own |
 | `idhazh record` | Prefill and decode speed per call, onto the item health row |
 | The runtime log artifact | All of the above, off the machine |

- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | The steps are lifted as they are. A second implementation of a measurement is a second answer to the same question | Carmack |
 | 2 | The machine fingerprint runs before the server starts, as it does in the nightly run, so its probe sees an idle machine | Carmack |
 | 3 | The entry proof runs too. This workflow does not run it today, and a wrongly declared turn envelope degrades every summary with nothing going red - which is the single most likely failure for a model nobody here has run | Andre |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Read the timings out of the server log alone | The log carries the server's view; the item health row carries the call's, including what the prefix cache served, which is what makes a speed figure mean anything | About 30 lines saved, and a prefill figure with the wrong denominator | Carmack |
 | 2 | Take only the three readings the owner named | The other five are already written and cost one step each, and the memory peak is what decides whether the packing was the right one | Nothing to take - the cost is near zero and the readings answer the fallback question | Carmack |

## Section 7 - Row #6 - A trial state root, and the summaries the run keeps

- **Scope:** Point the dispatch's state at a trial root of its own, and commit the summary each article produced into a state collection of its own so a model's writing can be read and compared without downloading an artifact.
- **Files touched:**
  - `.github/workflows/idhazh-pipeline-tests.yaml`
  - `.github/actions/candidate-config/action.yml` (if the trial name is not already reachable from the dispatch)
  - `backend/idhazh/ledger.py` (the path function for the new collection)
  - `backend/idhazh/stages/record.py` (the write)
  - `backend/idhazh/contracts/knobs/retention.py` (its window)
  - `.github/scripts/commit-and-push.sh` call site in the workflow
  - `backend/tests/workflows/test_staged_paths.py`
  - `backend/tests/workflows/test_validation_state_root.py`
  - `docs/reference/repository-layout.md`
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows backend/tests -k 'state or ledger or record' -q`; CI - full suite. ESCALATE trigger 3 applies: pause for sign-off on the path and the prune window before the first commit step is written.
- **Oracle:** a dispatch writes nothing outside its trial root, and the summary file for each planned article exists at the declared path with the article's own identifier in its name - both asserted against the staged-path check, which already refuses a path outside the root. What it cannot settle: whether the summary is any good; a person reads it, which is the point of committing it.
- **The path, and why:** the trial redirect already exists at `backend/idhazh/cli.py:519` and moves every state collection under a named directory. That directory is named for the model, so a summaries collection on the day tree every other collection uses lands at `state/<model id>/summaries/<YYYY>/<MM>/<DD>/<item id>.json`. One file an article, named by the identity the pipeline already computes, so two models summarising the same article produce two trees a person can read side by side and compare with an ordinary diff.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | The trial root is the existing redirect, named for the model the dispatch is testing, not a new tree with a new contract | Fowler |
 | 2 | The summary is committed, not left as an artifact. An artifact expires and has to be downloaded; the point of this probe is to read what a model wrote and to be able to read it again next month against a different model | Owner ruling 2026-09-21 |
 | 3 | One file an article, on the day tree, rather than one file a day holding every article. A day file makes two runs of the same day collide on one path; a file an article makes a re-run replace exactly what it re-summarised | Fowler |
 | 4 | The collection is written only when a trial root is set. The nightly run leaves it unset, so production never grows this tree - a condition read from configuration, not a name checked in code | Fowler, Guardrail #6 |
 | 5 | It gets a retention window on the line that declares it, because a committed collection with no prune rule is a repository that grows on a schedule (Guardrail #12) | Fowler |
 | 6 | The contract is the summary payload the pipeline already produces. No new shape is invented for this | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Keep per-item output as an artifact only | Cheapest, and it is what the workflow does today. It loses the thing the owner asked for: reading one model's writing against another's, months apart, without keeping artifacts alive | Nothing to take - it is the current behaviour | Fowler |
 | 2 | Commit the whole run directory - article, health, evaluation and visual decision beside the summary | The article text is the largest payload and is already fetchable from its address; the health and evaluation rows already land in their own ledgers | Several times the bytes for readings that are already recorded elsewhere | Fowler |
 | 3 | Write to the production state root | One mistaken dispatch puts trial rows in the ledger the console draws | Nothing to take. The redirect already exists | Fowler |
 | 4 | A day file holding every article's summary | Two dispatches on one day rewrite each other, and the file is the unit a merge conflicts on | About the same effort, and a collision that appears only when two probes run on one day | Fowler |

## Section 8 - Row #7 - One dispatch, and the readings written up

- **Scope:** Dispatch the workflow against named addresses with the new entry, and record what came back as a benchmark page of its own.
- **Files touched:**
  - `docs/reference/benchmarks/<the page this run creates>.md` (new)
  - `docs/reference/ci-model-runtime.md`
  - `TODO/STATUS.md`
- **Acceptance gates:** the dispatch itself; then the documentation load check before and after, and the split test on any page a section was added to. No application suite is required for a documentation-only closure. ESCALATE trigger 5 applies if the dispatch exceeds its bound.
- **Oracle:** the write-up answers all five questions the plan was opened for, each with the instrument that produced it and the date, and a reader can tell from the page which binary and which packing produced every number. What it cannot settle: whether the model should be adopted. That is the qualification workflow's verdict, and this page is an input to it, never a substitute.
- **The page records, at minimum:**

 | Reading | Unit |
 | --- | --- |
 | The machine | processor model, core count, memory |
 | The model server's peak memory, and the Python process's | bytes, and the two together against the machine's total |
 | Prefill speed | tokens a second, per call, with the count of tokens the prefix cache served named alongside |
 | Decode speed | tokens a second, per call |
 | Time an article | seconds, and what share went to reasoning |
 | The summaries | read and judged by a person, not scored |
 | The binary | the fork's build, named as not being the one production ships |

- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | The run gets its own page under the benchmark directory, named for what it measured. A re-run replaces that page rather than adding a second one | Fowler |
 | 2 | Every figure carries its hardware, its date and its spread, and says what it means next to itself (Guardrail #10, CLAUDE.md section 0b) | Fowler |
 | 3 | If the two-bit packing fails to load or fails the memory arithmetic, the fallback is a second entry at the one-bit packing and a second dispatch. That is a named cheap step costing 40 to 50 minutes, not a scope change | Owner ruling 2026-09-21 |
 | 4 | If the model produces usable summaries but too slowly for the nightly budget, that is a finding and not a failure. The page says what window, what fan-out and what article count would fit, and hands the decision back | Carmack |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Fold the readings into the existing runtime page | A benchmark run gets its own record, and a re-run replaces it. Folding it in means the page grows a section per run | Nothing to take; it is the documentation rule | Fowler |
 | 2 | Run the qualification workflow instead, for a verdict | Ninety model calls and ten gates to answer a question two calls answer, against a model nobody has yet seen produce a sentence | The dispatch cost, and a verdict on a model whose basic viability is unknown. Take it after this page says the model runs | Andre |
 | 3 | Dispatch before row #5 lands | The summaries would arrive with no measurement beside them, which is half the question | Nothing saved - the telemetry row is independent and runs in parallel | Carmack |
