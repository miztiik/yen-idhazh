# Documentation Structure

**Last Updated**: 2026-09-10

How `docs/` is organised, and where a new statement of project knowledge belongs. Companion to [CLAUDE.md](../../CLAUDE.md) section 5 (Documentation Discipline) - this doc defines the _placement rules_; CLAUDE.md section 5 defines the _constraints_ (ASCII, single source of truth, no duplicate definitions).

This reference is **domain-neutral** so it can be copied between projects unchanged (CLAUDE.md section 5).

## Diataxis tiers

Every document belongs to exactly one tier:

| Tier | Directory | Reader question |
| ------------ | -------------------- | ------------------------------------------------ |
| Architecture | `docs/architecture/` | Why is it designed this way? |
| How-to | `docs/how-to/` | How do I perform a specific task? |
| Concepts | `docs/concepts/` | What is this concept / vocabulary? |
| Reference | `docs/reference/` | What are the exact options / values / contracts? |

Support tiers:

- `docs/getting-started/` - onboarding entry points.
- `docs/archive/` - historical / superseded material.

## Depth rule (maximum 3 levels)

- Allowed: `docs/<tier>/<topic>/<file>.md`
- Forbidden: `docs/<tier>/<topic>/<subtopic>/<file>.md` or deeper.

A topic that needs deeper nesting is two topics. Split it.

## Required elements (every doc)

- One H1 title.
- `**Last Updated**: YYYY-MM-DD` line directly under the title.
- "See also" callout with cross-tier links (architecture <-> how-to <-> concepts <-> reference).
- Content that stays in its tier (no mixed-purpose docs).
- ASCII only - see CLAUDE.md section 5.

## Doc-class routing contract

Docs fall into the typed classes below. Each has one audience, one mutability rule, one allowed content type, and one forbidden content type. Routing is enforced at PR review time, not by tooling. A decision is NOT its own class - when a choice clears the Rule #4 bar, its rationale lives as a `## Design rationale` / `## Rejected alternatives` section on whichever class below it impacts; there is no ADR file and no `docs/architecture/decisions/` directory.

| Class | Path pattern | Audience | Mutability | Contains | Forbidden |
| ----------------- | --------------------------------------- | ---------------------------------- | ------------------------------------------------- | ------------------------------------------------------------------- | ------------------------------------------------- |
| **Subsystem doc** | `docs/architecture/<area>/*.md` | Engineer extending the subsystem | Living snapshot (edit in place) | Shape, layout, contracts, invariants, write/read paths (+ a `## Design rationale` for a decision the subsystem carries) | Long PR narrative; duplicate concept definitions |
| **Concept doc** | `docs/concepts/*.md` | Anyone learning project vocabulary | Living, terse | One term, defined once, with cross-links | Duplication of any term defined elsewhere |
| **How-to doc** | `docs/how-to/<verb>-<slug>.md` | Operator running a procedure | Living runbook | Ordered steps, inputs, validation, failure modes | Rationale prose; concept definitions |
| **Reference doc** | `docs/reference/*.md` | Someone needing an exact value | Living table | Exact options, values, contracts, measurements with hardware + date | Narrative; procedure |
| **Agent notes** | `docs/reference/agent-notes.md` (index) + `docs/reference/agent-notes/<tool-family>.md` | Anyone running commands in the repo | Living list | Environment and tool quirks that make a command lie about its result | Project behaviour, design rationale, product rules |
| **Benchmark record** | `docs/reference/benchmarks/<YYYY-MM-DD>-<what-was-measured>.md` | Anyone citing or re-running that run | **Frozen** - a run happened on a date and its conditions do not change | One run: its conditions, method, arms, raw figures, and what it settles and does not | The rule the figures justify; a figure a later run superseded |
| **Plan-doc** | `TODO/<YYYYMMDD>-<slug>-plan.md` | Next person picking up work | Single-snapshot; DELETED once distilled (git history is the ledger) | Phase status, active PR breakdown, TBD list, pointers | Rationale prose; decisions; rejected alternatives |

### Routing rules (decide a new statement's home)

