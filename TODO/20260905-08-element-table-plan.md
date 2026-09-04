# 08 - Every fact in an article, with the characters that prove it

**Last Updated**: 2026-09-05
**Level**: 5 (a new persisted contract that everything downstream reads, and the trust boundary between what code found and what a model said about it)

**Chain**: previous [`20260905-07-better-summaries-plan.md`](20260905-07-better-summaries-plan.md) | next [`20260905-09-pin-the-runtime-plan.md`](20260905-09-pin-the-runtime-plan.md).
**Reference**: [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - O37, O46, rows 1 to 5, sections 10.1a, 10.1b, C2, C13, C14, C15, 12.11 G19, G20, G21, 12.13 G35.

Execute per docs/how-to/execute-a-plan.md: orchestrator dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity; AUTO-merge on green gates; parallel N = 1; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Nothing in this repository can say *where in an article a number came from*. `numeric_facts()` computes the character offsets and throws them away. Without a span there is no way to prove a drawn figure is the article's, and every later plan rests on that proof. On its own this delivers a queryable fact table over every article, reusable by search |
| Hard scope - in | The six-kind element contract; the deterministic candidate pass for the two kinds code can find alone (quantity, date); the span-drift invariant in three parts; extraction health metrics; the denominator query for `chartable` and `narrative` |
| Hard scope - out | **The four model-discovered kinds' producers** - `entity`, `place`, `quote`, `claim` need call 1, which plan 11 introduces. The contract covers all six here; four of the producers land there. No visual, no plan, no model call added by this plan |
| ESCALATE triggers | 1. A Tier 1 field would be writable by anything other than the candidate pass or code slicing bytes. 2. The span invariant cannot degrade a single item and would have to fail a corpus build. 3. The element table would need to be committed per item in a way that moves the site cap measurably |
| Chosen strategy | Contract first, then the two code-only producers, then the invariant that makes a span trustworthy, then the health metrics. Code finds and cuts every character a reader will see; the model points and names, and it does not exist yet in this plan |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 1.` |

**The naming decision this plan must settle first.** Three names are in play for one concept - `raw`, `surface` and `span_excerpt` - and a later metric is defined on whichever one wins. `raw` is whitespace-cleaned and drops the magnitude word and the unit; `span_excerpt` is the verbatim slice. **Pick one, define it in the contract docstring, and use it everywhere.** Getting this wrong silently changes what `information_delta` means five plans later.

---

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | One contract, six kinds, two tiers | - | A | PENDING | - | - | - |
| 2 | Every quantity, with the characters that prove it | 1 | B | PENDING | - | - | - |
| 3 | Dates join the table | 2 | C | PENDING | - | - | - |
| 4 | A span that no longer points where it did | 3 | D | PENDING | - | - | - |
| 5 | What was found, what was used, and what could have been drawn | 4 | E | PENDING | - | - | - |

---

## 2. Row #1 - One contract, six kinds, two tiers

- **Scope:** The element contract covering `quantity`, `entity`, `date`, `quote`, `claim`, `place`, with Tier 1 fields that only code may write and Tier 2 fields a later model may assign.
- **Files touched:** `backend/idhazh/contracts/element.py` (new), `schemas/element.schema.json` (generated), `tests/fixtures/contracts/element/*.json` (new), `backend/tests/test_contracts.py`, `docs/architecture/extraction/**` (new or extended)
- **Acceptance gates:** `ruff`; `mypy --strict`; export + `git diff --exit-code -- schemas/`; the full suite.
- **Oracle:** **No Tier 2 field is required.** An element constructed with only its Tier 1 fields validates; an element carrying a Tier 2 field with no Tier 1 anchor does not. That pair is what the two-tier split means, and testing only the first half proves nothing.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Tier 1 - `element_id`, `kind`, `surface`, `span_start`, `span_end`, `span_excerpt`, `value`, `unit`, `sentence_index`, `extractor`. **Never model-authored**, on any kind | Section 10.1b invariant 1 |
| 2 | Tier 2 - `entity`, `time`, `measure`, `measure_canonical`, `dimension`, `salience`, `attribution`, `hedge`, `label_source`, `ledger_version`. Never drawn without its Tier 1 anchor | Section 10.1b invariant 2 |
| 3 | `extractor` records which path found the element, so a later run can measure the regex path and the model-proposed path apart | Section 10.1b |
| 4 | The contract covers six kinds; this plan ships two producers. A kind with no producer yet is legal and simply never appears | Fowler |
| 5 | `context` is superseded by `sentence_index` plus the span - a derived string replaced by a pointer. **Say so explicitly**; a field that ships today disappearing in silence is the one deletion section 2 cannot afford | 12.11 G20 |
| 6 | `source_text_hash` is **one hash per article**, not per element, reusing the existing content fingerprint. If the text moved, the first moved element fails the re-slice | Row 3 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | A per-element text hash | Redundant against the per-article hash plus the re-slice, and it is a hash per element on every article for ever | Fowler, row 3 |
| 2 | One flat tier | Then nothing distinguishes a character code cut from a word a model chose, which is the entire trust argument | Andre |
| 3 | Ship only the two kinds with producers | Six kinds in one contract with one changelog entry is cheaper than four later widenings of a persisted shape | Fowler |

---

## 3. Row #2 - Every quantity, with the characters that prove it

- **Scope:** The candidate pass emits every quantity the number pattern matches, each with the offsets that prove where it came from, and records the count it found **before** deduplicating and **before** the cap.
- **Files touched:** `backend/idhazh/elements.py` (new) or the renamed planner module, `backend/idhazh/extract.py`, `backend/idhazh/contracts/element.py`, `backend/tests/test_elements.py`, `tests/fixtures/**`, `docs/architecture/extraction/**`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite.
- **Oracle:** For every emitted element, `article.text[span_start:span_end] == span_excerpt`, asserted over the whole committed canary corpus rather than a chosen fixture. **And** on an article carrying the same figure in two periods, both survive - the candidate table is not the deduplicated fact list.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `numeric_facts()` already computes `match.start()` and `match.end()` and discards them. This row keeps them - the offsets are not new work, only the discarding was | C2 |
| 2 | **The candidate table does not dedupe.** `numeric_facts()` dedupes on `(magnitude, unit)`, which deletes exactly the series a trend chart exists to show. That behaviour is correct for picking a few bars and wrong for a candidate set | C14 |
| 3 | **Record the total match count before dedup and before the cap**, beside the capped table. A density signal off a saturating counter cannot tell a 600-word note carrying 16 figures from a 3,000-word data story carrying 60 - and the second is the chartable one. It fails silently, because a capped counter returns a plausible integer | Andre, 2026-09-05 |
| 4 | The existing `numeric_facts()` behaviour is preserved wherever something still calls it. This row adds a producer; it does not repair the old one in place | Fowler |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Reuse `numeric_facts()` as the candidate source | It deletes the series, drops magnitudes at or below 2, nulls stop-listed units and stops at 16. Every one of those is right for its original job | C14 |
| 2 | Let a model supply the offsets | A model has no character-level view and cannot count. The offsets are the one thing that must be mechanical | O37 |

---

## 4. Row #3 - Dates join the table

- **Scope:** A date extractor over the same bytes, emitting `kind=date` elements with the same span guarantee, plus the rule that settles two extractors competing for one span.
- **Files touched:** as row 2, plus `backend/tests/test_elements.py`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite.
- **Oracle:** A bare four-digit year is claimed as a `date` and **not** as a `quantity`, and the two extractors never emit overlapping spans - asserted by checking every pair of emitted spans on the canary corpus for overlap.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **No date extractor exists today.** `numeric_facts()` actively drops a bare year in 1900-2100, because a year is a label and not a bar height. So this is new work, not a rename of something that ships | C15 |
| 2 | Date sits with quantity because of the **seam**, not the cost. Both are pure regexes over the same bytes with the same `extractor="regex"`, the same table and the same invariant. The four kinds in plan 11 are the opposite shape - model-discovered, code-anchored, a different rule each | Andre, 2026-09-05 |
| 3 | The overlap rule is written **once, in the phase that owns the table.** Two extractors now compete for `2026`, and that rule has no other home | Andre |
| 4 | **Absolute dates and years only.** "Three years ago" resolves against the publication date, which is a value the article never wrote - a derived value, against a closed allow-list. Refused here | Andre, O45 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Put `date` with the model-anchored kinds | A pure regex in the model-anchoring phase is the wrong seam, and the overlap rule would then be written after the table it governs | Andre |
| 2 | Resolve relative dates | It states a date the article did not, outside the allow-list, on the very plan that establishes the trust boundary | Andre |

---

## 5. Row #4 - A span that no longer points where it did

- **Scope:** The span-drift invariant, in three parts: a write-time validator, a read-time re-slice that degrades that item alone, and a CI contract test over canary fixtures.
- **Files touched:** `backend/idhazh/contracts/element.py`, `backend/idhazh/elements.py`, `backend/idhazh/cli.py`, `backend/tests/test_contracts.py`, `backend/tests/test_elements.py`, `tests/fixtures/**`, `docs/architecture/extraction/**`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite.
- **Oracle:** A fixture whose article text has moved by one character causes exactly **that item** to degrade with a recorded reason, while every sibling item in the same run still publishes. A build that fails wholesale on one drifted span has implemented a different rule.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Three parts, not one build-failing gate. A corpus-wide break over one drifted span is the wrong trade | Row 2 |
| 2 | `raw` cannot serve as the excerpt - it is whitespace-cleaned and drops the magnitude word and the unit | Row 1 |
| 3 | The article hash is taken over the **normalised bytes the spans index**, so a span and its hash always describe the same string | Section 10.1b |
| 4 | Whether the two provenance invariants that are declared build-failing elsewhere stay build-failing is **open and must be ruled in this row**, with one sentence each saying why the span invariant is the exception rather than the new rule | 12.9 G13 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | One build-failing gate | Degrade, do not fail - a drifted span is one item's problem | CLAUDE.md section 1a |
| 2 | Trust the write-time validator alone | It cannot see text that moves after the write, which is the whole failure mode | Fowler |

---

## 6. Row #5 - What was found, what was used, and what could have been drawn

- **Scope:** Extraction health metrics, and the query that gives `chartable` and `narrative` a real denominator.
- **Files touched:** `backend/idhazh/elements.py`, `backend/idhazh/evals/metrics.py`, the item-health or a new ledger contract plus its schema, `frontend/src/routes/console/**`, `backend/tests/**`, `docs/concepts/evaluation.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite; `npm run check`; build; `bundle-gate`; the browser suite.
- **Oracle:** `extractable_but_unused_rate` is re-derived in the test from the committed element table and the committed plans, and equals what the metric reports. The classification query is asserted against hand-classified fixtures at both ends - an article with three quantities sharing a unit is `chartable`, an article with none is `narrative`.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `extractable_but_unused_rate` is the single metric that separates a planner regression from an extractor that started missing numbers. It is free, needs no labels, and without it the planner gets blamed for both | 12.13 G35 |
| 2 | `span_integrity_rate` is the reporting half of row 4's invariant and ships with it | 12.13 G35 |
| 3 | **Only two classes are derivable here.** `chartable` and `narrative` come from the element table as a query; `comparative` and `processual` are language, not numbers, and land with the diagram plan. **Any rate reported per class before then names three classes, not five, and must say so** | O46 |
| 4 | The classifier query rests only on Tier 1 elements, so unlike the seven-signal version it is byte-exact and inherits none of the model-judgement risk | O46, Fowler |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Build the full seven-signal classifier here | Four of its seven signals read call-1 output, which does not exist until plan 11. It would ship on two signals and still call itself the denominator | Andre, O46 |
| 2 | Report no denominator until all five classes exist | Then every rate this programme reports for the next three plans means nothing | Andre |

---

## See also

- [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - the decision record this group executes.
- [`20260905-07-better-summaries-plan.md`](20260905-07-better-summaries-plan.md) - the previous plan.
- [`20260905-09-pin-the-runtime-plan.md`](20260905-09-pin-the-runtime-plan.md) - the next plan.
- [`20260905-18-diagram-vocabulary-plan.md`](20260905-18-diagram-vocabulary-plan.md) - where the other two potential classes land.
