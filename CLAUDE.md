# CLAUDE.md - yen-idhazh Engineering Contract

**Last Updated**: 2026-09-12

Non-negotiable contract for any human or AI agent working in this repo.

You are a data-pipeline and static-publishing agent.

## 0. User Approval

User approval supersedes every agent and every rule in this file. Amend conflicting rules in the same commit.

## 0a. Non-Goals

**A non-goal is a dated decision with an owner, not a law of physics.** Three of the clauses below have already been narrowed by owner decisions - the fine-tuning clause on 2026-08-27, the article-bodies clause on 2026-08-28, and the LLM-as-judge clause on 2026-09-07 and again on 2026-09-11 - which is the proof. So naming a non-goal is not a finished answer: when intent meets one, price what narrowing it would cost and what it would buy, and hand the decision back (section 0d, section 0c). What a non-goal does mean is that the default answer is no and the burden is on the change. **No agent narrows or widens one for itself** (section 0).

- **Production backend.** See Guardrail #1. `backend/` is a build-time producer that runs in CI and on a developer machine; it is never a service.
- **Hosted inference, anywhere.** No API call to a model provider from the pipeline, the published site, or the reader's browser. Inference running wholly on the reader's device over weights we committed and serve from our own origin is not hosted inference, and is governed by Guardrail #1.
- **On-device inference on the digest's critical path.** The reading experience never waits on a model. Every on-device feature is secondary, reader-initiated, and removable without changing a single digest assertion. **The bundle must render complete with the model directory deleted - which is a test anybody can run, not a description of what ships.** The weights are committed and served from our own origin, and a plan to delete them was descoped on 2026-09-09. Since 2026-09-10 there is a second origin, so the test has a second half: with the committed weights gone **and** the hub blocked, every digest assertion still renders and search says it cannot run.
- **Account systems** (login, signup, email collection, server-backed sync). The site is anonymous and read-only.
- **Push notifications.** The reader decides when to read.
- **Runtime telemetry / analytics SDKs / third-party scripts that fetch at runtime.** Static-first means no runtime calls home.
- **Republishing article bodies to a reader.** The digest publishes a link and our own summary. A reader-facing page never carries the source text. `corpus/` is the one exception: it holds source text as training samples, and nothing renders it, links to it, or serves it. Owner decision, 2026-08-28.
- **Paywalled or login-walled sources.** If `robots.txt` or a paywall says no, the answer is no.
- **LLM-as-judge evaluation.** A judge that shares the failure modes of the thing judged is not a measurement. **The property is one sentence: a model verdict that reaches no reader and selects nothing to publish is not a section 0a deviation.** Two things stay banned whether or not a verdict satisfies the property, and those two are the whole of the ban. **A model may not grade a published summary, and it may not grade a published visual.** **A model may not select what publishes** - a label says what a story is about; it never decides whether the story runs. Those verdicts are deterministic or human. A verdict that is neither of those two is permitted. **The two bans stand in addition to the property, never as instances of it**, and the witness is a model pre-label sitting in a human label queue: it reaches no reader and it selects nothing, so the property on its own would permit a grade of a published summary. The offline write-critique-revise prompt loop is the worked example rather than a carve-out - a model judge proposes a revised summariser prompt, deterministic model-free scorers dispose, the judge's preference promotes nothing, and nothing it produces reaches a reader ([`docs/concepts/evaluation.md`](docs/concepts/evaluation.md)). Owner decisions, 2026-09-07 (the loop) and 2026-09-11 (the property), under section 0.
- **Training on the runner, GPU runners, and models that do not fit the runner.** See Guardrail #2. Training a model elsewhere is not a non-goal. The runner only ever opens finished weights and reads bytes, so where those weights were trained does not change what the runner has to do. A fine-tuned model is an ordinary candidate: one entry in `config/idhazh.json`, the same qualification, the same SHA-256.
- **Accessibility framework / audit tooling** (axe-core, WCAG-level gating, automated contrast checks). Descoped at project level. Basic ARIA and keyboard navigation ARE in scope: visible focus rings, labelled controls, semantic landmarks, keyboard-reachable interactive surfaces. Design-level accessibility is encouraged; merge-gating on audit tooling is not.

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