1. Current behaviour rule, published shape, tuning invariant, or subsystem contract? -> **Concept doc**, **how-to doc**, or **subsystem doc**. This is the default.
2. Vocabulary term used across multiple subsystems? -> **Concept doc.** Defined once.
3. Step-by-step procedure an operator runs? -> **How-to doc.** Cite the concept or subsystem doc for why.
4. An exact value, threshold, or measurement someone will look up? -> **Reference doc.** A measurement carries its hardware and its date (CLAUDE.md Rule #10).
5. "Which PRs land when"? -> **Plan-doc.** Carry pointers, not full rationale.
6. Architecture choice with an actively explored rejected alternative, non-trivial reversal cost, and cross-system consequences? -> a `## Design rationale` / `## Rejected alternatives` section ON the living doc it impacts (concept / how-to / subsystem). No ADR file, no `decisions/` directory. If any leg is missing, just update the living doc's current-state text.
7. Where a file or a whole directory belongs in the tree? -> the **repository-layout reference doc.** One page maps every top-level directory to what it holds, who writes it, and whether it is committed - so a new directory has to state its reason before it exists.
8. A tool quirk, an environment trap, or a command whose result cannot be trusted at face value? -> the **agent-notes reference.** Not a private memory file - see below. It is one page until it stops being readable as one; then the stem path becomes an index and each child is named for the tool family whose output lies, so every inbound link keeps working.
9. A benchmark run - a sweep, a candidate priced, two arms raced? -> its own **benchmark record**, and a link from the instrument log. Never an append to the log. See below.

### A benchmark run gets its own page, and never the log's name

A run is a fact about a day: these weights, that build, this corpus, that
machine. The figure it produces is a fact about now, and only until the next run.
Appending the run to the instrument log merges the two, and the page then carries
several readings of one quantity in date order where only the ordering says which
governs - which is the failure the three tests above exist to stop, arriving by
the one door nobody guards, because each append is individually correct.

So they separate:

- **The record holds the run.** Conditions, method, arms, raw figures, and what
  it settles and does not. It is **frozen** once written: a later run does not
  edit it, it gets its own record.
- **The instrument log holds the figure now in force**, one per quantity, and
  links to the record behind it. When a run supersedes a figure, the log's number
  is replaced in the same commit - the old reading goes, and the record it came
  from stays where it is.

**The name says what was measured, never a sequence and never the family.**
`2026-09-09-doubled-window-and-cap.md` is a name somebody can arrive at.
`benchmark-2.md`, `measurements-3.md` and `perf-run-final.md` are not: the first
two answer no question and the third will be wrong within a week. A record may
not take the instrument log's name, because the log is where somebody arrives
holding "what is the number today" and the record answers "what happened on that
day" - two questions, and the log is the one every other doc links to.

**A run whose figure nothing acts on still gets a record**, and the log gets no
row. That is the honest outcome for an exploratory sweep, and it is cheaper than
the alternative this project has already paid for twice: a number in the log
that no config key reads, which a later reader treats as load-bearing.

### A page answers one question, and length is a symptom rather than the fault

A document does not go wrong by getting long. It goes wrong by holding **several
answers to one question**, where only the order of the sections says which one
governs - and the order is the one signal a reader who arrives by search never
sees. That is also the engine that makes a page grow: somebody who cannot tell
which statement is in force adds a new one instead of editing the old.

So the guardrail is three tests over questions, and **no page here has a maximum
length**.

**A split names a question. It never names a sequence.** `feature-part2.md` is
not a split and never will be: part 2 answers no question of its own, it is the
remainder of part 1, and a reader cannot arrive at it because nobody has ever
held the question "the rest of that". A page whose title only makes sense after
reading another page is a section of that page wearing a filename. The check is
one line, and it is the merge test applied to whatever the split test produced:
**say out loud the question somebody would be holding when they open the new
page.** If that sentence needs the old page's title in it, do not split - the
page was long and it was not confused, and a long page beats a set nobody can
navigate.

What a real split looks like: `measurements.md` became the producer and
`measurements-site.md` became what the reader downloads, because "how fast does
the model write" and "how big is the page I ship" are two questions and a person
arrives holding one or the other. What it never looks like: `measurements-1.md`
and `measurements-2.md`.

- **The split test.** Open the page at one section, read only that section, act
  on it. If acting correctly needs a fact that lives in a different section of
  the same page, the page has outgrown itself. Split it **along the question
  each part answers**, and the stem path becomes an index so every inbound link
  keeps working - rule 8 above, which is this test written for one doc class.
- **The delete test.** A section a later section corrects is not history, it is
  a second answer. Delete it in the commit that writes the correction; git holds
  the bytes. Leave one sentence behind wherever a reader meeting only the new
  text would re-propose the thing the correction killed. The plan-doc
  single-snapshot rule below is this test written for one doc class.
- **The merge test.** A page earns its existence by being where somebody arrives
  with a question in hand. If the only way to reach it is a link on a page they
  had to read anyway, it is a section of that page.

**The tests are deliberately in tension, and fragmentation is the worse half.** A
page that is too long costs a diluted answer; a page nobody opens costs a
confident wrong one. Where the split test and the merge test disagree, the page
stays whole.

### What a sentence has to do to stay

**Keep the sentence a reader who skipped it would act wrongly without. Cut the
sentence that only leaves them less well read.** Being uninformed is not a
failure and acting wrongly is, and that asymmetry is the whole rule. Two checks
fall out of it: a sentence that restates its own heading goes, and a sentence
whose removal changes only what somebody knows rather than what they do goes.

**A rejected alternative is a fence, not a story.** It exists so nobody reopens a
settled gate, and a fence needs a name and a reason rather than the minutes of
the argument. The form is one sentence with four clauses - the rule now in
force, the alternative named, the cost it would carry, and who decided and when.
An alternative that was built and measured keeps its number and that number's
conditions; one that was only argued keeps one clause. Safe to lose as a class:
the sequence of the argument, every option nobody built, restatements of the
winner in other words, and any sentence describing how a conclusion was reached
rather than what it constrains.

**A dated correction is kept only while its trap is still reachable.** Where the
failure it describes is now refused by a schema, a gate or a type, the code says
it earlier and better and the correction goes. Where a later reader would meet
something that looks wrong on sight and "fix" it back, the correction stays - in
one sentence, beside the thing that looks wrong, never in a history section.

**Six classes are not cut at any budget**: a stated commitment to a reader or an
operator, the reason an absence or a zero is correct, a measurement's
conditions, the cost clause of a decision, a still-reachable trap, and an
exception with the authority line that granted it.

### Which page to fix first

**The property is how often a page enters a reader's or an agent's working set,
never how big it is.** Size sets what one pass saves; frequency sets how many
passes it is saved on, and the cost is paid on load rather than on existence. The
order is pages on the bootstrap path, then pages read once per task, then once
per subsystem, then once per question. At equal frequency the tie-break is how
much a page has been appended to lately, because a page still growing is the one
whose contradictions are freshest.

The one thing here worth measuring is the bootstrap load itself - the tokens a
reader has to hold before the first line of code is read. That names a budget
rather than a threshold, and a budget is what leaves room for the working set.

### The tool that hands you the numbers

```text
python backend/utilities/doc_load.py
```

It prints the bootstrap load and one row per page, and **it decides nothing**:
every column is an input to one of the three tests above, and no number it prints
is a threshold. There is no doc gate and no line-count lint, deliberately - a
count is met by starting a second file, which is the fragmentation failure with
none of the benefit.

| Column | The test it feeds |
| --- | --- |
| `~tok` | the bootstrap load, against the working set you still have to hold |
| `top h2` | the largest section as a share of the page. One section holding most of a page usually holds several answers - open it and ask the **split test** whether you can act on one section without another |
| `from` | how many other pages link here. `1` means one page is the only way in, so the **merge test** asks whether that page owns this as a section; `0` is the same question, louder |
| `super` | sections saying a later one corrects them. Each is a **delete test** candidate and never a verdict: keep the correction whose trap a reader can still walk into, cut the one the correction closed |

Its token figure is about four characters a token - a declared estimate rather
than a measurement (Rule #10), which is enough to compare pages and not enough to
quote anywhere else. Run it before a docs pass to pick the page, and after one to
see what moved.

### `docs/` is the memory

Everything a future contributor or agent needs is written here, in a file that
is reviewed in a PR and versioned in git. An agent tool may keep a private note
store; that store is a **cache of what `docs/` already says**, never the only
copy of anything.

The test is simple: if a fact would be lost when the note store is cleared, or
invisible to a person reading the repository, it is in the wrong place. Move it
to the living doc that owns it, or - when it is execution craft rather than
project knowledge - to the agent-notes reference. `AGENTS.md` and any private
memory are derived; if either disagrees with `docs/`, `docs/` wins (CLAUDE.md
section 5).

### Process docs are domain-neutral

Everything under `docs/how-to/` that describes *how work is done* - authoring a plan, executing a plan, distilling a plan, handling a scope change, shipping a PR, deploying - plus this reference, is written to be copied between projects unchanged. Such a doc cites `CLAUDE.md` by section number rather than restating a project-specific rule, and it uses neutral examples. Where a project binding is genuinely needed (a build command, a live URL, a gate command), it goes in a clearly marked "Project bindings" section at the end rather than being scattered through the prose. A process doc that cannot be stated neutrally says so explicitly and names why.

### Cross-doc consistency mechanism

- Living docs are the default source of truth for current shape. Edit them in place as the project changes.
- A decision's rationale lives on the page it impacts, as a `## Design rationale` section; the immutable record of WHEN it changed is git history, not a frozen ADR file.
- Plan-docs link ACROSS to the living doc that now owns the finding.
- Concept docs link laterally and DOWN to operationalising subsystem docs and how-to docs.

### Plan-doc single-snapshot rule

The top of a plan-doc is exactly one block - title, Last Updated, and one-paragraph Status. Previous status text is **deleted** at every phase boundary. Stacked "previous header" layers are a band-aid for missing snapshot semantics and are forbidden by CLAUDE.md Rule #5. History lives in `git blame` and merge-commit titles.

## See also

- [CLAUDE.md](../../CLAUDE.md) section 5 (Documentation Discipline) - the constraints every doc honours.
- [repository-layout.md](repository-layout.md) - the companion map: where a directory belongs, as this doc is where a document belongs.
- [how-to/ship-a-pr.md](../how-to/ship-a-pr.md) - the PR lifecycle that triggers doc updates.
- [how-to/distill-a-plan.md](../how-to/distill-a-plan.md) - how a finding in a plan-doc gets lifted into the right canonical home.
