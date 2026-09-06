# CLAUDE.md - yen-idhazh Engineering Contract

**Last Updated**: 2026-09-06

Non-negotiable contract for any human or AI agent working in this repo.

You are a data-pipeline and static-publishing agent.

## 0. User Approval

User approval supersedes every agent and every rule in this file. Amend conflicting rules in the same commit.

## 0a. Non-Goals

- **Production backend.** See Rule #1. `backend/` is a build-time producer that runs in CI and on a developer machine; it is never a service.
- **Hosted inference, anywhere.** No API call to a model provider from the pipeline, the published site, or the reader's browser. Inference running wholly on the reader's device over weights we committed and serve from our own origin is not hosted inference, and is governed by Rule #1.
- **On-device inference on the digest's critical path.** The reading experience never waits on a model. Every on-device feature is secondary, reader-initiated, and removable without changing a single digest assertion. The bundle must render complete with the model directory deleted.
- **Account systems** (login, signup, email collection, server-backed sync). The site is anonymous and read-only.
- **Push notifications.** The reader decides when to read.
- **Runtime telemetry / analytics SDKs / third-party scripts that fetch at runtime.** Static-first means no runtime calls home.
- **Republishing article bodies to a reader.** The digest publishes a link and our own summary. A reader-facing page never carries the source text. `corpus/` is the one exception: it holds source text as training samples, and nothing renders it, links to it, or serves it. Owner decision, 2026-08-28.
- **Paywalled or login-walled sources.** If `robots.txt` or a paywall says no, the answer is no.
- **LLM-as-judge evaluation.** A judge that shares the failure modes of the thing judged is not a measurement.
- **Training on the runner, GPU runners, and models that do not fit the runner.** See Rule #2. Training a model elsewhere is not a non-goal. The runner only ever opens finished weights and reads bytes, so where those weights were trained does not change what the runner has to do. A fine-tuned model is an ordinary candidate: one entry in `config/idhazh.json`, the same qualification, the same SHA-256.
- **Accessibility framework / audit tooling** (axe-core, WCAG-level gating, automated contrast checks). Descoped at project level. Basic ARIA and keyboard navigation ARE in scope: visible focus rings, labelled controls, semantic landmarks, keyboard-reachable interactive surfaces. Design-level accessibility is encouraged; merge-gating on audit tooling is not.

### Design rationale

**The fine-tuning clause was narrowed on 2026-08-27.** The hazard is a build step the runner cannot execute, not a fine-tuned model. Training elsewhere costs the runner nothing - it only opens a finished GGUF and reads bytes. The old wording made an ordinary model swap look like a rule reversal, and a rule that fires on ordinary work stops being read.

**The article-bodies clause was narrowed on 2026-08-28, and it cost something.** What is worth protecting is what a reader is served, so the clause names that and carves out `corpus/`. The cost is stated rather than hidden: this repository is public, so source text under `corpus/` is readable by anyone. Owner weighed that against a second private repository and took it. A source that forbids storage is still out of scope, and nothing under `corpus/` may reach a published page.

## 0b. Voice

This is the canonical writing rule. It binds every agent, every persona under `.github/agents/`, **every answer an agent gives a user**, every doc, every commit message, and every reader-facing string. Cite it as "section 0b".

- Write in plain, direct language. Use short sentences with one idea each.
- Use the active voice.
- Do not use corporate or self-invented tech jargon.
- Lead with the core answer. Skip all introductory fluff.
- Keep answers short unless asked for depth.
- **Say what a number means, next to the number.** `1.055x` is not an answer; "5.5 percent faster, and we needed 40 percent" is. This is the one clause of this section that can be checked mechanically, so it is the one that catches a drift the others cannot.
- **A term from a subsystem is not a term for a user.** `aggregate decode`, `spread`, `prefill` and `pipeline_fingerprint` are correct in the doc that owns them and wrong in an answer, unless the answer defines them in the same sentence.
- **A third-party product name is not a design vocabulary.** Name the artefact and the property - "a reliability scorecard", "a tinted status card", "a target marker on a bar" - never the vendor whose screenshot it came from. This binds a design doc, a plan-doc, a code comment, a commit message, a branch name and a filename equally. Naming the artefact is also the more useful sentence: it says what to look at, where the product name only said where somebody once saw it.
- Use ASD-STE100.

