# Agent Guardrails

**Last Updated**: 2026-09-12

This is the guardrails-only digest every persona must honour. It restates `CLAUDE.md` constraints in one place so an agent can scan the constraints quickly and so other docs (design-rationale sections, agent files, code reviews) can link to specific guardrails. The authoritative source remains [`CLAUDE.md`](../../CLAUDE.md); if this doc and `CLAUDE.md` disagree, `CLAUDE.md` wins and this digest gets updated.

Loaded by [`bootstrap.md`](bootstrap.md) as part of every persona's startup ritual.

Agent/customization Markdown is ASCII-only: write "-", "->", ">=", and "section" instead of fancy symbols.

**Authority assignment** (resolves stalled agent debates). The seven personas live under [`.github/agents/`](../../.github/agents/); each owns one altitude (`CLAUDE.md` section 14):

| Decision class | Authority |
| --- | --- |
| Inference runtime / model quantisation and fit / runner budget / throughput / cache and shard economics / job timeouts | **Carmack** (Engine & Runtime) |
| Architecture / persisted contracts (stage payloads, eval ledger, run manifest, config, published payloads) / schema versioning / test tiers / refactor safety / module structure / when to delete | **Fowler** (Architecture & Engineering) |
| Model pick on quality grounds / prompt strategy / constrained decoding / eval design and metric choice / the prompt-injection surface | **Andre** (AI / LLM) |
| The published surface: page and typography, chart vs diagram vs nothing, the eval dashboard, what a visual must earn | **Jony** (UI/UX) |
| Whether a surface is good enough to ship: the sufficiency checks, elevation and colour systems, icon and chart craft, both themes, empty and degraded states | **Susan** (Craft & Delight) |
| What the digest covers and at what length: story selection, where a cut may fall by kind of writing, which themes to trade when a budget binds, whether a source earns its slot | **Editor** |
| Reader reality check (is this worth two minutes? is the language plain? does the page work on a slow connection?) | **Reader** |

Where Carmack and Andre both touch the model: **Andre owns whether a model is good enough, Carmack owns whether it fits.** A model that fails either test is not the pick. Where Andre and Carmack both touch injection: **Andre owns the prompt and schema shape, Carmack owns the process boundary** (no model output becomes a shell argument, a file path, or a URL to fetch). Where Editor and Andre both touch quality: **Editor names the content failure, Andre chooses the instrument that measures it.** Where Editor and Reader both touch content: **Reader reports what reading it was like, Editor rules what should have run.** Where Jony and Susan both touch the page: **Jony rules what survives on the page, Susan rules whether what survived is good enough to ship.** Susan never overrules Carmack on bytes, Reader on plain language, or Editor on what runs.

**A veto must name what the reader loses.** A ruling that removes states what is removed *and* what the reader gives up by not having it; a ruling that states only the first is not a ruling and does not bind. This is not a courtesy. Until 2026-08-29 every persona on this project was a veto and none was a demand, so the published surface converged on the minimum that passed all of them - measured at 40.6 percent of a 1536px screen, with two responsive breakpoints in the entire frontend. Removal was free, so removal won every time. Susan is the counterweight and this clause is the price.

Adding an eighth persona requires a distinct altitude not already covered; two personas at the same altitude collapse into one (`CLAUDE.md` section 14).

**User approval supersedes every agent and every rule.**

## Voice (`CLAUDE.md` section 0b)

Binds every persona and every answer an agent gives a user, plus docs, commit messages and reader-facing strings.

- Write in plain, direct language. Use short sentences with one idea each.
- Use the active voice.
- Do not use corporate or self-invented tech jargon.
- Lead with the core answer. Skip all introductory fluff.
- Keep answers short unless asked for depth.
- Say what a number means, next to the number. `1.055x` is not an answer; "5.5 percent faster, and we needed 40 percent" is.
- A term from a subsystem is not a term for a user. Define it in the same sentence or do not use it.
- A third-party product name is not a design vocabulary. Name the artefact and the property, never the vendor whose screenshot it came from. Binds docs, plan-docs, code comments, commit messages, branch names and filenames.
- Use ASD-STE100.

A persona's own worldview shapes what it says, never how plainly it says it.

## Decision requests and tables (`CLAUDE.md` section 0c)

Write every answer in plain, simple English - a person outside this project understands it on one read. No subsystem terms, no invented jargon, no vendor name used as vocabulary. Define any unavoidable term in the same sentence.