Everywhere else restates this section rather than inventing its own style rule (Guardrail #4): [`AGENTS.md`](AGENTS.md) carries it for agent tools that read that file instead of this one.

## 0c. Decision Requests and Tables

**Write every answer in plain, simple English.** A person outside this project understands it on one read. No subsystem terms, no invented jargon, no vendor name used as vocabulary. Where a term is unavoidable, define it in the same sentence. This is section 0b applied, and it is the clause agents break most.

When you need the user to choose, ask in one message, in this order, and put nothing before it:

1. **Situation.** What is true now.
2. **Problem.** What is wrong or undecided, in one or two sentences.
3. **Impact.** What it touches and what it costs to leave alone - the files, the subsystems, the published surfaces, the runs.
4. **Options.** Every option worth taking, each with its cost and what it gives up. An option with no cost named is not an option.
5. **Recommendation.** One option per table, marked `**Recommended**` in the row itself and named again at the end with the reason in one sentence.

**Every table in every answer is lettered, and every row carries an id.** Tables are `Table A`, `Table B` and so on, in the order they appear. A row's id is that letter plus its number - `A1`, `A2`, `B1` - and it is the first column. No id repeats in one message, so the user answers `A3`, or `A2 and B1`, and quotes nothing back.

**A message may carry more than one table when one decision genuinely depends on another**, and then each table gets its own recommended row. What it may not do is bundle unrelated decisions to save a round trip: a table the user did not need to see is a table they have to read. When several tables appear, the five-part shape is written once for the whole message, not repeated per table.

**The recommendation is marked where the choice is made.** A recommendation stated only in a closing paragraph makes the reader hold a row id in their head while they scan back up the table, so it is marked in the row AND restated at the end. The restatement carries the reason; the marker carries the position.

A message with no options is a status update, not a decision request, and does not use the five-part shape.

[`AGENTS.md`](AGENTS.md) restates this section; it does not extend it (Guardrail #4).

## 0d. Intent, Contract, Code

**Intent is the top of the chain. The contract follows intent. Code follows the contract.**

**Intent** is what the user wants to be true when the work is done. **The contract** is this file, `docs/`, the models in `backend/idhazh/contracts/` and the generated `schemas/`; when intent and the contract disagree, the contract is what changes, in the same commit (section 0). **Code** follows the contract; when they disagree, the code is what changes.

**Compliance is to the intent, not to the current shape of the system.** An existing limitation - a guardrail, a budget, a schema, a dependency, a design already shipped - is a cost to price, never an answer on its own. "We cannot, because X" is not a finished sentence. The finished sentence names what X costs to move, what moving it buys, and what you recommend.

**When intent meets a limitation, the answer moves.** Three moves are legitimate.

- **Do it**, and say what it moved.
- **Price it**: what the limitation costs to move, what moving it buys, and a recommendation (section 0c).
- **Say what would settle it**, when the price cannot be measured today: name the measurement, what it costs to take, and the smallest step that makes progress while it is unknown. Label the guess an estimate (Guardrail #10) - an estimate carrying its own name is a better answer than a refusal.

Not legitimate: naming the limitation and stopping. **A limitation named with no next move is an unfinished answer.**

**When the measurement refuses the intent, that is a finding and not a veto.** Report what the data says, name the part of the intent it still supports, and hand the decision back with options. The agent never narrows the intent by itself (section 10); the person does (section 0).

**What this does not license.** It does not license routing around a person's ruling (section 0), the runner budget (Guardrail #2), or the trust boundary (Guardrail #11) - those are surfaced, not overruled. And it does not license a larger change than the intent needs: intent is what the user asked for, not what you would have asked for.

## 1. Adaptive Guardrails (Read First, Every Session)

**When a guardrail bites, that is feedback, not a verdict.** Two responses are legitimate - adapt it, saying what changed and why, or take a named exception recorded next to the work - and two are not: quietly routing around it, or reading it as advice because it is inconvenient. **Every deviation carries a person's name, and no agent may adapt a guardrail or take an exception for itself**: it proposes, a person disposes, and the decision is written into the commit that carries it. Each guardrail carries its reason, the reason is the load-bearing part, and **a guardrail cited without its reason is a half-quote** - so a guardrail whose reason no longer holds is one to change, and saying so is the job. **Three of the twelve are boundaries rather than adaptable constraints** - static-first publication (#1), the runner budget (#2) and the trust boundary (#11) - which an agent surfaces and never overrules, because the first two are set outside this project and the third protects a reader.

1. **Static-first publication, because there is no server we operate.** The forbidden thing is **a service we run** - logic executing on a machine we maintain, and a runtime dependency on a provider that can go down or send a bill. What we do have is not forbidden and must not be described as absent. **The GitHub repository is the backend**: it holds the payloads a run commits, and the Pages bundle delivers them. **The browser is our compute** - the app runs there, and that includes the search model a reader starts by hand, which downloads on demand, from our own origin or the second one section 0a names, and runs on their device. **Telemetry exists** (Guardrail #10 and section 1b): the pipeline's own run, model, evaluation and hardware measurements are committed to the repository, projected to a browser-safe file, and fetched at runtime by the operator console. One sentence bounds all of it - **the ban is on automatic transmission, not on measurement.** Nothing reports a reader's behaviour anywhere, no third-party script phones home, and there is no account, no ad and no push notification. Fetching a static asset is allowed, including from a third party - a font, a stylesheet, an icon set, a charting library - and fetching our own committed files at runtime is how an interactive view reads its data. A third-party asset is judged on its bytes, its licence and its privacy behaviour (Guardrail #8), not on its hostname; prefer self-hosting when the asset is small enough that a request is the larger cost. This one is surfaced rather than adapted: GitHub Pages is the platform we publish on and a reader's privacy is not ours to trade, so a design that needs a server is reported as a design that does not fit here.
2. **The stock runner is the production target, and measuring elsewhere is legitimate.** What must fit is production: a stock GitHub-hosted `ubuntu-latest` - 4 vCPU, 16 GB RAM, no GPU, 6 h per job, 20 concurrent jobs, 10 GB cache per repo, 500 MB artifact storage, and a **1 GB hard cap on the published Pages site**. A benchmark, an experiment or a one-off export may run on any hardware and says which hardware it ran on (Guardrail #10), so a developer-machine figure is a legitimate instrument rather than a breach - it just cannot stand in for the runner when the question is whether the step finishes inside the job. Actions minutes are free and unmetered because this repository is public, so wall clock is the constraint rather than a monthly budget; nothing here is billed, which is why the money figure Guardrail #10 permits on the operator console is a counterfactual and not a cost. **A model that does not fit, a step that does not finish, a cache that does not hold, or a site that outgrows 1 GB is a design error, not a budget request.** The required next move is not a refusal: name the design that does fit and what it traded - fewer items, a smaller model, a shorter context, a shard that splits - so the answer is a smaller feature rather than a larger machine. These limits are GitHub's and not ours, so this one is surfaced and never adapted; an agent cannot move a number it does not own, and it is not asked to.
3. **Contracts before logic.** Every persisted shape - article, summary, visual decision, eval row, run manifest, config, digest payload - is a Pydantic model in `backend/idhazh/contracts/` before any logic reads or writes it, and the JSON Schema in `schemas/` is generated from that model, never hand-written. The reason is that a shape nobody declared is a shape nobody can validate, migrate, or generate a frontend type from, so it survives instead as several hand-written copies that drift apart quietly. **The test is a substitution: a persisted shape with no model is a contract break, not "not modelled yet".** A shape that appears mid-work - a file a stage has started writing, a column added to a ledger, a key a payload grew - stops the work until it has a model, because the cheapest moment to declare it is before anything has read it. Deviating buys an hour now and costs a read-side migration later, so it is a person's call, written into the living doc for the surface it impacts and never taken by an agent for itself.
4. **docs/ is the memory, and a decision lives on the page it impacts.** Pipeline rules, published shapes, tuning knobs and current subsystem contracts live in `docs/concepts/`, `docs/how-to/` or the relevant `docs/architecture/<area>/` living doc. A choice that clears the bar - a real rejected alternative, cross-system consequences, non-trivial reversal cost - is recorded IN the living doc it impacts, as a `## Design rationale` or `## Rejected alternatives` section on that page, never as a standalone record. There is no ADR file and no `docs/architecture/decisions/` directory. The reason is where each kind of reader stands: a decision written beside the thing it governs is read by the person about to change that thing, and a decision filed in a separate register is read by nobody. **An agent's private note store is a cache of `docs/`, never the only copy of anything** - it can be cleared at any moment, and a person reading the repository cannot see it. So the loop closes in the same session: when a durable fact is learned and no page owns it, either the page is created or the fact goes to [`docs/reference/agent-notes.md`](docs/reference/agent-notes.md), and "there was nowhere to put it" is not an outcome. Leaving a fact out costs the next person the search that found it, so keeping one out of `docs/` deliberately is a person's call, and that person says where it lives instead.
5. **Structural fixes only.** No band-aids, no monkey patches, no "temporary" hacks. This one does not bend: a temporary fix is a permanent fix with a note attached, and the note is what gets lost. When the structural fix is out of scope, escalate the correction level and say so - that is the adapt path, and it is the only one. Escalation is a person's decision under section 6, not a label an agent applies to itself to keep going.
6. **No hardcoding, anywhere in the codebase.** Frontend, backend, utilities, workflows and measurement harnesses all read tunable behaviour from `config/`, schema-validated, and every knob ships a sane default so a fresh clone runs unconfigured. **This binds the frontend exactly as hard as the backend**: `theme.elevation_enabled`, `theme.surface_tint_alpha`, `motion.duration_base_ms`, `chart.donut_thickness_px` and the console's `default_window_days` are knobs, not literals. The named examples on the pipeline side are the truncation cap, the score bands, the retry budget, the shard size and its timeout, the model reference and its checksum, and the source list. **The test is a substitution: change the config or the theme token, and the behaviour changes with no source edit.** If it does not, it was hardcoded. **A feature under development ships behind a config flag, default off, and the flag is an ordinary knob in `config/` with a schema and a default** - a half-built surface reachable only by editing source is a branch nobody can test and nobody can turn off in a hurry. **A flag carries its removal condition in the same line that declares it**: what has to be true for the flag and the old path to be deleted. A flag with no removal condition is a permanent second implementation, which costs more than the feature it was hiding. Deviating costs a code change and a redeploy where a config edit would have done, so a value that genuinely belongs in source - a protocol constant, a format literal - is named as one by a person who says why it can never vary.
7. **No mocks unless asked, because a mock is how a thing looks finished without being built.** The failure this exists to stop is specific and it is an agent failure: asked for a capability, an agent writes a stub that returns a plausible value, writes a test that asserts the stub, and reports success. Everything passes and nothing works - which is worse than a red test, because a red test tells the truth. So real implementations and real fixtures: captured pages, golden summaries and injection canaries under `tests/fixtures/`, and no test touches the network. Where the model itself is not under test, the model boundary is driven by a recorded response - a real artifact, not a fake. A mock ships only on explicit request, or for a genuinely untestable external boundary, and it is named as one where it sits; that named exception is the whole of the adapt path here, and it is a person's to open.
8. **Open source first.** Prefer a mature open-source library over a custom build, and name for every dependency the feature that benefits and the cost it adds - install seconds, shipped bytes, or runner minutes. The reason is arithmetic rather than taste: a library has already paid for the edge cases we have not met yet, so a hand-rolled HTTP client, retry policy, parser or validator buys them back one outage at a time. Naming the beneficiary matters as much as naming the cost, because a dependency nobody can attribute to a feature is one nobody can later argue for removing. Writing it ourselves is sometimes right and is not a breach; it is a person's call that says which library was considered and what about it did not fit.
9. **Tests ship with the feature.** A behaviour-changing commit lands with its tests, at the tier appropriate to the surface (section 13), and the full suite is green at merge. The reason is what a late test is written against: code as built rather than behaviour as intended, so it documents the bug as readily as the feature and then defends it. Deferring the test costs a commit nobody can revert with confidence, because nothing says what it was supposed to do; so a feature that lands without one carries a person's name and the row that will add it.
10. **Measured, not estimated.** Any claim about throughput, cost, size, or quality carries the hardware it was measured on, the date, and the spread. An unmeasured number is labelled an estimate. When a measurement contradicts the design, the design changes. The reason is that an unlabelled guess is indistinguishable from a reading, so one guess propagates silently into every figure computed from it. **An estimate may not settle a design; it may carry one to the next step.** It carries a design forward only when three things are true together: it is labelled an estimate, it names the measurement that would settle it, and it names the smallest step that makes progress while the answer is unknown. That is section 0d's third move, and it is why a missing measurement is never on its own a reason to stop. What an estimate may never do is close the question - when the measurement is cheap to take, taking it is the work. **One exception, and only one: a counterfactual cost in currency on the operator console.** It is computed from measured token counts and a rate the operator sets, it prints the rate it used and where that rate came from, and it is labelled for what it is - what this run would have cost at a hosted provider's price. **It is never presented as a bill**, because nothing bills us. It appears on no other surface, and every other number on every surface still carries hardware, date and spread. Owner decision, 2026-08-30, under section 0. Deviating costs a reader the ability to tell what would move a number, so publishing a figure with no provenance is a person's call and is labelled as one where it is published.
11. **Fetched text is data, never instruction - and this project does fetch.** Every run reads the open web: feed entries, article pages, whatever text a source chose to publish that day. All of it is untrusted. The hazard has a name - **side-loaded instructions reaching a model**, text that talks its way into being obeyed rather than summarised. It never enters a system prompt, never becomes a shell argument, a file path, or a URL to fetch, and never reaches a reader unlabelled. A filename is recomputed from the item's identity, never built from the item's own words. **The schema and the sanitizer are the control; a prompt asking a model to behave is not** - a polite instruction is itself text, and text is the thing we just said we do not trust. This one protects a reader rather than us, so it is surfaced and never adapted: a stage that needs fetched text somewhere this forbids is a stage to redesign, and it goes to a person as a design question.
12. **Nothing costs more as the repository grows.** A step whose work scales with what we have already accumulated is a bill that arrives every run for an answer we already had. **The test is a property, not a list**: does this cost rise when nobody wrote any code - because a run appended more? If yes, it is the thing this guardrail is about, whatever the collection is called and whether or not anybody has thought of it yet. Published days, ledger rows, shards, images, vectors, corpus rows and the collection nobody has created yet all count equally; source a person writes does not, because it grows at review speed. **Constant cost is the default.** Take one item, one day, one shard, one header - a fixed input, never a walk over everything we hold. One good case proves the code, and what we already wrote is checked once, by the producer that wrote it. **The escape hatch is a person, and it is deliberately open**: where a growing cost is genuinely the right answer, say next to the code what it reads, how the cost grows, and why a bounded input cannot answer the question, and have a person agree. That exception is normal engineering, not a violation. What is forbidden is a growing cost nobody chose - and no agent may approve one for itself. **This is the guardrail the other eleven were rewritten toward**: a property rather than a list, the reason standing beside the constraint, and an escape hatch that names a person - which is why it needed a voice pass and nothing more.

## 1a. Architecture Principles

These operationalize the guardrails and shape every subsystem.

- **Event-driven.** Stages communicate through structured-payload events, never direct calls into each other's internals. A stage consumes one validated payload and emits another; the contract between stages, and between `backend/` and `frontend/`, is a typed payload - not a function signature.
- **Pydantic models are the source of truth.** Every event, every persisted payload, and every config file is a Pydantic model under `backend/idhazh/contracts/`. `schemas/*.schema.json` is generated from those models, and the frontend's TypeScript types and validators are generated from those schemas. A CI drift gate regenerates both and fails on any diff. Nobody hand-edits a generated artifact.
- **Payloads, not calls.** Data crossing any boundary is a serializable structured payload (JSON-shaped), so it can be logged, validated, replayed, and tested with real fixtures.
- **Atomic, resumable units.** One work item is one content-addressed file written with a temp-file-plus-rename. A failed item never damages a sibling, and a re-run costs only the unfinished items.
- **Config-driven, sane defaults.** Both `frontend/` and `backend/` read tunable behaviour from `config/`; every knob has a sane default; a fresh clone runs on the defaults (Guardrail #6).
- **Schema-first.** Every config file and every persisted payload conforms to a generated schema in `schemas/`; a config or payload that fails its schema fails the build (Guardrail #3).
- **Degrade, do not fail.** A missing visual, a failed extraction, or an unreachable source degrades that item and records why. It never takes down the run.

## 1b. Logging

Logging is local by construction. There is no log sink, no log service, and no runtime call home (Guardrail #1).

- **Backend.** Structured records to stderr through the standard library `logging` module, configured once at the entry point. Level from `config/`; default `INFO`..
- **Backend, CI.** The same stderr stream. GitHub Actions captures it and retains it with the run - that IS the log store. Nothing is uploaded anywhere else. Anything a later run needs to read is a committed artifact or an eval row, not a log line.
- **Frontend.** The browser console, and only the browser console. A published page logs what a reader would need to hand back when something looks wrong. No SDK, no beacon, no `fetch` to a collector.
- **Every log record is the event payload.** A stage logs the same structured envelope it emits (section 1a), so a log line and a persisted payload never disagree about what happened.
- **Secrets never reach a log record.** Not a token, not a signed URL, not a request header.

## 2. Path Conventions

For anything leaving the process (JSON, logs, manifests, agent memory, error messages, doc cross-links):

- Relative paths only. No absolute paths. No drive letters.
- POSIX separators only (`/`). Never `\`.
- Minimal reconstructable form.

In-memory `Path` objects for local I/O may stay platform-native. This applies at the moment a path leaves the process.

These are conventions rather than guardrails because a serialization invariant has one correct answer, so there is nothing here to adapt.

## 3. Repository Topology

`backend/` is a build-time producer that runs in CI and on a developer machine and is never a service. `frontend/` is the published static site. The two meet only through committed data and the contracts generated from `backend/idhazh/contracts/` (section 4).

Which directory holds what, who writes it, whether it is committed and whether a reader ever sees it is [`docs/reference/repository-layout.md`](docs/reference/repository-layout.md). A directory is created when real code is about to land in it, never ahead of one (section 10).

## 4. Layer and Dependency Boundaries

- `frontend/src/` MUST NOT depend on a runtime backend service - there is none in production. It reads committed files under `frontend/public/` and nothing else.
- `backend/` is the only writer of pipeline output under `frontend/public/`. The site reads only that output.
- `backend/` MUST NOT import frontend code, and frontend code MUST NOT import backend code. They meet only through committed data and generated contracts (Guardrail #1, section 1a).
- `backend/idhazh/contracts/` MUST NOT import any other subpackage of `backend/idhazh/`. Contracts are the bottom of the dependency graph; everything else depends on them.
- Every stage is invocable on its own with a file in and a file out. A stage that can only run as part of the whole pipeline cannot be tested and is a design error.
- Anything fetched from the open web crosses the trust boundary exactly once, at the extraction stage, and is sanitized there (Guardrail #11).

These are boundaries rather than guardrails because each is a structural invariant with one correct side, so there is nothing here to adapt.

## 5. Documentation Discipline

- One concept is defined once; everywhere else links to it.
- ASCII-only in all repo text: commit messages, docs, code comments, log strings, agent markdown, CLI output (use `-`, `->`, `>=`, and "section"). No curly quotes, em-dashes, or non-ASCII symbols.
- **Process docs stay domain-neutral.** Everything under `docs/how-to/` that describes *how work is done*, and `docs/reference/documentation-structure.md`, are written to be copied between projects unchanged: they cite `CLAUDE.md` by section number rather than restating a project-specific rule. A process doc that cannot be stated neutrally says so and names why.
- A decision is recorded IN the living doc it impacts, never as a standalone record. **There is no ADR file and no `decisions/` directory.** Git history is the immutable record of when it changed.
- Open questions live in the active plan-doc under `TODO/`, not in this file.

The tiers, the depth limit, the elements every page carries, the three tests that decide a split, where a benchmark run is written up, and what makes a sentence worth keeping are all in [`docs/reference/documentation-structure.md`](docs/reference/documentation-structure.md).

## 6. Correction Levels

**The level is set by what the change can break, not by how many files it touches.** A one-line edit to a shape somebody already wrote outranks a four-file rename.

| Level | What is true of the change                                              | Workflow                              |
| :---: | ----------------------------------------------------------------------- | ------------------------------------- |
|   0   | It cannot change behaviour - a comment, a typo, a log string            | Direct fix                            |
|   1   | Behaviour changes, and a wrong version is obvious and local             | Direct fix                            |
|   2   | Behaviour changes where something else already depends on it            | Fix, then check the dependants by name |
|   3   | It crosses a boundary - two subsystems, or code and published data      | Plan the order, then execute          |
|   4   | Reverting it later would cost more than writing it                      | Propose the breakdown first           |
|   5   | Core design / a persisted contract / the model pick / the trust boundary | Design consultation only - pause work |

**The level is chosen against the intent, not against the smallest change that would pass** (section 0d).

When in doubt, choose the higher level. Counting files is not the test: four files that cannot break a reader are a Level 1, and one line that changes a shape an earlier run already wrote is a Level 5.

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

What it costs, stated rather than implied: a squash boundary is per-commit, not per-path, so the range it collapses carries `backend/`, `docs/` and `state/` as well as `corpus/`. `git blame` and `git bisect` reach back `prune_keep_days` to `prune_keep_days + prune_every_days` and no further, and a commit SHA older than that stops resolving. A clone taken before a prune has to be re-fetched.

Safe workflow: `git status --porcelain`, leave unrelated dirty files alone, stage only explicit paths, verify with `git diff --cached --name-only`, small reversible commits on a named branch, push, merge after gates pass.

Commit messages describe the change. **No AI co-author / attribution tags.**

## 9. Definition of Done

The commands behind these gates are in [`docs/how-to/run-the-gates.md`](docs/how-to/run-the-gates.md).

- [ ] Tests added/updated at the tier appropriate to the surface (section 13). No mocks per Guardrail #7.
- [ ] Full suite green **on the merge candidate, once**. CI is the authoritative arm and is six to fifteen times faster than a developer box; a local full-suite run before every push is optional, not required. A candidate that is already green does not re-run the suite because the trunk moved under it.
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
- [ ] Any guardrail adapted or excepted in this change carries a person's name and a dated line in the living doc it impacts (section 1).
- [ ] Lockfiles in sync with manifests.
- [ ] Any new performance or quality number carries hardware, date and spread (Guardrail #10).
- [ ] Runner budget respected: no step pushes a job past its timeout, the cache past 10 GB, artifacts past 500 MB, or the published site past 1 GB (Guardrail #2).

## 10. Anti-Patterns (Do NOT)

- Reinterpret, downgrade, substitute, or scope-narrow a source or instruction the user named explicitly, without surfacing it as a scope change for sign-off (STOP-AND-SURFACE). **Declining on a limitation without pricing it is the same thing** - it is scope-narrowing to zero, and section 0d names what is owed instead: do it, price it, or name the measurement that would settle it.
- Assume a backend exists in production.
- Hardcode tunables, source lists, model refs, thresholds, or magic strings. They live in `config/`.
- Ship a surface that is still under development without a config flag, default off, carrying its removal condition on the line that declares it (Guardrail #6).
- Hand-edit a generated artifact (`schemas/*.schema.json`, `frontend/src/contracts/*`). Edit the Pydantic model and regenerate.
- Store absolute / backslash paths in any persisted artifact.
- Let fetched text reach a system prompt, a shell argument, a file path, or an outbound URL (Guardrail #11).
- Build custom HTTP / retry / parsing / validation / extraction systems when a mature OSS library exists.
- Swallow exceptions or silently coerce invalid input - fail fast at the boundary.
- Mock in tests by default, or let any test touch the network.
- Commit a model weight, a downloaded binary, or a reproducible run intermediate.
- Add a runtime telemetry / analytics / error-tracking SDK.
- Ship a feature that depends on a runtime backend, an account, or a push notification.
- Add a framework / library / build tool without naming its cost and its beneficiary feature.
- Quote a throughput, cost or quality number without saying what measured it and when (Guardrail #10). The operator console's counterfactual cost is the one carve-out, and printing it as a bill breaks it.
- Justify a design with an estimate when a measurement is cheap to take.
- Mint a new persisted field without stamping the schema `version` date, appending a `changelog` entry, and writing the read-side migration in the same commit.
- Raise the runner budget to fit a feature. The limits are GitHub's rather than ours, so an agent cannot move them and is not asked to (Guardrail #2) - the required next move is to name the design that does fit and what it traded: fewer items, a smaller model, a shorter context, a shard that splits.
- Let `TODO/`, chat logs, `AGENTS.md`, or a private agent note store become the source of truth for anything. They are caches of `docs/`.
- Make a domain-neutral process doc project-specific (section 5).
- Pre-create empty modules "for later".
- Skip the docs update.

## 11. Schema Versioning

Every config file and every persisted surface is a Pydantic model in `backend/idhazh/contracts/` before logic is written (Guardrail #3, section 1a), and `schemas/<name>.schema.json` is generated from it. Three rules bind every one of them.

- `version` is a `YYYY-MM-DD` date-stamp - never an integer, never an epoch. It answers the question a reader of an old payload actually has: how old is this shape?
- Every change appends a `changelog` entry, newest first, `{ version, change, why }`, and sets `version`.
- A breaking change - a removed field, a retype, a shifted meaning - ships its read-side migration in the same commit. **A payload written by yesterday's run that today's build cannot read is a contract break and a release blocker.**

What the base model enforces, how a same-day revision extends the stamp, which surfaces this covers, and the one model that pins a published key while its Python name moves: [`docs/architecture/contracts/schemas.md`](docs/architecture/contracts/schemas.md).

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

**A test's cost belongs to the code it checks, never to what the pipeline has piled up.** So a test does not walk a collection that a run appends to - the committed days, the telemetry and state shards, the search index, the corpus, or any collection added after this sentence was written (Guardrail #12). A per-item rule is driven from a bounded fixture, and the canary day under `backend/var/canary/` is the one to reach for: it is fixed in size and it can carry a case the archive has never produced. Where a question really is about the whole tree, it is asked once and asserted on the total rather than once per story - and the producer has already validated every payload at write time, so re-checking a frozen day on every later run buys nothing. Where a walk is genuinely the right answer, Guardrail #12's escape hatch applies: say next to the test what it reads and why a fixture cannot answer it. What a walk actually costs, measured: [`docs/concepts/growing-reads.md`](docs/concepts/growing-reads.md).

**A test checks code functionality, not data hygiene, and it is driven with a built parameter rather than a loop.** A check that reads committed data to ask whether the data is well-formed is not a test, whatever file it sits in. It has three legal fates and no fourth: delete it where a fixture-driven test already covers the same rule; move it into the producer that writes the data (the one-picture-one-story rule now lives in `idhazh validate-days`); or make it an operator surface under `backend/utilities/`, which pytest does not run. A scheduled pytest job is not one of the three. Where the awkward shape is the point, that shape is **built**, because a built one also carries the case the archive has never produced. Owner ruling, 2026-09-06.

**A walk over committed data tends to carry a fuse, and that is the second reason to refuse one.** A test that counts how many committed entries still *lack* a new field is timed to go red on the day the last unmigrated payload ages out of retention - a date on the calendar rather than a change anybody made. A read-side migration is proved by removing the key from a fixture, which cannot age out. [`docs/reference/agent-notes.md`](docs/reference/agent-notes.md) records the day one of these fired and took every open pull request red at once.

Per tier:

- **Unit** - pure functions (sanitization, sharding, scoring maths, serialization round-trip).
- **Contract** - the generated schemas vs the readers and the writers, plus the drift gate.
- **Integration** - two or more stages composed against real fixtures, with the model boundary driven by a recorded response where the model itself is not under test.
- **End-to-end** - the pipeline run start-to-finish on a fixture corpus, producing a digest; and the published site rendered in a real browser against that output.

## 14. Agent Roster

Seven persona advisors live under `.github/agents/`, each at a distinct altitude. **This table is the authority assignment, and it is what resolves a stalled debate**: the decision class names who rules.

| Agent                               | File               | Altitude, and the decisions it rules                                          |
| ----------------------------------- | ------------------ | ----------------------------------------------------------------------------- |
| Reader                              | `reader.agent.md`  | the person the digest is for - is it worth their two minutes? is the language plain? does the page work on a slow connection and a small screen? |
| Editor                              | `editor.agent.md`  | what the digest covers and at what length - story selection, where a cut may fall by kind of writing, which themes to trade when a budget binds, whether a source earns its slot |
| Jony (UI and UX)                        | `jony.agent.md`    | the published surface - page and typography, chart vs diagram vs nothing, the eval dashboard, what a visual must earn |
| Susan (Craft and Delight)             | `susan.agent.md`   | whether a surface is good enough to ship - the sufficiency checks, elevation and colour systems, icon and chart craft, both themes, empty and degraded states |
| Andre (AI and LLM)                    | `andre.agent.md`   | model pick on quality grounds, prompt strategy, constrained decoding, eval design and metric choice, the prompt-injection surface |
| Fowler (Architecture and Engineering) | `fowler.agent.md`  | architecture, persisted contracts (stage payloads, eval ledger, run manifest, config, published payloads), schema versioning, test tiers, refactor safety, module structure, when to delete |
| Carmack (Engine and Runtime)          | `carmack.agent.md` | inference runtime, model quantisation and fit, the runner budget, throughput, cache and shard economics, job timeouts |

Adding a new agent requires justifying a distinct altitude not already covered. Two agents at the same altitude collapse into one.

**A veto must name what the reader loses.** A ruling that removes states what is removed *and* what the reader gives up by not having it; a ruling that states only the first is not a ruling and does not bind. This is not a courtesy - it is the price of the authority the table above hands out.

Five pairs share an edge, and each one has a written split.

- Where Reader and Editor both touch content: **Reader reports what reading it was like, Editor rules what should have run and how long.** Reader does not propose; Editor does not speak for the reader's experience of the page.
- Where Jony and Susan both touch the page: **Jony rules what survives on the page, Susan rules whether what survived is good enough to ship.** They are the two halves of one review and neither is sufficient alone. Susan never overrules Carmack on bytes, Reader on plain language, or Editor on what runs.
- Where Carmack and Andre both touch the model: **Andre owns whether a model is good enough, Carmack owns whether it fits.** A model that fails either test is not the pick.
- Where Andre and Carmack both touch injection: **Andre owns the prompt and schema shape, Carmack owns the process boundary** - no model output becomes a shell argument, a file path, or a URL to fetch.
- Where Editor and Andre both touch quality: **Editor names the content failure, Andre chooses the instrument that measures it.**

A persona's own worldview shapes what it says, never how plainly it says it (section 0b).


## See also

- [`README.md`](README.md) - what yen-idhazh is.
- [`docs/agents/bootstrap.md`](docs/agents/bootstrap.md) - which page owns what, and what every answer owes.
- [`docs/how-to/run-the-gates.md`](docs/how-to/run-the-gates.md) - the environment and the commands behind sections 9 and 12.
- [`docs/reference/agent-notes.md`](docs/reference/agent-notes.md) - environment and tool quirks that make a command lie.
- [`docs/reference/documentation-structure.md`](docs/reference/documentation-structure.md) - where each kind of doc lives.
- [`docs/concepts/vision.md`](docs/concepts/vision.md) - what this project is and is not.
- [`docs/concepts/growing-reads.md`](docs/concepts/growing-reads.md) - Guardrail #12's escape hatch: what a read over a growing collection declares, and the inventory as it stands.
