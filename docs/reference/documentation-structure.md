# Documentation Structure

**Last Updated**: 2026-10-02

Where documentation belongs and what it must contain. Follow [CLAUDE.md](../../CLAUDE.md) section 5. These rules are domain-neutral.

## Diataxis tiers

| Directory | Question |
| --- | --- |
| `docs/architecture/` | How does this subsystem work, and why? |
| `docs/how-to/` | How do I perform this task? |
| `docs/concepts/` | What does this concept mean? |
| `docs/reference/` | What are the exact options, contracts or current readings? |

Each page answers one question. Onboarding belongs under `docs/getting-started/`. Do not create archives to avoid deleting obsolete prose; git keeps it.

## Depth rule (maximum 3 levels)

Use at most `docs/<tier>/<topic>/<file>.md`. Name a page for its question, never a sequence such as `part2`.

## Required elements (every doc)

- One H1, followed by `**Last Updated**: YYYY-MM-DD`.
- A short statement of the question the page answers.
- Current content in the page's tier, written in ASCII.
- A `## See also` section with useful cross-tier links.
- Valid relative links, including their section anchors.

## Doc-class routing contract

### Routing rules (decide a new statement's home)

| Content | Home | Do not include |
| --- | --- | --- |
| Subsystem behavior, boundaries and design reasons | Living architecture page | PR narratives and copied concept definitions |
| Shared vocabulary or policy | Concept page | A second definition elsewhere |
| Steps, inputs, checks and failure handling | How-to page | Design debates |
| Options, fields or current measurements | Reference page | Incident narratives |
| Portable checks that make tool results trustworthy | Agent-notes reference | Workstation configuration or product rules |
| One current benchmark answering one question | Benchmark record | Superseded runs or a second current answer |
| One interchangeable component and its current readings | Subject dossier, linked from its index | Other components' figures |
| Execution sequence and unfinished work | Plan under `TODO/` | Copied rationale, rejected alternatives or completed history |
| Directory purpose and writers | Repository-layout reference | Retention policy |
| What is retained, summarised or removed | Lifecycle concept page | A second directory inventory |

Put a decision's reason under `## Design rationale` on the page it affects. Do not create an ADR register. Link to that reason elsewhere.

### A benchmark run gets its own page, and never the log's name

Name the record for what it measures, without a date or sequence. A new run answering the same question replaces that record. Keep conditions, method, inputs, current figures, and what the result can and cannot settle. Keep enough information to reproduce a number still used by a current decision.

The shared reference holds one current reading per quantity and links to the record. A dossier holds the readings for one component. Remove a superseded reading rather than moving it into an appendix.

Keep a utility that reproduces a current cited measurement. Remove a completed migration or unused measurement tool only after checking its callers and documentation links.

### A page answers one question, and length is a symptom rather than the fault

There is no page-length limit. Apply these tests before adding material:

- **Split:** can two sections be used independently to answer different questions? Give each question a named page. Keep the original path as an index when needed for existing links.
- **Delete:** does a later statement correct an earlier one? Keep the current answer. Retain one warning only when it prevents a still-plausible wrong action.
- **Merge:** does a page have no useful purpose except as a section of another? Move it there and repair its links.

Do not split a coherent answer to meet a number. Before adding a section, apply the split test to its destination; one addition requires at most one related split. State why a large page remains whole when that is the right result.

### What a sentence has to do to stay

Keep current rules, their reasons and the checks that prevent wrong actions.

- State what contributors must do or avoid. Preserve reader guarantees, safety boundaries, missing-data behavior and real costs.
- Remove approval narratives, personal attributions and dates from rationale. Git holds that history; the requirement or exception remains. Follow `CLAUDE.md` for authorization limits.
- Remove developer-machine paths, local hardware inventories and workstation-specific commands. Keep portable prerequisites and production requirements.
- Delete incident timelines, run ids, stack traces, PR narratives, completed migrations and descriptions of what the page used to say. Do not move them into another doc.
- Delete rejected-option catalogues. Keep at most one sentence when its reason prevents a plausible wrong change.
- Keep a failure warning only while the failure is reachable, beside the action it constrains.
- Keep a measurement only while a current decision uses it, with its conditions. Replace superseded readings.

### Which page to fix first

Start with pages routinely loaded by contributors and agents. At similar read frequency, prefer the page with the most repeated or superseded content.

### The tool that hands you the numbers

Run before and after a documentation pass:

```text
python backend/utilities/doc_load.py docs/concepts/config.md
python backend/utilities/doc_load.py docs/concepts/config.md docs/concepts/evaluation.md
```

The token count estimates one token per four characters; it is not a tokenizer measurement. Use it to compare revisions, not as a length limit.

| Column | Inspect |
| --- | --- |
| `~tok` | How much context the page takes before work begins |
| `top h2` | Whether one section contains several independent questions |
| `from` | Whether readers can reach the page and whether it belongs elsewhere |
| `super` | Whether corrections have accumulated instead of replacing old answers |

The tool also reports missing required elements and broken paths or anchors. It reports rather than gates. Inspect the findings even when the command exits successfully. CI includes the changed-page report in its documentation summary.

### `docs/` is the memory

Durable knowledge belongs in its owning page, reviewed and versioned. Private memory and `AGENTS.md` are disposable indexes or caches. They must not be the only copy of a rule.

### Process docs are domain-neutral

Process how-to pages and this reference cite `CLAUDE.md` by section rather than copying project policy. Put necessary project-specific commands or values under Project bindings. State why a procedure cannot be domain-neutral when that applies.

### Cross-doc consistency mechanism

Edit current documentation in place. Define a concept once and link to it. Before moving a page or heading, find its readers, including tests and tools; repair them in the same change. A docs-only change is valid, but it must not claim that unchanged code gained new behavior.

### Plan-doc single-snapshot rule

A plan begins with one title, Last Updated line and current Status paragraph. Replace old status text at each phase boundary. Keep unfinished work in the plan and durable rules in their owning docs. Distil a completed plan, then delete it.

## Diagrams

Use a fenced `mermaid` block. The native theme, print rules, node meanings,
Metrics notes and copyable example live in
[mermaid-diagrams.md](mermaid-diagrams.md). That page answers how to draw a
diagram; this page answers where documentation belongs.

## See also

- [repository-layout.md](repository-layout.md) - directory purposes and writers.
- [mermaid-diagrams.md](mermaid-diagrams.md) - diagram notation for light, dark and print.
- [../how-to/ship-a-pr.md](../how-to/ship-a-pr.md) - delivery workflow.
- [../how-to/distill-a-plan.md](../how-to/distill-a-plan.md) - moving durable findings into docs.
- [../concepts/principles.md](../concepts/principles.md) - project design principles.
- [../../CLAUDE.md](../../CLAUDE.md) - engineering contract.