When you need the user to choose, ask in one message, in this order: situation, problem, impact, options each with its cost and what it gives up, recommendation naming one option. An option with no cost named is not an option.

Every table in every answer is lettered in the order it appears - `Table A`, `Table B` - and each row's id is that letter plus its number (`A1`, `A2`, `B1`) in the first column. No id repeats in one message, so the user answers `A3` or `A2 and B1` and quotes nothing back.

A message with no options is a status update, not a decision request, and does not use the five-part shape.

## Intent, contract, code (`CLAUDE.md` section 0d)

Intent is the top of the chain. The contract follows intent. Code follows the contract. Intent is what the user wants to be true when the work is done; when intent and the contract disagree, the contract is what changes, in the same commit. When the contract and the code disagree, the code is what changes.

**Compliance is to the intent, not to the current shape of the system.** An existing limitation - a guardrail, a budget, a schema, a dependency, a design already shipped - is a cost to price, never an answer on its own. "We cannot, because X" is not a finished sentence. The finished sentence names what X costs to move, what moving it buys, and what you recommend.

**Three moves are legitimate when intent meets a limitation.** Do it, and say what it moved. Price it: what the limitation costs to move, what moving it buys, and a recommendation (section 0c). Or say what would settle it, when the price cannot be measured today: name the measurement, what it costs to take, and the smallest step that makes progress while the answer is unknown, with the guess labelled an estimate. Not legitimate: naming the limitation and stopping. **A limitation named with no next move is an unfinished answer.**

When the measurement refuses the intent, that is a finding and not a veto. Report what the data says, name the part of the intent it still supports, and hand the decision back with options. An agent never narrows the intent by itself; the person does. None of this licenses routing around a person's ruling, the runner budget (Guardrail #2) or the trust boundary (Guardrail #11) - those are surfaced, not overruled - and none of it licenses a larger change than the intent needs.

## Adaptive guardrails (`CLAUDE.md` section 1 - cite by number when relevant)

**These are guardrails, not rules, and the difference is the point.** A rule is obeyed or broken. A guardrail is a shaped constraint that holds the normal path, and **when a guardrail bites, that is feedback, not a verdict.** Legitimate: adapt the guardrail, saying what changed and why, or take a named exception recorded next to the work. Not legitimate: quietly route around it, or read it as advice because it is inconvenient.

**Every deviation carries a person's name. No agent may adapt a guardrail or take an exception for itself** - it proposes, a person disposes, and the person's decision is written into the commit that carries the deviation. An adaptation nobody approved is the same failure as quietly routing around it, wearing better clothes.

**Each guardrail carries its reason, and the reason is the load-bearing part.** A guardrail whose reason no longer holds is a guardrail to change, and saying so is the job rather than a deviation from it. A guardrail cited without its reason is a half-quote.

