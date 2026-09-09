# 10 - A plan that cannot draw a number the article did not state

**Last Updated**: 2026-09-05
**Level**: 5 (a persisted contract, and the rule that decides what a reader is allowed to be shown)

**Chain**: previous [`20260905-09-pin-the-runtime-plan.md`](20260905-09-pin-the-runtime-plan.md) | next [`20260905-11-two-call-planner-plan.md`](20260905-11-two-call-planner-plan.md).
**Reference**: [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - O45, O47, rows 14, 15, 18, 19, 45, sections 7.5, 12.8 X2, X6, 12.13 G29, G32, 12.9 G13, 12.11 G21.

Execute per docs/how-to/execute-a-plan.md: orchestrator dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity; AUTO-merge on green gates; parallel N = 1; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | **Contracts before logic.** Plan 11's second call emits a visual plan; this plan defines what a visual plan is and what it may not contain, and builds the validator that refuses a bad one. Written the other way round, logic would be writing a payload with no contract, which is Rule #3 backwards. On its own it delivers the trust guarantee - a checkable rule that no drawn figure can be one the article did not state - and it is testable with no model running at all |
| Hard scope - in | The plan contract and its four prohibitions; the encoding roles; the validator's checks; the Derived Value contract with its four-function allow-list, the versioned unit table and the provenance chain |
| Hard scope - out | The planner module, the model calls, the reachability gate and the downgrade ladder (plan 11). Any renderer or compiler (plan 12). The display formatter - `convert` is a contract rule and belongs here, but SI prefixes, locale and precision are rendering and belong with the compiler |
| ESCALATE triggers | 1. A validator check cannot be expressed without calling a model. 2. A fifth allow-list function is proposed - the list is closed and its shortness is the guarantee. 3. The two provenance invariants declared build-failing elsewhere cannot be ruled without changing what a corpus build does |
| Chosen strategy | Contract, roles, validator, derived values - in that order, each shippable, none needing a model to test |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 1.` |

---

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | What a plan is, and the four things it may not carry | - | A | DONE #532 | yi-j01-plan | #532 | worker |
| 2 | Every role is a key, and an unused one is empty | 1 | B | DONE #533 | yi-j02-roles | #533 | worker |
| 3 | The validator refuses | 2 | C | DONE #535 | yi-j03-validator | #535 | worker |
| 4 | A number the article did not write, and the four ways code may reach one | 3 | D | DONE #537 | yi-j04-derived | #537 | worker |

**Every row is closed. The substance is distilled into
[`docs/architecture/publishing/visuals.md`](../docs/architecture/publishing/visuals.md)
and [`docs/concepts/design-system.md`](../docs/concepts/design-system.md), which
are the pages that own it.** Two follow-ups below need a home before this
plan-doc is deleted.

### Row 4 - the four functions, and the stamp that became three

Every chain carries `function`, `version` and `inputs` - Tier 1 element ids,
ordered, and never another derived value. `inputs` is flat by design: a nesting
chain can be complete at every hop and still name no element at the bottom, and
"every input element" is what the oracle asks for.

| Function | Reads | Produces | Adds to the chain |
| --- | --- | --- | --- |
| `count` | the elements in one bin | how many, unitless | the bin's floor and ceiling |
| `sum` | two or more elements stating one unit | their total, in that unit | nothing |
| `share_of_declared_whole` | the part, then the parts making the whole | a percentage | nothing |
| `convert` | one element | the same quantity against another unit of its dimension | the source unit and `UNIT_TABLE_VERSION` |

**Row 3's single stamp split into three, and `visuals.unit_table_version` was
refused.** Row 3 kept its role table in code for two reasons and only the second
carries over: a JSON file cannot reference two Python enums, which the unit
table does not need - but which units measure the same thing is arithmetic, so a
stamp an operator can edit without editing the table it stamps is a stamp that
lies, and every derived value recording it lies with it. The three are
`PLAN_VOCABULARY_VERSION` (which roles a type may fill), `UNIT_TABLE_VERSION`
(which units measure the same thing, and by what factor) and
`DERIVED_VALUE_VERSION` (the four functions and the binning rule). They are
separate because `plan_version_current` re-plans a plan behind the first, at one
model call an item - folded together, adding one unit spelling would re-plan
every in-flight plan for a reason the model had no part in.

**A mixed-but-commensurable value channel is now drawable**, which it was not
when row 3 closed. The target unit is the smallest scale present, tie-broken
alphabetically - a fact about the channel's contents rather than the plan's
order, so the model does not choose it, and converting to the smallest present
unit only ever multiplies, so no rounding decision hides inside a mark. The line
is scale, not spelling: `tonne` to `t` moves no number and is formatting; `kt`
to `t` is a different number and carries the chain.

**`derived_value_rate` and `trusted_data_ratio` ship as computations with
bounded tests and are deliberately not wired.** Nothing resolves a plan into
figures on the daily path until plan 12's compiler exists, so the run manifest
is named as their home rather than given two columns nobody writes. Both are
needed and they measure different things: the first is the narrowness alarm -
what share of a page's figures code computed - and the second is the correctness
alarm - what share resolves at all. Both return nothing over an empty set,
because a day whose planner drew no charts is not a perfect score.

ESCALATE trigger 2 is now mechanical rather than a paragraph:
`backend/idhazh/contracts/derived.py` raises at import if `DerivedFunction` and
the allow-list disagree, and the message says a fifth is an owner decision.

### Two follow-ups this plan created and did not close

1. **`_enough_data` counts the wrong thing for a histogram.** It counts elements
   in the `bins` channel against `min_chart_points` and `max_chart_points`, but
   a histogram's drawn marks are bins rather than input values. It is row 3's
   check and row 4 correctly left it. With `visuals.histogram_bins` at 3 and a
   channel of 3 to 8 values the two happen not to collide, so nothing is broken
   today - but a raised bin count can ask for more bins than the floor admits.
2. **`derived_values` imports `visual_validator`, which reads as a backwards
   arrow and is not one** - the resolver runs after validation, so a later stage
   imports an earlier stage's vocabulary. `UNIT_DIMENSIONS` was left where row 3
   put it rather than moved to a neutral module, because moving it would edit
   row 3's test imports for no behaviour change. If a reviewer prefers the move
   it is a two-line import change plus the guard.

### One process note worth carrying

Row 4's worker read the persona files **after** implementing rather than before,
then checked each ruling against them. None of the three contradicted a ruling,
but the order was wrong and the ratification is worth less for it. A persona is
an input to the action (`docs/how-to/execute-a-plan.md`), and read afterwards it
is a review instead.

---

### Row 3's two rulings on the provenance invariants (decision 5, 12.9 G13)

- **`derived_provenance_complete` degrades the item.** A plan whose drawn
  figure resolves neither to a Tier 1 element nor to a derived value with a
  complete chain is refused, the item publishes with no picture, and the
  refusing check is recorded - because taking a whole day's digest off the air
  to punish one story is the trade `CLAUDE.md` section 1a already refuses.
- **`span_integrity_pass` breaks the build on its write side and degrades the
  item on its read side**, which is what `ElementTable.span_drift` already does
  and what plan 08 row 4 shipped as three parts rather than one gate.
- **Why span is the exception, and it is not because span drift is graver.** It
  is the only one of the two asked on both sides of a boundary. A producer cut
  every excerpt out of the string it hashed moments earlier, so a mismatch there
  is this run's own arithmetic being wrong and every article in the run has it -
  failing the build states what is true. Every other invariant here is asked
  only of a payload the asker did not build, where the worst case is one item's
  problem. **Degrading is the rule; the exception turns on the side of the
  boundary, not on the invariant.**

Neither ruling changes what a corpus build does, so ESCALATE trigger 3 did not
fire.

### Where the per-type role table went, and the seven types with no rule

**Code, not `config/`, and decision 3's premise had already moved** - there is no
type vocabulary in `config/idhazh.json` today, so the check guards the table
where it actually lives. The relation is between `VisualType` and
`EncodingRole`, two closed enums, and a JSON file can reference neither; a copy
there is a second spelling that drifts from both. And "a bar has no bins" is
what a bar is rather than a tunable. The knobs that ARE knobs -
`min_chart_points` and `max_chart_points` - are read from `config/` (Rule #6),
and a test asserts they are read rather than typed.

**Eleven of the eighteen types have a rule. The other seven** - `table`, `flow`,
`comparison`, `callout`, `quotecard`, `whowhat`, `keyfacts` - **are named as
unruled and refused by name**, because a type in neither set would be waved
through by both per-type checks and drawn with nothing having ruled on it.
`enabled_kinds` is `["chart"]` and the downgrade ladder re-enters the same
validator with a nearer neighbour, so refusing is correct rather than a stopgap.

### The check that nearly could not be separated, and why the answer matters

`no_invented_values` read as "a value channel holds an element with no value" is
**unreachable** once `semantically_compatible` has passed - a value channel then
holds only `quantity` or `date` elements, and the `Element` contract forces both
to carry a value. That reading is a restatement, not a check. The separable
check is the one the subsystem needs: `Element` holds `span_excerpt` to the
width of its span and cannot hold it to the `value` beside it, because the value
is a READING of those characters and the shape does no reading.
`no_invented_values` re-reads it with the producer's own reader.

Separation was proved twice: the oracle asserts an equality on the returned
check list rather than a membership - a membership passes while three other
rules are firing - and then each check was neutered in turn against its own
fixture, with all nine leaving the plan accepted.

---

### Three judgement calls row 1 left open, and how row 2 closed the first

1. **There is no `label` role, and row 2 settled it rather than deferring it a
   third time.** Section 12.8 X2 lists one. Row 2 declined, and the reason is
   now held by a test: a `label` role asks the model the same question a second
   time inside `encodings`, and a model that answers twice can answer two ways
   with nothing in the payload to say which is right. So `labels` is the one
   naming channel - the elements whose own characters name the marks and the
   axes, ten of them for eight marks plus two axes. `event_label` is not the
   exception it looks like: a timeline's `time` channel places a dot and nothing
   else, so the event text is the mark rather than a name for one.
2. **`purpose` is nine members and `type` is eighteen.** `purpose` has to be
   coarser than `type` or it is a second name for it. The eighteen types are the
   pseudo-plan section 7.2 matrix verbatim.
3. **`plan_version` is code-stamped rather than decoded**, so row 3's "is
   current" comparison fires at read time, which is when it can find drift.

### What rows 1 and 2 settled, and the numbers that moved

The worst-case decoded reply is **3,767 characters, and therefore at most 3,767
tokens**, computed from the bounds rather than asserted.
`worst_case_reply_characters()` recomputes it from the generated schema and the
module refuses to import if that and the constant disagree. **Row 2 did not move
it by one character**, because a grammar-constrained decoder emits every
declared key either way - what changed is that the count is now true of an
ordinary plan as well as the worst one.

**Required-but-empty roles cost 87 to 114 characters a plan, which is 23 to 28
tokens** (measured with `llama-tokenize` against the committed tokenizer,
2026-09-09; a token count is deterministic, so the host does not matter). At the
visual planner's 13.00 tokens a second that is 1.8 to 2.2 seconds a plan, and
**12 to 14 minutes of runner wall-clock across a day** of five runs at the
80-item safety ceiling - 6 to 7 percent of `run.visual_planner_budget_minutes`.

**The decode rate the pseudo-plan quotes is the wrong model's.** Section 12.8 X2
prices the empty arrays at 6.01 tokens a second, which is the configured
summarizer's rate (`ubuntu-latest`, 2026-08-23). `config/idhazh.json` names
Qwen3-4B for `models.visual_planner`, measured at 13.00 tokens a second
(`ubuntu-latest`, 2026-08-22) - **2.16 times faster**. The pseudo-plan's figure
becomes the right one only after ruling O17 retires the 4B, so both are on
record. On the summarizer the same arrays cost 26 to 31 minutes a day.

`visuals.max_output_tokens` is **400** today, well under the 3,767-character
ceiling. Deriving that budget is plan 11's, from this arithmetic.

All four prohibitions are enforced in the shape except one half: `title`,
`caption` and `why` are prose the shape only length-bounds, because deciding
whether a numeral in them is matched by a cited element needs the article's
element table, which the plan deliberately does not carry. That is row 3's
"numerals matched" check, and nothing else was deferred.

---

## 2. Row #1 - What a plan is, and the four things it may not carry

- **Scope:** The `VisualPlan` contract: `decision`, `purpose`, `type`, `encodings`, `element_ids`, `labels`, `annotations`, `why`, `title`, `caption`, `confidence`, `plan_version`.
- **Files touched:** `backend/idhazh/contracts/visual.py` (new), `schemas/visual-plan.schema.json` (generated), `tests/fixtures/contracts/visual-plan/*.json`, `backend/tests/test_contracts.py`, `docs/architecture/publishing/**`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite.
- **Oracle:** A plan carrying a geometry value, a literal number, authored text or `alt_text` **fails validation**, and a plan carrying only references and closed names passes. All four prohibitions asserted separately, because a single combined test passes when three of the four are unenforced.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Four prohibitions: **no geometry**, no literal values, no authored text, and **no `alt_text`** | Row 4, 12.6 G6, 12.8 X6 |
| 2 | The geometry ban is what keeps the compiler swappable. A plan carrying a pixel is a plan bound to one renderer, and plan 12 is about to pick one | 12.6 G6 |
| 3 | **`alt_text` is the compiler's, and the contract loses the field.** If the model wrote it, it would be the last unguarded prose channel in the system. Generated by the compiler it is satisfied by construction, because the compiler holds only element values | 12.8 X6 |
| 4 | `confidence` decodes **after** `type`, or it is deleted. Second in the field list means it conditions every field after it. Record, never gate | Row 18 |
| 5 | Every array bounded, every string length-bounded, so the worst-case reply length is arithmetic rather than a hope | Row 14 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Let the plan carry `alt_text` | Reverses a ruling already recorded as closed, costs output tokens in a budget that is already tight, and opens a prose channel no validator can check | 12.8 X6 |
| 2 | Let the plan carry values as well as references | Then the worst an injection can do stops being "pick the wrong bars" and starts being "draw the wrong number" | C13 |

---

## 3. Row #2 - Every role is a key, and an unused one is empty

- **Scope:** `encodings` as one flat map in which every role name is a key, every key is required by the schema, and an inapplicable role is an **empty array**.
- **Files touched:** `backend/idhazh/contracts/visual.py`, `schemas/visual-plan.schema.json`, `tests/fixtures/contracts/visual-plan/*.json`, `backend/tests/test_contracts.py`, `docs/architecture/publishing/**`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite.
- **Oracle:** A reply omitting any role key fails the decoder; a reply supplying an inapplicable role as `[]` passes the contract and is then judged by the per-type check in row 3. Both halves asserted.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **Structurally present, semantically optional, per-type enforced.** One flat map with all keys required stops "a confident chart with no bars in it", which happened twice on the first live run; leaving roles optional brings that back | Row 15, 12.8 X2 |
| 2 | The per-type required set is the **validator's** job, not the schema's. The schema guarantees presence; the validator rules what may be empty for a given type | 12.8 X2 |
| 3 | The cost is real and must be measured, not assumed: roughly eight empty arrays per plan at 6.01 tokens a second decode | 12.8 X2 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | An eighteen-branch discriminated union, one per type | Enormous schema, and a decoder that has to choose a branch before it has chosen a type | Andre |
| 2 | Optional role keys | The exact failure row 15 exists to prevent | Andre |

---

## 4. Row #3 - The validator refuses

- **Scope:** Every check, run over a plan with no model in the loop.
- **Files touched:** `backend/idhazh/visual_planner.py` or a sibling validator module, `backend/tests/test_visual_validator.py`, `tests/fixtures/**`, `docs/architecture/publishing/**`
- **Acceptance gates:** `ruff`; `mypy --strict`; the full suite.
- **Oracle:** One fixture per check, each failing **only** its own check - proved by asserting the returned reason names that check and no other. A validator whose fixtures each trip three rules cannot tell you which rule works.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The checks: every element exists; elements are semantically compatible; **units are convertible or identical, not merely equal strings**; roles are valid for the type; enough data; no duplicate element in a role; no invented values; numerals matched; **`plan_version` is current** | Row 15, 12.13 G29, G32 |
| 2 | "Convertible or identical" keeps its second word. Every restatement in the source document dropped it, and the word was the check | 12.13 G29 |
| 3 | `plan_version is current` is a **comparison**, not an equality, because versions are date-stamps. It matters more now that the type vocabulary lives in `config/` and can drift independently of the contract that reads it | 12.13 G32, P.L15 |
| 4 | The behaviour behind `same_unit_bars` becomes a **committed fixture**: a small model picked three correct megawatt bars and appended a headcount. That is a real recorded failure and it must not be deleted with the module | Row 19 |
| 5 | The two provenance invariants declared build-failing elsewhere are ruled here, one sentence each, saying whether they break the build or degrade the item - and saying why the span invariant is the exception rather than the new rule | 12.9 G13 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | A model checks the plan | A judge sharing the failure modes of the thing judged is not a measurement | CLAUDE.md section 0a |
| 2 | Compare unit strings for equality | Cheaper, and it silently accepts `tonnes` beside `t` while refusing `4,200 tonnes` beside `4.2 kt`, which is the pair a reader most needs joined | 12.13 G29 |

---

## 5. Row #4 - A number the article did not write, and the four ways code may reach one

- **Scope:** The Derived Value contract: a closed four-function allow-list, deterministic versioned binning, a versioned unit table, and a complete provenance chain per derived value.
- **Files touched:** `backend/idhazh/contracts/visual.py` or a derived-value module, `schemas/*.schema.json`, `config/idhazh.json` (`visuals.unit_table_version`), `backend/idhazh/contracts/app_config.py`, `tests/fixtures/**`, `backend/tests/**`, `docs/architecture/publishing/**`, `docs/concepts/design-system.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite.
- **Oracle:** Every displayed value resolves either to a Tier 1 element or to a derived value whose provenance chain names its function, its version and every input element - asserted by walking a compiled plan and finding **zero** values with neither. And a plan requesting a function not on the list is refused by name.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The list is `count`, `sum`, `share_of_declared_whole`, `convert`. **Four, and closed.** Its shortness is the guarantee - the model cannot name a member, cannot supply an operand, and has no numeric field anywhere in its schema | O45, O47 |
| 2 | **`convert` is a derived value; formatting is not.** `2000000` drawn as `2M` moves no quantity and needs no provenance. `4200 tonnes` drawn as `4.2 kt` is a different number against a different unit and needs the full chain | O47, section 7.5 |
| 3 | Conversion is safe here because an element's Tier 1 `surface` is the article's own characters and is **never overwritten**. The axis draws the readable form; the provenance carries the original | O47 |
| 4 | `derived_value_rate` and `trusted_data_ratio` are reported. The closed list and the separate rate are the only two things keeping this narrow, and skipping either loses the guarantee unnoticed | 12.11 G21, P.L22 |
| 5 | Binning for a histogram is **versioned config**, never model-chosen | Row 45 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Refuse derived values entirely | Then a chart cannot show a total, a share or a distribution, and `pie`, `histogram` and every part-of-whole read go with it. The objection confused a number **code computed** with a number **a model invented** | Owner, O45 |
| 2 | An open function list | The list being short and closed is the whole argument. An open list is a model asking for arbitrary arithmetic | Andre |
| 3 | Let the model perform the conversion | Code does arithmetic. A model has no character-level view and cannot count | Section 10.6 |

---

## See also

- [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - the decision record this group executes.
- [`20260905-09-pin-the-runtime-plan.md`](20260905-09-pin-the-runtime-plan.md) - the previous plan.
- [`20260905-11-two-call-planner-plan.md`](20260905-11-two-call-planner-plan.md) - the next plan.