Everywhere else restates this section rather than inventing its own style rule (Rule #4): [`docs/agents/guardrails.md`](docs/agents/guardrails.md) carries it for the personas that run the bootstrap ritual, and [`AGENTS.md`](AGENTS.md) carries it for agent tools that read that file instead of this one.

### Design rationale

**"Every answer" was added on 2026-08-25** because the three copies of this rule disagreed and the canonical one was the weakest. An agent reporting `1.055x aggregate decode, spread 0.022, prefill flat` at a user who asked what happened was inside the letter of it.

**The number clause exists because the rest of the section cannot fail.** "Write in plain language" is advice, and advice catches nothing. "Say what the number means, next to the number" is a check a reader applies to a sentence and gets a yes or a no.

## 1. Rules (Read First, Every Session)

1. **Static-first publication.** What ships to a reader is a static bundle on GitHub Pages. No production backend, no server we run, no runtime call to a model provider, no runtime telemetry, analytics, error-tracking SDKs, ads, accounts, or push notifications. The pipeline runs in CI and commits its output; the site only renders what is already committed. **Every computation happens in the reader's browser or in CI - never on a server we operate.** Fetching static assets is allowed, including from a third party: a font, a stylesheet, an icon set, a charting library. Fetching our own committed files at runtime is likewise allowed and is how an interactive view reads its data. What is forbidden is a *service* - anything that executes our logic off the reader's device, anything that reports a reader's behaviour anywhere, and any third-party script that phones home. A third-party asset is judged on its bytes, its licence and its privacy behaviour (section 8), not on its hostname; prefer self-hosting when the asset is small enough that a request is the larger cost.
2. **The runner is the architecture.** Every pipeline decision is measured against a stock GitHub-hosted `ubuntu-latest`: 4 vCPU, 16 GB RAM, no GPU, 6 h per job, 20 concurrent jobs, 10 GB cache per repo, 500 MB artifact storage, and a **1 GB hard cap on the published Pages site**. Actions minutes are free and unmetered because this repository is public - wall-clock is the constraint, not a monthly budget. Nothing here is billed, which is why the money figure Rule #10 permits on the operator console is a counterfactual and not a cost. A model that does not fit, a step that does not finish, a cache that does not hold, or a site that outgrows 1 GB is a design error, not a budget request.
3. **Contracts before logic.** Every persisted shape - article, summary, visual decision, eval row, run manifest, config, digest payload - is a Pydantic model in `backend/idhazh/contracts/` before any logic reads or writes it. The exported JSON Schema in `schemas/` is generated from it, never hand-written.
4. **docs/ = the memory; a decision lives on the page it impacts.** Pipeline rules, published shapes, tuning knobs, and current subsystem contracts live in `docs/concepts/`, `docs/how-to/`, or the relevant `docs/architecture/<area>/` living doc. A choice that clears the bar (a real rejected alternative, cross-system consequences, non-trivial reversal cost) is recorded IN the living doc it impacts, as a `## Design rationale` / `## Rejected alternatives` section on that page - never as a standalone record. There is no ADR file and no `docs/architecture/decisions/` directory. An agent's private note store is a **cache** of `docs/`, never the only copy of anything.
5. **Structural fixes only.** No band-aids, no monkey patches, no "temporary" hacks. Escalate the correction level instead.
6. **No hardcoding.** Tunable knobs (article cap, truncation cap, score bands, retry budget, shard size, model refs, source lists) live in `config/`; schema-validated.
7. **No mocks unless asked.** Real implementations and real fixtures. No test touches the network - captured pages, golden summaries and canary payloads live in `tests/fixtures/`. Mocks only on explicit user request or for a genuinely untestable external boundary.
8. **Open source first.** Prefer mature OSS over custom builds. Every dependency must name a beneficiary feature and its cost (install seconds, bytes, or runner minutes).
9. **Tests ship with the feature.** Behaviour-changing commit lands with tests. Full suite green at merge.
10. **Measured, not estimated.** Any claim about throughput, cost, size, or quality carries the hardware it was measured on, the date, and the spread. An unmeasured number is labelled an estimate and may not be used to justify a design. When a measurement contradicts the design, the design changes. **One exception, and only one: a counterfactual cost in currency on the operator console.** It is computed from measured token counts and a rate the operator sets, it prints the rate it used and where that rate came from, and it is labelled for what it is - what this run would have cost at a hosted provider's price. **It is never presented as a bill**, because nothing bills us. It appears on no other surface, and every other number on every surface still carries hardware, date and spread. Owner decision, 2026-08-30, under section 0.
11. **Fetched text is data, never instruction.** Anything the pipeline pulls from the open web is untrusted. It never enters a system prompt, never becomes a shell argument, a file path, or a URL to fetch, and never reaches a reader unlabelled. The schema and the sanitizer are the control; a prompt asking a model to behave is not.
12. **Nothing costs more as the repository grows.** A step whose work scales with what we have already accumulated is a bill that arrives every run for an answer we already had. **The test is a property, not a list**: does this cost rise when nobody wrote any code - because a run appended more? If yes, it is the thing this rule is about, whatever the collection is called and whether or not anybody has thought of it yet. Published days, ledger rows, shards, images, vectors, corpus rows and the collection nobody has created yet all count equally; source a person writes does not, because it grows at review speed. **Constant cost is the default.** Take one item, one day, one shard, one header - a fixed input, never a walk over everything we hold. One good case proves the code, and what we already wrote is checked once, by the producer that wrote it. **The escape hatch is a person, and it is deliberately open**: where a growing cost is genuinely the right answer, say next to the code what it reads, how the cost grows, and why a bounded input cannot answer the question, and have a person agree. That exception is normal engineering, not a violation. What is forbidden is a growing cost nobody chose - and no agent may approve one for itself.

### Design rationale

**These are "Rules", not "Holy Laws" (renamed 2026-08-23).** The old name dressed eleven engineering constraints in religious language, which made them sound unarguable rather than reasoned. A rule earns its authority from the reason written next to it.

**Rule #12 was added 2026-09-05, and it is about cost rather than correctness.** Measured that day on an Intel Core i7-1265U: two frontend checks spent 270 s and 93 s asserting once per published story, while reading and parsing the whole archive took 0.15 s and running the function under test on every story took a further 0.02 s. The work was never the archive - it was the same handful of cases re-checked tens of thousands of times. Those 6,539 stories carried six distinct cases between them, so the corpus stopped teaching anything on about day one while the bill went on arriving every four hours. A published day is frozen once it is written, so re-reading it later cannot find a fault that `idhazh validate-days` and the contract models did not already refuse. Authority: owner, 2026-09-05.

**The default-and-exception wording was added 2026-09-06, because the rule as first written could be read as advice.** It said what not to do and named no bar for doing it anyway, so every growing step was arguable on its own merits and the arguments were always locally reasonable - the archive was right there, and walking it was the shortest code. Naming constant cost as the default inverts who carries the burden: an O(1) design needs no defence and a growing one needs a person's name against it.

**The same day, a mechanical guard was written for it and then deleted.** `backend/tests/test_archive_readers.py` scanned every test file for two hand-written path patterns and held the matches against a list of twelve approved names. It failed for three reasons and each one is worth remembering, because the next person to reach for a guard here will reach for the same one. **It enumerated the hazard rather than the safe set**, so it covered two collections out of nineteen and looked finished - `corpus/`, `assist/`, `source-health.json` and three ledgers that grow for ever were never in it. **Its own maintenance cost grew with the number of collections**, which is the defect it existed to catch. And **it was a list of paths with no escape hatch**: the only way past it was to edit the list, so it made a judgement call look like a permission slip. A rule stated as a property survives a collection nobody has invented yet; a rule stated as a list is wrong the day after it is written. This one is enforced by review, and the reviewer's question is the one sentence in the rule: does a run that changed no code make it slower. Cost, stated rather than hidden: nothing fails automatically now, so a growing step can merge if nobody asks. Authority: owner, 2026-09-06.

**Rule #1 draws the line at "a service", not at "an origin" (amended 2026-08-23).** Banning any third-party origin forbade a webfont, which costs a reader nothing a self-hosted copy does not, while the real hazard - logic executing off the reader's device, and anything reporting a reader's behaviour - was only implied. Practical consequence: an interactive chart may fetch our own committed CSV and may use a third-party charting library. A third-party script that phones home still cannot.

**Rule #10 took its one exception on 2026-08-30, and that is section 0 working rather than a rule bending.** Actions minutes are free, so wall clock is the only budget the site can show, and wall clock cannot say whether four hours was a good trade. Priced at a hosted rate, the same run gets a second unit. The exception is narrow because the hazard is narrow: a money figure reads as a fact about a bank account, so this one prints the rate it used and is labelled a counterfactual. **We are not billed, and presenting it as a bill is the one way to make it a lie.** Authority: owner, 2026-08-30.

## 1a. Architecture Principles

These operationalize the Rules and shape every subsystem.

- **Event-driven.** Stages communicate through structured-payload events, never direct calls into each other's internals. A stage consumes one validated payload and emits another; the contract between stages, and between `backend/` and `frontend/`, is a typed payload - not a function signature.
- **Pydantic models are the source of truth.** Every event, every persisted payload, and every config file is a Pydantic model under `backend/idhazh/contracts/`. `schemas/*.schema.json` is generated from those models, and the frontend's TypeScript types and validators are generated from those schemas. A CI drift gate regenerates both and fails on any diff. Nobody hand-edits a generated artifact.
- **Payloads, not calls.** Data crossing any boundary is a serializable structured payload (JSON-shaped), so it can be logged, validated, replayed, and tested with real fixtures.
- **Atomic, resumable units.** One work item is one content-addressed file written with a temp-file-plus-rename. A failed item never damages a sibling, and a re-run costs only the unfinished items.
- **Config-driven, sane defaults.** Both `frontend/` and `backend/` read tunable behaviour from `config/`; every knob has a sane default; a fresh clone runs on the defaults (Rule #6).
- **Schema-first.** Every config file and every persisted payload conforms to a generated schema in `schemas/`; a config or payload that fails its schema fails the build (Rule #3).
- **Degrade, do not fail.** A missing visual, a failed extraction, or an unreachable source degrades that item and records why. It never takes down the run.

## 1b. Logging

Logging is local by construction. There is no log sink, no log service, and no runtime call home (Rule #1).

- **Backend, developer machine.** Structured records to stderr through the standard library `logging` module, configured once at the entry point. Level from `config/`; default `INFO`. A developer reads them in the terminal.
- **Backend, CI.** The same stderr stream. GitHub Actions captures it and retains it with the run - that IS the log store. Nothing is uploaded anywhere else. Anything a later run needs to read is a committed artifact or an eval row, not a log line.
- **Frontend.** The browser console, and only the browser console. A published page logs what a reader would need to hand back when something looks wrong. No SDK, no beacon, no `fetch` to a collector.
- **Every log record is the event payload.** A stage logs the same structured envelope it emits (section 1a), so a log line and a persisted payload never disagree about what happened.
- **Secrets never reach a log record.** Not a token, not a signed URL, not a request header.

## 2. Path Rules

For anything leaving the process (JSON, logs, manifests, agent memory, error messages, doc cross-links):

- Relative paths only. No absolute paths. No drive letters.
- POSIX separators only (`/`). Never `\`.
- Minimal reconstructable form.

In-memory `Path` objects for local I/O may stay platform-native. Rule applies at the moment a path leaves the process.

## 3. Repository Topology

| Directory            | Status     | Purpose                                                                                                     |
| -------------------- | ---------- | ----------------------------------------------------------------------------------------------------------- |
| `CLAUDE.md`          | created    | This file - the engineering contract.                                                                        |
| `README.md`          | created    | Entry point.                                                                                                 |
| `docs/`              | created    | Canonical knowledge (Diataxis tiers, 3-level depth).                                                         |
| `.claude/skills/`    | created    | Claude Code skill wrappers (bootstrap, prepare-plan) that point at `docs/`.                                  |
| `.github/agents/`    | created    | Persona advisors (Andre, Carmack, Fowler, Jony, Reader).                                                     |
| `.github/scripts/`   | created    | A shell step two or more workflow jobs run. Written once so a test can execute it; never imported by `backend/`. |
| `.github/workflows/` | created    | CI, the measurement harness, the daily pipeline, and the GitHub Pages deploy.                                |
| `config/`            | planned    | Human-edited tunable knobs, schema-validated. Read by `backend/` and shipped to `frontend/` where a reader-facing surface needs one. |
| `corpus/`            | planned    | The rolling training window: source text as training samples, plus its meta and holdout files. Committed, never rendered, never served to a reader (section 0a). Rewritten by `prune.yml` (section 8). |
| `schemas/`           | planned    | Generated JSON Schema, one file per contract model. Never hand-edited (Rule #3, section 1a).             |
| `backend/`           | partial    | The build-time producer (Python). `backend/idhazh/` is the package; `backend/idhazh/contracts/` holds the Pydantic models; `backend/utilities/` holds operator tooling; `backend/tests/` holds its tests. NOT a runtime server (Rule #1). |
| `backend/bin/`       | gitignored | Local llama.cpp binaries - downloaded, not authored.                                                         |
| `backend/models/`    | gitignored | Local GGUF weights - multi-gigabyte, downloaded from Hugging Face.                                           |
| `backend/var/`       | gitignored | Reproducible run output, caches and benchmark artifacts. Never the committed record of a run.                |
| `frontend/`          | planned    | The published static site: the digest pages and the eval dashboard. `frontend/public/` holds the committed payloads the site renders; `frontend/src/contracts/` holds the generated types. |
| `frontend/dist/`     | gitignored | Built bundle for GitHub Pages.                                                                               |
| `notebooks/`         | created    | Committed notebooks a person runs off this machine, on hardware the runner does not have. Instructions only - never weights, never a token, and nothing in CI runs them (Rule #2). |
| `evals/`             | folded     | Merged into `state/`. The published dashboard keeps the `/evals/` route; the folder is gone.                 |
| `state/`             | created    | Everything one run commits for a later run to read: the eval ledger, fingerprints, seen URLs, feed health. Appended by CI, never recomputed at runtime, never served to a reader. |
| `tests/`             | planned    | Cross-cutting fixtures: captured pages, golden summaries, injection canaries.                                |
| `TODO/`              | created    | Active plan-docs. Non-authoritative working material.                                                        |

Folders are created only when real code is about to land. Do not pre-create empty modules.

## 4. Layer and Dependency Rules

- `frontend/src/` MUST NOT depend on a runtime backend service - there is none in production. It reads committed files under `frontend/public/` and nothing else.
- `backend/` is the only writer of pipeline output under `frontend/public/`. The site reads only that output.
- `backend/` MUST NOT import frontend code, and frontend code MUST NOT import backend code. They meet only through committed data and generated contracts (Rule #1, section 1a).
- `backend/idhazh/contracts/` MUST NOT import any other subpackage of `backend/idhazh/`. Contracts are the bottom of the dependency graph; everything else depends on them.
- Every stage is invocable on its own with a file in and a file out. A stage that can only run as part of the whole pipeline cannot be tested and is a design error.
- Anything fetched from the open web crosses the trust boundary exactly once, at the extraction stage, and is sanitized there (Rule #11).

## 5. Documentation Discipline

- Diataxis tiers under `docs/`: `architecture/`, `how-to/`, `concepts/`, `reference/` (+ `getting-started/`, `agents/`, `archive/`).
- Max depth: `docs/<tier>/<topic>/<file>.md`.
- Every doc: H1 title, `Last Updated: YYYY-MM-DD`, "See also" cross-links.
- One concept defined once; everywhere else links to it.
- **Process docs stay domain-neutral.** Everything under `docs/how-to/` that describes *how work is done* (authoring a plan, executing a plan, distilling a plan, shipping a PR, deploying to Pages) and `docs/reference/documentation-structure.md` are written to be copied between projects unchanged. They cite `CLAUDE.md` by section number rather than restating a project-specific rule, and they use neutral examples. A process doc that cannot be stated neutrally says so explicitly and names why.
- ASCII-only in all repo text: commit messages, docs, code comments, log strings, agent markdown, CLI output (use `-`, `->`, `>=`, and "section"). No curly quotes, em-dashes, or non-ASCII symbols.
- **`docs/` is the memory.** `AGENTS.md`, `/memories/`, and any other private agent note store are derived caches, not authoritative; if one disagrees with `docs/`, docs win. A note store can be cleared at any moment and is invisible to a person reading the repository, so a durable fact learned during a session is written into `docs/` in that same session. That includes execution craft - a tool quirk, an environment trap, a command whose result cannot be trusted at face value - which lives in [`docs/reference/agent-notes.md`](docs/reference/agent-notes.md).
- Architecture decisions are recorded IN the living doc they impact, never as standalone records under a `decisions/` directory. Git history is the immutable record of when it changed.
- Open questions live in the active plan-doc under `TODO/`, not in this file.
- Docs-only PRs are a code smell - unless the change **is** to the documentation system itself (this section, the placement reference, or a page that exists only to be read).

## 6. Correction Levels

| Level | Scope                                                         | Workflow                              |
| :---: | ------------------------------------------------------------- | ------------------------------------- |
|   0   | Comments, typos, log strings                                  | Direct fix                            |
|   1   | 1 file, ~50 lines, isolated bug                               | Direct fix                            |
|   2   | 1-2 files, explicit behavior change                           | Plan -> execute once scope is clear   |
|   3   | 2-3 files, cross-cutting                                      | Plan -> phased execution              |
|   4   | 4+ files, structural                                          | Propose breakdown first               |
|   5   | Core design / a persisted contract / the model pick / the trust boundary | Design consultation only - pause work |

When in doubt, choose the higher level.

## 7. Debug Logging

- Temporary logs MUST be prefixed `[DEBUG]`.
- Before finalizing: grep for `[DEBUG]` and remove every match. Re-run tests after cleanup.

## 8. Git Hygiene

User saying finish / ship / merge authorizes the normal reversible git workflow: inspect, named branch, stage exact paths, commit, push, gates, merge.

Avoid (broad / lossy / history-rewriting):

- `git stash`
- `git reset --hard`
- `git clean -fd`
- `git checkout .` / broad `git restore .`
- `git add .` / `git add -A`
- `git push --force` / `git push --force-with-lease`
- Amending pushed commits
- Leaving a merged PR's remote branch undeleted or its `: gone]` local tracking branches unpruned.

**One exception, and only one: `.github/workflows/prune.yml`.** It squashes commits older than `finetune.prune_keep_days` and force-pushes `main`, every `finetune.prune_every_days`. Nothing else in this repository may force-push, and no person may. The exception exists because the corpus commits article text (section 0a) and git history is append-only, so deleting a row does not delete its bytes - the only way to bound the repository is to rewrite the range those bytes are in.

What it costs, stated rather than implied: a squash boundary is per-commit, not per-path, so the range it collapses carries `backend/`, `docs/` and `state/` as well as `corpus/`. `git blame` and `git bisect` reach back `prune_keep_days` to `prune_keep_days + prune_every_days` and no further, and a commit SHA older than that stops resolving. A clone taken before a prune has to be re-fetched. Owner decision, 2026-08-28, taken over the alternative of keeping the corpus on a branch nobody works from.

Safe workflow: `git status --porcelain`, leave unrelated dirty files alone, stage only explicit paths, verify with `git diff --cached --name-only`, small reversible commits on a named branch, push, merge after gates pass.

Commit messages describe the change. **No AI co-author / attribution tags.**

## 9. Definition of Done

The commands behind these gates are in [`docs/how-to/run-the-gates.md`](docs/how-to/run-the-gates.md).

- [ ] Tests added/updated at the tier appropriate to the surface (section 13). No mocks per Rule #7.
- [ ] Full suite green **on the merge candidate**. CI is the authoritative arm and is six to fifteen times faster than a developer box; a local full-suite run before every push is optional, not required.
- [ ] Applicable local lint, type checks and selected tests pass before the push, per [docs/how-to/run-the-gates.md](docs/how-to/run-the-gates.md). Use the shared test selector. Keep full-suite checks in CI unless local full coverage is explicitly needed. Verify a worker's unchanged test record instead of repeating its check; documentation-only closure needs no local application suite.
- [ ] Contract drift gate green: schemas and frontend types regenerate byte-identical to what is committed.
- [ ] For published-site changes: smoke-tested via integrated browser tools per section 12.
- [ ] For reader-facing and operator-facing surfaces: the sufficiency checks in [`docs/concepts/design-system.md`](docs/concepts/design-system.md) pass, or a `## Design rationale` entry says why not. A surface can fail by being too little.
- [ ] Canonical docs updated in `docs/` (right tier).
- [ ] Schemas version-stamped + changelogged (and migrated if breaking) when any persisted contract changed (section 11).
- [ ] Module `AGENTS.md` updated if structure or invariants changed.
- [ ] No `[DEBUG]` markers left.
- [ ] No new hardcoded values.
- [ ] No new mocks unless explicitly requested.
- [ ] Lockfiles in sync with manifests.
- [ ] Any new performance or quality number carries hardware, date and spread (Rule #10).
- [ ] Runner budget respected: no step pushes a job past its timeout, the cache past 10 GB, artifacts past 500 MB, or the published site past 1 GB (Rule #2).

## 10. Anti-Patterns (Do NOT)

- Reinterpret, downgrade, substitute, or scope-narrow a source or instruction the user named explicitly, without surfacing it as a scope change for sign-off (STOP-AND-SURFACE).
- Assume a backend exists in production.
- Hardcode tunables, source lists, model refs, thresholds, or magic strings. They live in `config/`.
- Hand-edit a generated artifact (`schemas/*.schema.json`, `frontend/src/contracts/*`). Edit the Pydantic model and regenerate.
- Store absolute / backslash paths in any persisted artifact.
- Let fetched text reach a system prompt, a shell argument, a file path, or an outbound URL (Rule #11).
- Build custom HTTP / retry / parsing / validation / extraction systems when a mature OSS library exists.
- Swallow exceptions or silently coerce invalid input - fail fast at the boundary.
- Mock in tests by default, or let any test touch the network.
- Commit a model weight, a downloaded binary, or a reproducible run intermediate.
- Add a runtime telemetry / analytics / error-tracking SDK.
- Ship a feature that depends on a runtime backend, an account, or a push notification.
- Add a framework / library / build tool without naming its cost and its beneficiary feature.
- Quote a throughput, cost or quality number without saying what measured it and when (Rule #10). The operator console's counterfactual cost is the one carve-out, and printing it as a bill breaks it.
- Justify a design with an estimate when a measurement is cheap to take.
- Mint a new persisted field without stamping the schema `version` date, appending a `changelog` entry, and writing the read-side migration in the same commit.
- Raise the runner budget to fit a feature. The budget is the platform, not a preference - if the feature cannot run inside it, the feature is simplified.
- Let `TODO/`, chat logs, `AGENTS.md`, or a private agent note store become the source of truth for anything. They are caches of `docs/`.
- Make a domain-neutral process doc project-specific (section 5).
- Pre-create empty modules "for later".
- Skip the docs update.

## 11. Schema Versioning

Every config file and every persisted surface is a Pydantic model in `backend/idhazh/contracts/` before logic is written (Rule #3, section 1a), and `schemas/<name>.schema.json` is generated from it. The persisted surfaces this project cares about:

- **Stage payloads** - the validated shapes that move between pipeline stages and land as committed files.
- **The eval ledger** - the CSV row shape appended once per item.
- **The run manifest** - what ran, against which model, at which commit.
- **Config** - the tunable knobs in `config/`.
- **Published payloads** - what `frontend/public/` carries and the site renders.

### `version` is a date-stamp, not an integer

Each schema carries a `version` field that is a human-readable date-stamp - never an integer, never an epoch timestamp:

- Format: `YYYY-MM-DD` (e.g. `2026-08-20`). When more than one change lands the same day, extend to the minute or second: `YYYY-MM-DDTHH:MM` or `YYYY-MM-DDTHH:MM:SS`.
- The value is ASCII-sortable and self-documenting: `version` tells you *when* the shape last changed, and equals the newest `changelog` entry's version.

### `changelog` array (in-schema change log)

Each schema carries a `changelog` array - newest entry first - recording every change and why it was made. Each entry is `{ version, change, why }`:

- `version` - the date-stamp of that change (same format as above).
- `change` - what changed (field added / removed / retyped, semantics shifted).
- `why` - the reason for the change.

Each change is one commit:

- **Additive, backwards-compatible** (new optional field): append a `changelog` entry, set `version` to today; older payloads still validate.
- **Breaking** (removed field, type change, semantic shift): append a `changelog` entry, set `version` to today, AND write the read-side migration the new build runs on older payloads - same commit.

A payload written by yesterday's run that today's build cannot read is a contract break and a release blocker.

## 12. Published-Site Verification (Browser Smoke)

Any change to the published site MUST be verified by the agent using integrated browser tools, not deferred to the human. The commands, and the three traps that make this check lie, are in [`docs/how-to/run-the-gates.md`](docs/how-to/run-the-gates.md).

Minimum loop:

1. Confirm dev server up; start if not.
2. Navigate the affected page(s) plus one cross-page smoke.
3. Read the page console; confirm zero new `[error]` events and zero new `404`.
4. If layout-sensitive: screenshot to confirm visual intent.
5. Confirm the page still renders when its data file is absent or empty - a published page that white-screens on missing data is a failure.
6. Only then mark done.

Does not apply to backend-only, tooling, docs, or schema-only changes.

## 13. Test Coverage Policy

Four tiers - **Unit / Contract / Integration / End-to-end**. Change without an appropriate-tier test in the same commit is a Definition-of-Done failure. No test touches the network; fixtures live in `tests/fixtures/`. Mock carve-outs require an explicit user request.

**A test's cost belongs to the code it checks, never to what the pipeline has piled up.** So a test does not walk a collection that a run appends to - the committed days, the telemetry and state shards, the search index, the corpus, or any collection added after this sentence was written (Rule #12). A per-item rule is driven from a bounded fixture, and the canary day under `backend/var/canary/` is the one to reach for: it is fixed in size and it can carry a case the archive has never produced. Where a question really is about the whole tree, it is asked once and asserted on the total rather than once per story - and the producer has already validated every payload at write time, so re-checking a frozen day on every later run buys nothing. Where a walk is genuinely the right answer, Rule #12's escape hatch applies: say next to the test what it reads and why a fixture cannot answer it. Measured 2026-09-05 over 16 days and 6,539 stories: reading the whole tree costs 0.15 s, while the two specs that assert once per story cost 270 s and 93 s, and the corpus offers six distinct cases however far it grows.

**A test checks code functionality, not data hygiene, and it is driven with a built parameter rather than a loop.** A check that reads committed data to ask whether the data is well-formed is not a test, whatever file it sits in. It has three legal fates and no fourth: delete it where a fixture-driven test already covers the same rule; move it into the producer that writes the data (the one-picture-one-story rule now lives in `idhazh validate-days`); or make it an operator surface under `backend/utilities/`, which pytest does not run. A scheduled pytest job is not one of the three. Where the awkward shape is the point - eleven failure causes with a 529-to-1 spread, a source sitting exactly on a display cap - that shape is **built**, because a built one also carries the case the archive has never produced. Owner ruling, 2026-09-06.

**A walk over committed data tends to carry a fuse, and that is the second reason to refuse one.** Six migrated tests counted how many committed entries still *lacked* a new field and asserted that count was not zero, so each was timed to go red on the day the last unmigrated payload aged out of retention - a date on the calendar rather than a change anybody made. A read-side migration is proved by removing the key from a fixture, which cannot age out. `docs/reference/agent-notes.md` records the day one of these fired and took every open pull request red at once.

Per tier:

- **Unit** - pure functions (sanitization, sharding, scoring maths, serialization round-trip).
- **Contract** - the generated schemas vs the readers and the writers, plus the drift gate.
- **Integration** - two or more stages composed against real fixtures, with the model boundary driven by a recorded response where the model itself is not under test.
- **End-to-end** - the pipeline run start-to-finish on a fixture corpus, producing a digest; and the published site rendered in a real browser against that output.

## 14. Agent Roster

Seven persona advisors live under `.github/agents/`, each at a distinct altitude:

| Agent                               | File               | Altitude                                                                      |
| ----------------------------------- | ------------------ | ----------------------------------------------------------------------------- |
| Reader                              | `reader.agent.md`  | the person the digest is for - is it worth their two minutes?                 |
| Editor                              | `editor.agent.md`  | what the digest covers and at what length - story selection, where a cut may fall, what to trade when a budget binds |
| Jony (UI/UX)                        | `jony.agent.md`    | the published surface: page, typography, chart-vs-diagram, the dashboard      |
| Susan (Craft & Delight)             | `susan.agent.md`   | whether a surface is good enough to ship - the demand side of design review   |
| Andre (AI / LLM)                    | `andre.agent.md`   | model pick, prompt strategy, eval design, the injection surface               |
| Fowler (Architecture & Engineering) | `fowler.agent.md`  | architecture + contracts + commits + tests                                    |
| Carmack (Engine & Runtime)          | `carmack.agent.md` | inference runtime, runner budget, throughput, cache and shard economics       |

Rule: adding a new agent requires justifying a distinct altitude not already covered. Two agents at the same altitude collapse into one.

Where Reader and Editor both touch content: **Reader reports what reading it was like, Editor rules what should have run and how long.** Reader does not propose; Editor does not speak for the reader's experience of the page.

Where Jony and Susan both touch the page: **Jony rules what survives on the page, Susan rules whether what survived is good enough to ship.** They are the two halves of one review and neither is sufficient alone.

### Design rationale

**Susan was added on 2026-08-29 because the roster was six vetoes and no demand.** A system of pure vetoes converges on the minimum that passes every veto - measured 2026-08-28 as a published surface using 40.6 percent of a 1536px screen, two responsive breakpoints in the whole frontend, no elevation scale, two icons and no interactive chart. Every one of those passed a review.

Giving Jony the demand mandate too was rejected: one head holding both "remove before adding" and "this is not enough" resolves to the veto every time. Making sufficiency advisory was rejected because an advisory check is the one skipped on the day it would have bitten. Authority: owner, 2026-08-29.

## See also

- [`README.md`](README.md) - what yen-idhazh is.
- [`docs/agents/bootstrap.md`](docs/agents/bootstrap.md) - the load ritual every persona runs before answering.
- [`docs/agents/guardrails.md`](docs/agents/guardrails.md) - the rules-only digest of this contract.
- [`docs/how-to/run-the-gates.md`](docs/how-to/run-the-gates.md) - the environment and the commands behind sections 9 and 12.
- [`docs/reference/agent-notes.md`](docs/reference/agent-notes.md) - environment and tool quirks that make a command lie.
- [`docs/reference/documentation-structure.md`](docs/reference/documentation-structure.md) - where each kind of doc lives.
- [`docs/concepts/vision.md`](docs/concepts/vision.md) - what this project is and is not.