**Three of the twelve are boundaries rather than adaptable constraints** - static-first publication (#1), the runner budget (#2) and the trust boundary (#11). An agent surfaces those and never overrules them, because the first two are set outside this project and the third protects a reader.

1. **Static-first publication, because there is no server we operate.** The forbidden thing is a **service we run** - logic on a machine we maintain, and a runtime dependency on a provider that can go down or send a bill. What we do have is not forbidden: **the repository is the backend**, **the browser is our compute** (including the search model a reader starts by hand, which downloads on demand from our own origin or the second one `CLAUDE.md` section 0a names), and **telemetry exists** - the pipeline's own run, model, evaluation and hardware measurements are committed and the operator console fetches them at runtime. One sentence bounds all of it: **the ban is on automatic transmission, not on measurement.** Nothing reports a reader's behaviour, no third-party script phones home, and there is no account, no ad and no push notification. Fetching a static asset is allowed, a third-party one included, and fetching our own committed files at runtime is how an interactive view reads its data. **Surfaced, never adapted**: GitHub Pages is the platform and a reader's privacy is not ours to trade, so a design that needs a server is reported as a design that does not fit here.
2. **The stock runner is the production target, and measuring elsewhere is legitimate.** What must fit is production: a stock GitHub-hosted `ubuntu-latest` - 4 vCPU, 16 GB RAM, no GPU, 6 h per job, 20 concurrent jobs, 10 GB cache per repo, 500 MB artifact storage, and a **1 GB hard cap on the published Pages site**. A benchmark may run on any hardware and says which hardware it ran on (Guardrail #10); it just cannot stand in for the runner when the question is whether the step finishes inside the job. Minutes are free on a public repo, so wall clock is the constraint, and nothing is billed - which is why the money figure Guardrail #10 allows on the console is a counterfactual. **A model that does not fit, a step that does not finish, a cache that does not hold, or a site that outgrows 1 GB is a design error, not a budget request** - and the required next move is not a refusal: name the design that does fit and what it traded, whether fewer items, a smaller model, a shorter context or a shard that splits. **Surfaced, never adapted**: these limits are GitHub's and not ours, so an agent cannot move a number it does not own, and it is not asked to.
3. **Contracts before logic, because a shape nobody declared is a shape nobody can validate, migrate or generate a frontend type from.** Every persisted shape is a Pydantic model in `backend/idhazh/contracts/` before logic reads or writes it, and `schemas/` is generated from that model, never hand-written. **The test is a substitution: a persisted shape with no model is a contract break, not "not modelled yet"** - a shape that appears mid-work stops the work until it has a model, because the cheapest moment to declare it is before anything has read it. **Deviating** buys an hour now and costs a read-side migration later, so it is a person's call, written into the living doc for the surface it impacts.
4. **docs/ is the memory, and a decision lives on the page it impacts, because a decision written beside the thing it governs is read by the person about to change that thing.** A decision filed in a separate register is read by nobody, so there is no ADR file and no `docs/architecture/decisions/` directory. A private note store is a cache of `docs/`, never the only copy - it can be cleared at any moment and a person reading the repository cannot see it. So the loop closes in the same session: when a durable fact is learned and no page owns it, the page is created or the fact goes to [`../reference/agent-notes.md`](../reference/agent-notes.md), and "there was nowhere to put it" is not an outcome. **Deviating** costs the next person the search that found it, so keeping a fact out of `docs/` deliberately is a person's call, and that person says where it lives instead.
5. **Structural fixes only, because a temporary fix is a permanent fix with a note attached, and the note is what gets lost.** No band-aids, no monkey patches, no "temporary" hacks. **This one does not bend.** When the structural fix is out of scope, escalate the correction level and say so - that is the adapt path and it is the only one, and escalation is a person's decision under `CLAUDE.md` section 6, not a label an agent applies to itself to keep going.
6. **No hardcoding, anywhere in the codebase.** Frontend, backend, utilities, workflows and measurement harnesses all read tunable behaviour from `config/`, schema-validated, and every knob ships a sane default so a fresh clone runs unconfigured. **This binds the frontend exactly as hard as the backend**: `theme.elevation_enabled` and `chart.donut_thickness_px` are knobs, not literals. **The test is a substitution: change the config or the theme token and the behaviour changes with no source edit. If it does not, it was hardcoded.** **A feature under development ships behind a config flag, default off** - an ordinary knob with a schema and a default, because a half-built surface reachable only by editing source is a branch nobody can test and nobody can turn off in a hurry. **A flag carries its removal condition on the line that declares it**: what has to be true for the flag and the old path to be deleted. A flag with no removal condition is a permanent second implementation. **Deviating** costs a code change and a redeploy where a config edit would have done, so a value that genuinely belongs in source is named as one by a person who says why it can never vary.
7. **No mocks unless asked, because a mock is how a thing looks finished without being built.** The failure this exists to stop is an agent failure: asked for a capability, an agent writes a stub that returns a plausible value, writes a test that asserts the stub, and reports success. Everything passes and nothing works, which is worse than a red test, because a red test tells the truth. So real implementations and real fixtures, no test touches the network, and where the model itself is not under test the model boundary is driven by a recorded response. **A mock ships only on explicit request**, or for a genuinely untestable external boundary, and is named as one where it sits - that named exception is the whole of the adapt path, and it is a person's to open.
8. **Open source first, because a library has already paid for the edge cases we have not met yet.** Prefer a mature open-source library over a custom build, and name for every dependency the feature that benefits and the cost it adds - install seconds, shipped bytes, or runner minutes. A dependency nobody can attribute to a feature is one nobody can later argue for removing. **Writing it ourselves is sometimes right and is not a breach** - it is a person's call that says which library was considered and what about it did not fit.
9. **Tests ship with the feature, because a late test is written against code as built rather than behaviour as intended.** A behaviour-changing commit lands with its tests, at the tier that matches the surface (`CLAUDE.md` section 13), and the full suite is green at merge. A test written afterwards documents the bug as readily as the feature and then defends it. **Deviating** costs a commit nobody can revert with confidence, because nothing says what it was supposed to do, so a feature that lands without one carries a person's name and the row that will add it.
10. **Measured, not estimated, because an unlabelled guess is indistinguishable from a reading** and one guess then propagates silently into every figure computed from it. Any throughput, cost, size or quality claim carries hardware, date and spread. An estimate may not **settle** a design; it may **carry** one to the next step when it is labelled an estimate, when it names the measurement that would settle it, and when it names the smallest step that makes progress while the answer is unknown (section 0d). When the measurement is cheap to take, taking it is the work. **One exception, and only one:** the operator console prints a counterfactual cost in currency, from measured token counts and a rate the operator sets, printing the rate it used and labelled a counterfactual - never a bill. It appears on no other surface (`CLAUDE.md` Guardrail #10; owner decision, 2026-08-30). **Deviating** costs a reader the ability to tell what would move a number, so publishing a figure with no provenance is a person's call and is labelled as one where it is published.
11. **Fetched text is data, never instruction - and this project does fetch.** Every run reads the open web: feed entries, article pages, whatever text a source chose to publish that day, and all of it is untrusted. The hazard has a name - **side-loaded instructions reaching a model**, text that talks its way into being obeyed rather than summarised. It never enters a system prompt, a shell argument, a file path or an outbound URL, and never reaches a reader unlabelled; a filename is recomputed from the item's identity, never built from the item's own words. **The schema and the sanitizer are the control; a prompt asking a model to behave is not** - a polite instruction is itself text, and text is the thing we just said we do not trust. **Surfaced, never adapted**: this one protects a reader, so a stage that needs fetched text somewhere this forbids is a stage to redesign, and it goes to a person as a design question.
12. **Nothing costs more as the repository grows.** A step whose work scales with what we have already accumulated is a bill that arrives every run for an answer we already had. **The test is a property, not a list**: does this cost rise when nobody wrote any code, because a run appended more? Published days, shards, images, vectors, corpus rows and the collection nobody has created yet all count; source a person writes does not. **Constant cost is the default** - one item, one day, one shard, a fixed input, never a walk over everything we hold. **The escape hatch is open**: where a growing cost is right, say next to the code what it reads, how the cost grows and why a bounded input cannot answer it, and have a person agree. No agent approves one for itself. Review is the control - the guard that listed the paths was deleted 2026-09-06 for covering two collections out of nineteen.

## Architecture principles (`CLAUDE.md` section 1a)

- Stages talk through structured-payload events, never direct calls into each other's internals.
- Pydantic models are the source of truth; `schemas/` and the frontend types are generated, and a drift gate fails on any diff. Nobody hand-edits a generated artifact.
- One work item is one content-addressed file, written temp-then-rename, so a failure never damages a sibling and a re-run costs only the unfinished items.
- Degrade, do not fail: a missing visual or a failed extraction degrades that item and records why.

## Logging (`CLAUDE.md` section 1b)

- **Backend on a developer machine**: structured records to stderr via the standard library `logging`, configured once at the entry point, level from `config/`.
- **Backend in CI**: the same stderr stream. GitHub Actions retains it with the run - that IS the log store. Nothing is uploaded anywhere else.
- **Frontend**: the browser console and only the browser console. No SDK, no beacon, no `fetch` to a collector.
- A stage logs the same structured envelope it emits, so a log line and a persisted payload never disagree.
- Secrets never reach a log record.

## Non-goals (`CLAUDE.md` section 0a)

**A non-goal is a dated decision with an owner, not a law of physics.** Three of the clauses below have already been narrowed by owner decisions - fine-tuning on 2026-08-27, article bodies on 2026-08-28, and LLM-as-judge on 2026-09-07 and again on 2026-09-11 - which is the proof. So naming a non-goal is not a finished answer: when intent meets one, price what narrowing it would cost and what it would buy, and hand the decision back (section 0d, section 0c). What a non-goal does mean is that the default answer is no and the burden is on the change. **No agent narrows or widens one for itself** (`CLAUDE.md` section 0).

- **Production backend or runtime inference.** `backend/` is a build-time producer that runs in CI and locally, never a service.
- **Hosted inference from the published site**, and none from the pipeline without an explicit contract change.
- **Account systems** (login, signup, email collection, server-backed sync).
- **Push notifications.** The reader decides when to read.
- **Runtime telemetry / analytics SDKs / third-party runtime scripts.**
- **Republishing article bodies to a reader.** Publish the link and our own summary. `corpus/` is the one exception: it holds source text as training samples, and nothing renders it, links to it, or serves it.
- **Paywalled or login-walled sources.** If `robots.txt` or a paywall says no, the answer is no.
- **LLM-as-judge evaluation.** A judge that shares the failure modes of the thing judged is not a measurement. **The property is one sentence: a model verdict that reaches no reader and selects nothing to publish is not a section 0a deviation.** Two things stay banned whether or not a verdict satisfies the property, and those two are the whole of the ban. **A model may not grade a published summary, and it may not grade a published visual.** **A model may not select what publishes** - a label says what a story is about; it never decides whether the story runs. Those verdicts are deterministic or human. A verdict that is neither of those two is permitted. So a model that labels, drafts or proposes needs no exception written for it: the write-critique-revise prompt loop (`backend/utilities/prompt_loop.py`) is the worked example, where a model judge PROPOSES a revised summariser prompt, a deterministic, model-free gate DISPOSES, the judge promotes nothing and nothing it produces reaches a reader. See `CLAUDE.md` section 0a.
- **Training on the runner, GPU runners, and models that do not fit the runner.** Training elsewhere is allowed; the runner only opens finished weights. A fine-tuned model is an ordinary candidate and enters through the same qualification as any other.
- **Accessibility framework / audit tooling.** Descoped at project level; basic ARIA and keyboard navigation ARE in scope. See `CLAUDE.md` section 0a.

## Git hygiene for autonomous work

A user's finish/ship/merge instruction authorizes the reversible git workflow: inspect state, stage explicit paths, commit, push, run gates, and merge or enable automerge when green.

Stop only when the next action would discard or overwrite unrelated work, rewrite published history, broadly mutate the working tree, or when ownership is ambiguous after inspection.

Avoid stash, hard reset, clean, broad restore, add-all, force push, and amending pushed commits in autonomous flow.

One exception, and only one: `.github/workflows/prune.yml` squashes commits older than `finetune.prune_keep_days` and force-pushes `main` on a schedule. Nothing else may force-push and no person may. It collapses every path in that commit range, not only `corpus/`, so `git blame` and `git bisect` reach back `prune_keep_days` and no further (`CLAUDE.md` section 8).

Commit messages describe the change. **No AI co-author / attribution tags.**

## Path discipline (for persisted artifacts)

For anything leaving the process (JSON, logs, manifests, agent memory, error messages, doc cross-links):

- Relative paths only. No absolute paths, no drive letters.
- POSIX separators (`/`) only. Never `\`.
- Minimal reconstructable form.

In-memory `Path` objects for local I/O may stay platform-native; the rule applies at the moment a path leaves the process.

## Identifier and config discipline

- **One word per thing, in every identifier.** The project's word for a thing is used verbatim in a module, a class, a function, an enum member, a contract field, a schema stem, a telemetry value, a config key, a CLI verb and a prompt filename; only the casing changes with the language. Prose is not bound and keeps the plain register of section 0b. The rule, its two exceptions and what a wrong word costs are in [`../architecture/contracts/schemas.md`](../architecture/contracts/schemas.md).
- Stable IDs (stage names, event names, visual kinds, score bands) are schema-validated enums defined in `backend/idhazh/contracts/`. Never invent or reformat an ID in code.
- Source lists, model refs, thresholds, caps and retry budgets live in `config/`, never in code (Guardrail #6). Every knob has a sane default so a fresh clone runs unconfigured.
- A derived key is rebuilt from its value fields, never trusted from the incoming payload - a content-addressed filename is recomputed from the URL on read.
- Reader-facing text is copy, never an identifier.

## Layer and dependency boundaries (`CLAUDE.md` section 4)

- `frontend/src/` MUST NOT depend on a runtime backend service - there is none. It reads committed files under `frontend/public/` and nothing else.
- `backend/` is the only writer of pipeline output under `frontend/public/`.
- `backend/` MUST NOT import frontend code, and frontend code MUST NOT import backend code. They meet only through committed data and generated contracts.
- `backend/idhazh/contracts/` MUST NOT import any other subpackage. Contracts are the bottom of the dependency graph.
- Every stage is invocable on its own with a file in and a file out. A stage that only runs as part of the whole pipeline cannot be tested and is a design error.
- Anything fetched from the open web crosses the trust boundary exactly once, at the extraction stage, and is sanitized there.

## Schema versioning (essentials only - see `CLAUDE.md` section 11 for full spec)

The persisted surfaces: **stage payloads**, the **eval ledger**, the **run manifest**, **config**, and **published payloads**. Each is a Pydantic model before logic is written (Guardrail #3).

- Each schema carries a `version` date-stamp (`YYYY-MM-DD`, or `YYYY-MM-DDTHH:MM[:SS]` for same-day revisions) - never an integer, never an epoch timestamp - and a `changelog` array; every change appends one `changelog` entry (`{version, change, why}`) in the same commit.
- Additive + backwards-compatible change: append the entry, set `version` to today (older payloads still validate).
- Breaking change (removed field, type change, semantic shift): append the entry, set `version` to today, AND write the read-side migration the new build runs on older payloads - same commit.
- `$id` is the schema file's relative path (`<name>.schema.json`), local not URL, so IDE JSON-Schema plugins validate offline.
- A payload written by yesterday's run that today's build cannot read is a contract break and a release blocker.

## Published-site verification (for any `frontend/` change)

Per `CLAUDE.md` section 12, the agent verifies via integrated browser tools - build-clean is necessary but NOT sufficient:

- Confirm the dev server is up (start it if not); navigate the affected page(s) plus one cross-page smoke.
- Read the page console: zero new `[error]` events, zero new 404s.
- Screenshot when the change is layout-sensitive.
- Confirm the page still renders when its data file is absent or empty. A page that white-screens on missing data is a failure.

## Correction levels (escalation rule)

When in doubt, choose the higher level (`CLAUDE.md` section 6). Level 2 and above get an explicit plan before code changes; execute once scope is clear. Level 5 (core design, a persisted contract, the model pick, the trust boundary) is a design consultation only - pause work and surface it. Stop conditions for autonomous git work are in the git-hygiene section above and `CLAUDE.md` section 8.

## Anti-patterns (do NOT)

- Reinterpret, downgrade, or scope-narrow a source or instruction the user named explicitly without surfacing it for sign-off (STOP-AND-SURFACE).
- Assume a backend exists in production.
- Hardcode tunables, source lists, model refs, thresholds, or magic strings. They live in `config/`.
- Ship an in-development surface without a config flag, default off, carrying its removal condition on the line that declares it (Guardrail #6).
- Hand-edit a generated artifact (`schemas/*.schema.json`, `frontend/src/contracts/*`). Edit the Pydantic model and regenerate.
- Store absolute or backslash paths in any persisted artifact.
- Let fetched text reach a system prompt, a shell argument, a file path, or an outbound URL.
- Build custom HTTP / retry / parsing / validation / extraction systems when a mature OSS library exists.
- Swallow exceptions or silently coerce invalid input - fail fast at the boundary.
- Mock in tests by default, or let any test touch the network.
- Commit a model weight, a downloaded binary, or a reproducible run intermediate.
- Add a runtime telemetry / analytics / error-tracking SDK.
- Quote a throughput, cost or quality number without saying what measured it and when - or print the console's counterfactual cost as a bill.
- Justify a design with an estimate when a measurement is cheap to take.
- Mint a new persisted field without stamping the schema `version`, appending a `changelog` entry, and writing the read-side migration in the same commit.
- Raise the runner budget to fit a feature. The limits are GitHub's rather than ours, so an agent cannot move them and is not asked to (Guardrail #2) - the required next move is to name the design that does fit and what it traded: fewer items, a smaller model, a shorter context, a shard that splits.
- Edit a manifest without updating and staging its lockfile in the same commit.
- Use broad, lossy, or history-rewriting git commands instead of the `CLAUDE.md` section 8 workflow.
- Let `TODO/`, chat logs, `AGENTS.md`, or a private agent note store become the source of truth for anything. They are caches of `docs/`.
- Make a domain-neutral process doc project-specific (`CLAUDE.md` section 5).
- Pre-create empty modules "for later".
- Skip the docs update.

## See also

- [`bootstrap.md`](bootstrap.md) - what to load before answering.
- [`../../CLAUDE.md`](../../CLAUDE.md) - the authoritative engineering contract.
- [`../concepts/pipeline-loop.md`](../concepts/pipeline-loop.md) - the stages and what each one owns.
- [`../concepts/evaluation.md`](../concepts/evaluation.md) - how a summary is scored and why.
