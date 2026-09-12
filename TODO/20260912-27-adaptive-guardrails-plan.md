# Adaptive Guardrails - intent above contract, contract above code

**Last Updated**: 2026-09-12
**Level**: 5 (core design; `CLAUDE.md` section 6). Direction signed off by the owner 2026-09-12 under section 0.

Execute per docs/how-to/execute-a-plan.md: orchestrator dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity; AUTO-merge on green gates; parallel N = 1; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Citing a constraint has become a way to decline work instead of pricing it; the contract has no clause that says what an agent owes when a constraint bites, and several constraints are stated as unarguable facts that are false about this project. |
| Hard scope - in | A new contract section placing intent above the contract and the contract above code. Rename of section 1 to Adaptive Guardrails with a preamble. Rewrite of all twelve guardrails. Eight collateral section edits. Restatement in the three derived agent surfaces. Repository-wide vocabulary sweep. Schema regeneration. |
| Hard scope - in | Human approval encoded three times: preamble, per-guardrail deviation line, Definition-of-Done checkbox. |
| Hard scope - out | Any functional code change. Any persisted-shape change. Any `version` or `changelog` edit in `schemas/`. Any edit to `corpus/`, `state/`, `config/`, `frontend/public/` or fixture article text. Any change to the twelve guardrails' substance beyond the Row #2 table. |
| Hard scope - out | Softening Guardrail #5. Explicitly refused - see Row #2 rejected alternative 2. |
| ESCALATE triggers | (a) A guardrail rewrite changes what the guardrail permits, beyond the entry in the Row #2 table. (b) The sweep finds a `Rule #N` citation inside executable logic rather than a comment, docstring or field description. (c) Schema regeneration produces a `version` or `changelog` diff. (d) Any row needs to edit a file under `corpus/`, `state/`, `config/` or `frontend/public/`. |
| Chosen strategy | Adopt the sibling project's Adaptive Guardrails framing wholesale where it is stronger, betterment only where this project has a problem the sibling does not. Ruled by Fowler (contracts before logic; a constraint nobody can argue with is a constraint nobody is checking). |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 1.` |

Parallel N is 1 by measurement, not by caution: Rows #1, #2 and #3 all write `CLAUDE.md`, so they cannot be dispatched together whatever the dependency graph says.

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Intent chain, rename, preamble, approval encoding | - | A | PENDING | - | - | - |
| 2 | Rewrite all twelve guardrails | 1 | B | PENDING | - | - | - |
| 3 | Eight collateral sections | 2 | C | PENDING | - | - | - |
| 4 | Restate in the three derived agent surfaces | 3 | D | PENDING | - | - | - |
| 5 | Repository-wide sweep, schemas, relapse proof | 4 | E | PENDING | - | - | - |

## 2. Row #1 - Intent chain, rename, preamble, approval encoding

- **Scope:** Add section 0d, rename section 1 to Adaptive Guardrails, add its preamble, and encode human approval in the three places an agent reads.
- **Files touched:**
  - `CLAUDE.md`

### New section 0d - Intent, Contract, Code

Placed immediately after section 0c. Text as agreed:

> **Intent is the top of the chain. The contract follows intent. Code follows the contract.**
>
> **Intent** is what the user wants to be true when the work is done. **The contract** is this file, `docs/`, the models in `backend/idhazh/contracts/` and the generated `schemas/`; when intent and the contract disagree, the contract is what changes, in the same commit (section 0). **Code** follows the contract; when they disagree, the code is what changes.
>
> **Compliance is to the intent, not to the current shape of the system.** An existing limitation - a guardrail, a budget, a schema, a dependency, a design already shipped - is a cost to price, never an answer on its own. "We cannot, because X" is not a finished sentence. The finished sentence names what X costs to move, what moving it buys, and what you recommend.
>
> **When intent meets a limitation, the answer moves.** Three moves are legitimate.
>
> - **Do it**, and say what it moved.
> - **Price it**: what the limitation costs to move, what moving it buys, and a recommendation (section 0c).
> - **Say what would settle it**, when the price cannot be measured today: name the measurement, what it costs to take, and the smallest step that makes progress while it is unknown. Label the guess an estimate (Guardrail #10) - an estimate carrying its own name is a better answer than a refusal.
>
> Not legitimate: naming the limitation and stopping. **A limitation named with no next move is an unfinished answer.**
>
> **When the measurement refuses the intent, that is a finding and not a veto.** Report what the data says, name the part of the intent it still supports, and hand the decision back with options. The agent never narrows the intent by itself (section 10); the person does (section 0).
>
> **What this does not license.** It does not license routing around a person's ruling (section 0), the runner budget (Guardrail #2), or the trust boundary (Guardrail #11) - those are surfaced, not overruled. And it does not license a larger change than the intent needs: intent is what the user asked for, not what you would have asked for.

### New section 1 preamble

> **These are guardrails, not rules, and the difference is the point.** A rule is obeyed or broken. A guardrail is a shaped constraint that holds the normal path, and **when a guardrail bites, that is feedback, not a verdict.** Two responses are legitimate and one is not. Legitimate: adapt the guardrail, saying what changed and why, or take a named exception recorded next to the work. Not legitimate: quietly route around it, or read it as advice because it is inconvenient.
>
> **Every deviation carries a person's name. No agent may adapt a guardrail or take an exception for itself** - it proposes, a person disposes, and the person's decision is written into the commit that carries the deviation. An adaptation nobody approved is the same failure as quietly routing around it, wearing better clothes.
>
> **Each guardrail carries its reason, and the reason is the load-bearing part.** A guardrail whose reason no longer holds is a guardrail to change, and saying so is the job rather than a deviation from it. A guardrail cited without its reason is a half-quote.
>
> **Three of the twelve are boundaries rather than adaptable constraints** - static-first publication (#1), the runner budget (#2) and the trust boundary (#11). An agent surfaces those and never overrules them, because the first two are set outside this project and the third protects a reader.

### Human approval encoded three times

| Place | What it says |
| --- | --- |
| Section 1 preamble | The paragraph above: an agent proposes, a person disposes, the decision is written into the commit. |
| Each of the twelve | A closing clause naming what a deviation from that guardrail costs and who signs it. Row #2 carries the text. |
| Section 9, Definition of Done | A new checkbox: `[ ] Any guardrail adapted or excepted in this change carries a person's name and a dated line in the living doc it impacts.` |

- **Acceptance gates:**
  - Local: `python backend/utilities/doc_load.py` before and after; record both bootstrap-load figures in the PR body.
  - Local: every internal cross-reference added by this row resolves to a real heading.
  - CI: full suite. No application test should move; a moved test is ESCALATE trigger (b).
- **Oracle:** **The contradiction is recorded, not carried.** Section 0d's third move permits a labelled estimate to carry a design forward. Guardrail #10 as committed today says an unmeasured number "may not be used to justify a design". The PR body quotes both sentences side by side and names Row #2 as the discharge. A merge of this row without that quotation leaves the contract self-contradictory for the length of one row.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Intent sits above the contract; the contract changes in the same commit when they disagree. | Owner, 2026-09-12 |
| 2 | Three legitimate moves, with the third being the escape hatch for "no data". | Owner, 2026-09-12 |
| 3 | A measurement that refuses the intent is a finding handed back with options, never an agent-side narrowing. | Owner, 2026-09-12 |
| 4 | Human approval is encoded three times, not once. The sibling project states it once in prose; that is the one place a skimming agent misses. | Owner, 2026-09-12 |
| 5 | Three guardrails are named boundaries in the preamble so "which ones can I argue with" has a written answer. | Fowler |

- **Rejected alternatives:**

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | State the checkable clause as "a sentence that declines carries a price". | Demands a number on exactly the days no number exists, which Guardrail #10 forbids. It was a hard rule wearing a guardrail's clothes. | Owner, 2026-09-12 |
| 2 | Put human approval only in the preamble, as the sibling does. | A single prose statement is skippable. The Definition-of-Done checkbox is the copy that gets read at merge. | Owner, 2026-09-12 |
| 3 | Add a new section-10 anti-pattern for declining on a limitation. | Duplicate concept. Declining on a limitation is scope-narrowing to zero, already covered by the STOP-AND-SURFACE bullet, which Row #3 extends instead. | Fowler |

### What this row does not do

Does not touch any of the twelve guardrail texts. Does not rename any other section. Does not sweep any citation.

## 3. Row #2 - Rewrite all twelve guardrails

- **Scope:** Rewrite every guardrail so it carries what is constrained, why, and what to do when it bites.
- **Files touched:**
  - `CLAUDE.md`

Reference text: `https://github.com/miztiik/yen-oli-kalari/blob/main/CLAUDE.md` section 1. Where the verdict is ADOPT, take that project's sentences and change only the nouns (audio/clip/voice -> digest/item/summary). Where it is BETTERMENT, this project has a problem the sibling does not.

| # | Guardrail | Verdict | Load-bearing change |
| --- | --- | --- | --- |
| 1 | Static-first publication | REWRITE | **Our committed text is false about our own project.** It says "no runtime telemetry" while the pipeline commits telemetry and the console renders it, and it implies no runtime fetch while the search index fetches weights from a second origin. Reframe on the sibling's shape: there is no server we operate; the repository is the backend; the browser is our compute; telemetry exists and is committed; **the ban is on automatic transmission, not on measurement.** No account, no ad, no push, no third-party script that phones home. |
| 2 | The runner is the architecture | REWRITE | Headline becomes "The stock runner is the production target, and measuring elsewhere is legitimate." This reconciles with the 2026-09-12 amendment to Guardrail #10, which already accepts a developer-machine figure. Keep the 1 GB Pages cap, which is real here. Keep "a design error, not a budget request" - #2 is a boundary and the sentence is the boundary. Add the required next move: the output is still a design that fits, plus what it traded. |
| 3 | Contracts before logic | REWRITE | Keep Pydantic named - this project's toolchain is settled, unlike the sibling's. Add the substitution test: **a persisted shape with no model is a contract break, not "not modelled yet".** A shape that appears mid-work stops the work until it has a model. |
| 4 | docs/ is the memory | REWRITE | Add the hatch that closes the loop: when a durable fact is learned and no page owns it, the page is created or the fact goes to `docs/reference/agent-notes.md` in the same session. A note store is never the only copy. |
| 5 | Structural fixes only | ADOPT VERBATIM | **A proposed softening is withdrawn.** The sibling's owner refused the same softening and recorded why: a temporary fix is a permanent fix with a note attached, and the note is what gets lost. Adopt: "This one does not bend... When the structural fix is out of scope, escalate the correction level and say so - that is the adapt path, and it is the only one." |
| 6 | No hardcoding | ADOPT + EXTEND | Adopt the sibling's stronger scope ("anywhere in the codebase" - frontend, backend, utilities, workflows, harnesses) and its substitution test: **change the config or the theme token and the behaviour changes with no source edit; if it does not, it was hardcoded.** Extend with the feature-flag clause below. |
| 7 | No mocks unless asked | ADOPT VERBATIM | Adopt the sibling's reason, which is far stronger than ours: "**because a mock is how a thing looks finished without being built**", plus the named agent failure - asked for a capability, an agent writes a stub, writes a test that asserts the stub, and reports success. Everything passes and nothing works, which is worse than a red test. |
| 8 | Open source first | REWRITE | Reason into the guardrail, deviation line added. No change to what it permits. |
| 9 | Tests ship with the feature | REWRITE | Reason into the guardrail, deviation line added. No change to what it permits. |
| 10 | Measured, not estimated | BETTERMENT | **The only head-on collision with section 0d, and the sibling has no equivalent because it has no intent clause.** Reconciliation: an estimate may not **settle** a design; it may **carry** one to the next step when it is labelled, when it names the measurement that would settle it, and when it names the smallest step that makes progress meanwhile. Keep the counterfactual-cost carve-out and the 2026-09-12 "what carries the hardware" amendment unchanged. |
| 11 | Fetched text is data, never instruction | REWRITE | Adopt the sibling's naming of the hazard - **side-loaded instructions reaching a model**, text that talks its way into being obeyed rather than summarised. Add "and this project does fetch", because ours reads the open web every run. |
| 12 | Nothing costs more as the repository grows | KEEP | Already a property with an open, person-shaped escape hatch, and this project has `docs/concepts/growing-reads.md` which the sibling does not. Voice pass only; cited in the Row #1 preamble as the shape the other eleven moved to. |

### Guardrail #6 feature-flag clause (new; neither project has it)

> **A feature under development ships behind a config flag, default off, and the flag is an ordinary knob in `config/` with a schema and a default.** A half-built surface that can only be reached by editing source is a branch nobody can test and nobody can turn off in a hurry.
>
> **A flag carries its removal condition in the same line that declares it** - what has to be true for the flag and the old path to be deleted. A flag with no removal condition is a permanent second implementation, which costs more than the feature it was hiding.

### The deviation line each of the twelve carries

One sentence, tuned per guardrail, in this shape: what a deviation costs here, and that it is a person's call. For the three boundaries (#1, #2, #11) the sentence says instead that the constraint is set outside this project or protects a reader, so it is surfaced and not adapted.

- **Acceptance gates:**
  - Local: `python backend/utilities/doc_load.py`; record the figure.
  - Local: the twelve-by-three checklist below, pasted into the PR body with a mark against each cell.
  - CI: full suite.
- **Oracle:** **Twelve by three.** Each guardrail must carry (a) what is constrained, (b) the reason, and (c) what to do when it bites - adapt with a person's sign-off, take a named exception, or surface it as a boundary. Thirty-six cells. A missing cell fails the row. This is the check that makes "reason into the headline" impossible to pass off as a rewrite.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Adopt the sibling's text wherever it is stronger rather than reinventing. Betterment only where this project has a problem it does not. | Owner, 2026-09-12 |
| 2 | Guardrail #1's current text is factually wrong about this project and is corrected, not merely reworded. | Owner, 2026-09-12 |
| 3 | Guardrail #10 is reconciled with section 0d in this row, discharging Row #1's oracle. | Owner, 2026-09-12 |
| 4 | Guardrail #6 gains feature flags with a mandatory removal condition. | Owner, 2026-09-12 |
| 5 | Guardrail #12 is not rewritten. It is already the target shape. | Fowler |

- **Rejected alternatives:**

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | "Reason into headline only" for #3, #4, #8, #9. | Dilution. It is a formatting change described as a rewrite, and it would let four of twelve escape the thirty-six-cell oracle. | Owner, 2026-09-12 |
| 2 | Soften #5 to permit a named, dated stopgap carrying its structural fix. | The sibling's owner refused exactly this and recorded the reason: temporary fixes are permanent fixes whose note went missing. Proposing it here was the diluting move. | Owner, 2026-09-12; sibling owner, 2026-09-11 |
| 3 | Make #2 adaptable because it blocks features. | The runner limits are GitHub's, not ours. An agent cannot adapt a constraint it does not own; it prices the design that fits. | Carmack |
| 4 | Drop the 1 GB Pages cap because the sibling dropped its self-imposed size target. | Not the same constraint. The sibling's audio is served from raw and never enters a Pages bundle; ours publishes to Pages, where the cap is external and real. | Carmack |

### What this row does not do

Does not change what any guardrail permits beyond this table - that is ESCALATE trigger (a). Does not touch section 0a, 0c, 2, 4, 5, 6, 9, 10 or 11. Does not sweep citations.

## 4. Row #3 - Eight collateral sections

- **Scope:** Bring every other section of the contract into the guardrail system.
- **Files touched:**
  - `CLAUDE.md`

| # | Section | Change |
| --- | --- | --- |
| 1 | 0a Non-Goals | New preamble. **A non-goal is a dated decision with an owner, not a law of physics.** Three of them have already been narrowed by owner decisions, which proves it. Naming a non-goal is not a finished answer; price it and hand it back (section 0d). |
| 2 | 0c Decision Requests | Adopt the sibling's improvement: the recommended option is marked `**Recommended**` in the row itself **and** restated at the end with the reason. A recommendation only in a closing paragraph makes the reader hold a row id in their head while scanning back up. |
| 3 | 2 Path Rules | Rename to **Path Conventions**. These are serialization invariants, not adaptive constraints, so they do not become guardrails - but they stop calling themselves rules. |
| 4 | 4 Layer and Dependency Rules | Rename to **Layer and Dependency Boundaries**. Same reasoning. |
| 5 | 5 Documentation Discipline | Reword "Docs-only PRs are a code smell". **The smell is docs describing code that did not change, not a docs-only PR as such.** As committed, the clause argues against this very change. |
| 6 | 6 Correction Levels | Add: the level is chosen against the intent, not against the smallest change that passes. When in doubt, choose the higher level (unchanged). |
| 7 | 9 Definition of Done | Add the human-approval checkbox specified in Row #1. |
| 8 | 10 Anti-Patterns | Extend the existing STOP-AND-SURFACE bullet: declining on a limitation without pricing it is the same thing (section 0d). Align the "Raise the runner budget" bullet with #2's rewrite. Add: ship an in-development surface without a config flag (Guardrail #6). |
| 9 | 14 Agent Roster | The line beginning "Rule: adding a new agent" loses the word. |

- **Acceptance gates:**
  - Local: `python backend/utilities/doc_load.py`; record the figure.
  - Local: `git grep -n 'section 2\|section 4' -- docs .github AGENTS.md` and confirm every citation of the two renamed sections still reads correctly.
  - CI: full suite.
- **Oracle:** **No orphaned citation.** Every section number cited anywhere in the repository resolves to a heading that still exists, and the two renamed headings keep their numbers so no cross-reference breaks. Produced as a list of cited section numbers against the file's headings, pasted in the PR body.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The non-goals get a preamble because that list is the largest refusal surface in the contract. | Owner, 2026-09-12 |
| 2 | Sections 2 and 4 are renamed to conventions and boundaries, not guardrails - they are invariants and calling them adaptive would be false. | Fowler |
| 3 | Section numbers are preserved through both renames so 1,300-plus citations stay valid. | Fowler |

- **Rejected alternatives:**

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Fold sections 2 and 4 into the twelve guardrails. | Would renumber the guardrails and invalidate every citation in the repository, for no gain. | Fowler |
| 2 | Leave "Path Rules" and "Layer and Dependency Rules" alone. | Half a rename. The owner's instruction is one vocabulary throughout. | Owner, 2026-09-12 |
| 3 | Delete the docs-only-PR clause. | The failure it names is real - docs drifting from code that did not change. It is reworded, not removed. | Fowler |

### What this row does not do

Does not touch section 0d or the twelve. Does not edit any file outside `CLAUDE.md`.

## 5. Row #4 - Restate in the three derived agent surfaces

- **Scope:** Carry section 0d and the section 1 preamble into the three files agents read instead of the contract.
- **Files touched:**
  - `AGENTS.md`
  - `docs/agents/guardrails.md`
  - `docs/agents/bootstrap.md`

Each restates. None extends (Guardrail #4). `docs/agents/guardrails.md` stops describing itself as the "rules-only digest" and becomes the guardrails-only digest.

- **Acceptance gates:**
  - Local: `python backend/utilities/doc_load.py`; the bootstrap load moves and the figure is recorded with what it means in words, not only as a number (section 0b).
  - CI: full suite.
- **Oracle:** **Restatement, not extension.** Every new paragraph in the three files maps to a sentence in `CLAUDE.md` that already says it. The PR body carries the mapping, one line per added paragraph. A paragraph with no source sentence is an extension and fails the row.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | All three derived surfaces carry 0d and the preamble, because an agent tool may read any one of them and not the others. | Owner, 2026-09-12 |
| 2 | The digest keeps its filename. `docs/agents/guardrails.md` was already named for the new vocabulary. | Fowler |

- **Rejected alternatives:**

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Point the derived files at `CLAUDE.md` instead of restating. | The files exist because some agent tools load them and not the contract. A pointer they cannot follow is no rule at all. | Fowler |

### What this row does not do

Does not sweep citations in these files - Row #5 does that pass over every file including these.

## 6. Row #5 - Repository-wide sweep, schemas, relapse proof

- **Scope:** One vocabulary everywhere, the schemas regenerated, and the result proved by count rather than asserted.
- **Files touched:**
  - Every file carrying a citation. Measured 2026-09-12: 1,338 lines across 338 files for `Rule #N` alone.
  - `schemas/*.schema.json` - regenerated, never hand-edited.

| # | Form | Measured 2026-09-12 | Action |
| --- | --- | --- | --- |
| 1 | `Rule #N` | 1,338 lines / 338 files | -> `Guardrail #N` |
| 2 | `Rule N`, `Rule:`, `P rule 1` | 11 lines / 7 files | -> guardrail wording |
| 3 | `R#n` | 1 line | -> `Guardrail #n` |
| 4 | "the Rules" as this project's noun | 3 lines | -> "the guardrails" |
| 5 | "rules-only" | 5 lines / 4 files | -> "guardrails-only" |
| 6 | "Holy Law" | 1 line | Kept as history; the rationale records both renames |
| 7 | Headings containing "Rules" | 4 (3 in the contract, 1 in a plan-doc) | Renamed |
| 8 | Bare `Rn` | 148 lines / 20 files | **No action.** Sampled: article text in `corpus/` and plan-doc row ids. Verified file by file before any edit. |

Two citation bugs surface during the sweep and are fixed in it:

| # | Bug | Fix |
| --- | --- | --- |
| 1 | One backend test cites `Rule #13`. There is no thirteenth guardrail; it means section 13, Test Coverage Policy. | Cite the section. |
| 2 | A concept doc calls itself "the concept-tier restatement of the Rules" while restating its own eleven principles. | Vocabulary only. The count of eleven is correct and does not move. |

- **Acceptance gates:**
  - Local: `python -m idhazh.contracts.export` then `git diff --stat schemas/`.
  - Local: `npm --prefix frontend run test:changed -- --list`, then the checks it selects. Pass `-- --python <abs path to the shared venv python>` when running from a worktree.
  - Local: the relapse scan, every pattern in the table above, re-run and quoted.
  - CI: full suite, including the contract drift gate.
- **Oracle:** **Three counts, all quoted, none asserted.**
  1. Every pattern in the table returns zero outside `corpus/`, `state/`, `config/`, `frontend/public/` and fixture article text.
  2. `git diff schemas/` contains no line matching `"version"` and no line matching `"changelog"`. A hit is ESCALATE trigger (c).
  3. The drift gate passes, proving the regenerated schemas are byte-identical to what is committed.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Full sweep, all 338 files, `docs/archive/` included. No bridging line saying the old word means the new one. | Owner, 2026-09-12 |
| 2 | The `Field(description=...)` strings are prose that ships into `schemas/`. Regenerating them costs no `version` bump and no `changelog` entry, because no shape moved. Verified: section 11 names only additive and breaking cases, and no test forces a bump. | Owner, 2026-09-12 |
| 3 | Committed data and fixture article text are never edited. A coincidental match in an article is not this project's vocabulary. | Fowler |
| 4 | The result is proved by quoting the counts, not by claiming the sweep is complete. | Owner, 2026-09-12 |

- **Rejected alternatives:**

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Sweep only the living docs and leave `docs/archive/`, plan-docs and comments. | Leaves the old vocabulary where an agent will read it and relapse. One vocabulary or none. | Owner, 2026-09-12 |
| 2 | Add a bridging line: "Rule #N is now Guardrail #N." | Keeps the old word alive in the one file everybody reads. History belongs in the design rationale, not in the working text. | Owner, 2026-09-12 |
| 3 | Bump every regenerated schema's `version`. | No shape moved. Section 11 names two cases and a prose edit is neither; Row #3 of the collateral work makes that third case explicit. | Owner, 2026-09-12 |
| 4 | Write a test that fails on a future `Rule #N`. | A mechanical guard of exactly this kind was written and deleted on 2026-09-06 for enumerating the hazard instead of the safe set, and for growing its own maintenance cost. Review enforces it. | `CLAUDE.md` section 1, design rationale |

### What this row does not do

Does not change any guardrail text. Does not touch `version` or `changelog` in any schema. Does not edit committed data.

## 7. Open questions

| # | Question | Owner |
| --- | --- | --- |
| 1 | Does the design rationale for the rename record the 2026-08-23 Holy-Laws rename as well, or link to it? Current plan: record both in one paragraph, since a reader asking "why is this named that" wants both answers on one page. | Owner |
| 2 | Row #5 collides with every open plan-doc that edits a file carrying a citation. The collision cost is reported in the PR rather than used as a reason to narrow scope - which is section 0d applied to this plan itself. | Orchestrator |

## See also

- [`../CLAUDE.md`](../CLAUDE.md) - the contract this plan amends.
- [`../docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md) - the orchestrator contract.
- [`../docs/how-to/run-the-gates.md`](../docs/how-to/run-the-gates.md) - the gate commands.
- [`../docs/concepts/growing-reads.md`](../docs/concepts/growing-reads.md) - Guardrail #12's escape hatch, the shape the other eleven move to.
