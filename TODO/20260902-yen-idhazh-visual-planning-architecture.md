# Yen Idhazh — Visual Planning Architecture

**Document type:** design specification, target state
**Audience:** the implementing agent or engineer
**Supersedes:** the current two-stage `summarise → route` pipeline and its bar-centric routing contract
**Revision:** consolidated 2026-09-02 — single document, seven numbered parts. Supersedes all earlier drafts.

---

## The idea in one paragraph

Read the article with code first, so you know exactly which facts are real and where each one came from. Then ask one capable model to understand the story and decide what visual would genuinely help — but only let it point at material the code already found, never let it author a number or a claim. Then let code check the model's choice makes sense, and let code render it.

> **The model decides what the visual *means*. Code decides what the visual *contains* and how it is rendered.**

Everything else in this document — trust tiers, validators, downgrade ladders, metrics — exists to keep that line from being crossed.

---

## Provenance warning — read before acting

Every statement in this document about **how the code works today** — `RouteDraft`, `ChartPoint {label, fact_index}`, `same_unit_bars()`, the two-model summarise→route split, the hard-coded bar renderer, the four-field fact record — is **second-hand and unverified**.

An independent attempt to read `github.com/miztiik/yen-idhazh` on 2026-09-02 failed on every public route (github.com HTML, `raw.githubusercontent.com`, `api.github.com`, `codeload`, third-party mirrors, the Software Heritage archive) while control fetches of public repositories — including one owned by the same account — succeeded on those same routes. The repository is most likely private.

**Confirm every identifier against the working tree before deleting or renaming anything.** The target design does not depend on those names being right; only the migration instructions do.

---

## How to read this

| Rule | |
| --- | --- |
| **1. Model neutrality is mandatory** | One component is named `SEMANTIC MODEL`. Its parameter count, vendor and revision are *configuration*, not architecture. Never hard-code a model size into class names, file names, telemetry fields, prompts, docs or comments. A 6B, 9B or 10B instruct model must be swappable without touching the design. |
| **2. Use the canonical vocabulary verbatim** | Consistent naming is load-bearing for this refactor. See the glossary below. |
| **3. Everything is normative** unless labelled *Example* or *Illustrative* | Illustrative numbers in this document are placeholders for measurement, never targets. |
| **4. Verify before you delete** | Anything describing the *current* implementation is recollection, not source. Treat each "replace X" instruction as a hypothesis to confirm first. |
| **5. You are expected to litigate this** | §7 holds 35 contested decisions, each with options, a recommendation, a confidence level and the strongest argument *against* it. Silently adopting the recommendations is a failed review. |

---

## Contents

| § | Contains | Read it when |
| --- | --- | --- |
| *Front matter* | Orientation, glossary, decision log, build order | First, always |
| **§1 Architecture** | Governing principle, ownership boundary, end-to-end flow, what changes, non-goals, compliance audit | Before writing any code |
| **§2 Data model** | Trusted Elements, the two trust tiers, open label vocabulary, derived values, Article Visual Potential | Building extraction |
| **§3 Visual Plan** | The plan contract, encoding roles, the three visual families and their vocabularies, worked example | Building the planner |
| **§4 Validation & rendering** | Validator rules, the downgrade ladder, the Visual Compiler, rendering decisions still open | Building validator or compiler |
| **§5 Measurement** | Upstream metrics, machine components, the quality index, cost, the human instrument, the KPI set, the two loops | Building telemetry or evaluation |
| **§6 Operations** | Telemetry schema, Console dashboard, feedback capture without a server, versioning and migration | Building the review loop or Console |
| **§7 Decisions & risks** | Risk register (20 rows), litigation table (35 rows), open questions, references | Reviewing, and whenever something feels wrong |

---

## Decision log

Decisions taken by the owner. Each is challengeable through its litigation row.

| # | Decision | Where |
| --- | --- | --- |
| **D1** | **Two calls, one model.** One set of weights, invoked twice per article: summarise, then plan the visual with the summary and the Trusted Elements in hand. There is no second, smaller model anywhere. | §1, L1, L27 |
| **D2** | **Full vocabulary declared in v1.** Compiler templates ship in waves; a planned type with no template yet is deterministically downgraded to its nearest implemented neighbour, and the downgrade is logged. | §3, §4, L2 |
| **D3** | **Element labels are model-assigned and open-vocabulary.** `measure`, `dimension` and `entity` are fitted to the article, not drawn from an enum. Values stay span-anchored. | §2, L4 |
| **D4** | **Encoding roles are per visual type**, not a fixed `x`/`y` pair. | §3, L4 |
| **D5** | **No invented metric weights.** The `0.30/0.25/0.20/0.15/0.10` vector is withdrawn. Weights start equal and are learned from human pairwise preference. | §5, L5 |
| **D6** | **Downgrade ladder with an escalating bar**, behind a flag. Each step down raises the acceptance floor and demands a machine-checkable justification. `VISUAL_DOWNGRADE=off` reverts to no-visual-on-failure. | §4, L7 |
| **D7** | **Numerals in prose are enforced.** Every number in `title`, `caption`, `alt_text` and `key_points` must match a Tier 1 element, with a narrow allow-list. | §2, §3, L8 |
| **D8** | **Feedback is captured out-of-band.** The application is stateless and serverless; a separate reviewer population supplies labels through the repository. | §6, L13 |
| **D9** | **Paired comparisons are A/B across config versions.** The second candidate is a Visual Plan generated under a different `weights.json` or prompt version for the same article. | §6, L16 |
| **D10** | **The `none` control arm is a config ratio, not a mode.** `review.none_arm_ratio ∈ [0.0, 1.0]`. | §6, L12 |
| **D11** | **The diagram path ships in v1**, with its own trusted-data model, validator rules and compiler target. | §3, §4, L9 |
| **D12** | **Rejected plans are labelled too.** A sample of plans that failed validation is rendered into `review/` — never published — and included in the labelling set. | §6, L30 |
| **D13** | **Extraction is measured.** The upstream stage enters the measured pipeline. | §5, L29 |
| **D14** | **The unit of trust is the Trusted Element, not the Trusted Fact.** A quantity is one *kind* of element; entities, dates, quotes and verbatim claims are others, all span-anchored. | §2, L31–L33 |
| **D15** | **The `§2` principle is amended** from "performs the semantic analysis once" to "performs all semantic analysis", to match D1 truthfully. | §1, L24 |

### Renames applied in this revision

| Was | Is | Reason |
| --- | --- | --- |
| Trusted Fact | **Trusted Element** | D14 — a quantity is one kind among six |
| `fact_id` / `fact_ids` | **`element_id` / `element_ids`** | Consequence of D14. If the codebase already ships `fact_id`, keep it as a deprecated alias for exactly one release and remove it |
| `RouteDraft` | **`VisualPlan`** | The routing contract is replaced |
| `ChartPoint {label, fact_index}` | **per-type `encodings` map** | Positional indexes break silently; a fixed x/y pair is a bar assumption |
| `same_unit_bars()` | **the Visual Validator** | Unit equality is not semantic equality |
| "router" / "routing stage" | **Visual Planning** | — |

---

## Build order

Sequenced so each step is verifiable before the next depends on it. Items marked ⚠ are gated on an open decision.

| # | Step | Delivers | Depends on |
| --- | --- | --- | --- |
| 1 | **Trusted Element model** — six kinds, two tiers, spans with a content hash | The source of truth for everything downstream | — |
| 2 | **Extraction measurement** — canary fixtures, free proxies, the potential classifier | The ability to tell an extractor regression from a planner regression | 1 |
| 3 | **`VisualPlan` contract** — replaces `RouteDraft`; per-type encodings; no literal values | The planner's output shape | 1 |
| 4 | **Single-model, two-call planning** — summary, then plan, with KV cache reuse | Removes the second model | 3 |
| 5 | **Visual Validator** — element existence, compatibility, role coherence, minimum data, no invented values | The integrity gate | 1, 3 |
| 6 | **Visual Compiler, wave 1** — `bar`, `line`, `dot`, `table` | First end-to-end publish path | 3, 5 |
| 7 | **Telemetry + Console** — one canonical event schema, the downgrade funnel | Failures become diagnosable | 4, 5, 6 |
| 8 | **Downgrade ladder** behind `VISUAL_DOWNGRADE` | Failure handling with an escalating bar | 5, 6, 7 |
| 9 | **Compiler waves 2–3** — `scatter`, `slope`, `stacked_bar`, `area`, `histogram`, `pie`, `timeline`, `bubble` | Vocabulary breadth | 6, 7 |
| 10 | **Review harness** — static `review/` page, queue generation, label ledger | Human ground truth | 6, 7 |
| 11 | **Human loop, bootstrap** — absolute mode, the Q1–Q5 rubric | The first keep-rate baseline | 10 |
| 12 | ⚠ **Infographic family** — `callout`, `comparison`, `quotecard`, `keyfacts`, `whowhat` | Coverage for non-numeric articles | 1, 5, 6, L28 |
| 13 | ⚠ **Diagram family** — Trusted Nodes and Edges, `flow` | Coverage for process articles | 1, 5, L18, L19 |
| 14 | **Paired mode + weight learning** — config-B variants, rejected-plan labelling, the fit | Learned weights replacing equal ones | 10, 11 |
| 15 | ⚠ **Interactivity / progressive enhancement** | The frontend requirements | 6, L21 |

**Do not start at step 6.** The temptation is to build the compiler first because it is the visible part. Everything it produces is worthless if step 1 is wrong, and step 2 is what tells you whether step 1 is wrong.

---

## Canonical vocabulary

| Term | Meaning |
| --- | --- |
| **Trusted Element** | An article-derived datum with a span, a `kind`, and semantic metadata. The single source of truth for everything a visual displays. A **Trusted Fact** is the `quantity` kind — the term survives only in that narrow sense. |
| **Tier 1 / Tier 2** | Tier 1 fields are byte-exact to the article and never model-authored. Tier 2 fields are model-assigned semantic labels, span-anchored and validated. The distinction is load-bearing; never collapse them. |
| **Visual Planning** | The semantic step in which the model decides *whether* a visual is warranted, *what* it should communicate, *which form* communicates it, and *which* elements support it. Under D1 it is the second of two calls to one model. |
| **Visual Plan** | The constrained JSON contract that step emits. Expresses **meaning only** — never rendering geometry, never literal values, never authored text. |
| **Visual Validator** | Deterministic code that accepts or rejects a Visual Plan against the Trusted Element store. |
| **Visual Compiler** | Deterministic code that turns a validated Visual Plan into a renderable specification. The specification target is decided in §4; it is not fixed by this document. |
| **Machine Loop** | The automated inner loop: plan → validation → metrics → failure diagnostics. Runs on every article, gates publication. |
| **Human Loop** | The sampled outer loop: published visuals *and* a sample of rejected plans → reviewer judgement → quality baseline. Runs periodically, gates nothing. |

### Plain-language glossary

| Term | In plain terms |
| --- | --- |
| **Span** | The exact character positions in the article where something was found — `[2210, 2228]` means characters 2210 to 2228. A **receipt**: any later stage can jump back and prove the article said it. A span is meaningless without knowing *which* normalisation of the text it indexes (see R5). |
| **Span-anchored** | Data carrying a span, and therefore provable against the source. Anything without one is unchecked model output. |
| **Node** | One box in a diagram — a step, stage or entity. |
| **Edge** | One arrow between two boxes — the claim that A leads to, precedes, or causes B. |
| **Encoding role** | What a piece of data *is doing* in a visual — the category, the quantity, the time axis, the size of a bubble. Not a pixel coordinate. |
| **Purpose** | What the visual is trying to show: `trend`, `ranking`, `relationship`, `composition`, `distribution`, `process`, `sequence`. Chosen before the visual type. |
| **Downgrade / depth** | Re-rendering the same claim in a weaker form after the first choice failed validation. Depth 0 is the original choice. |
| **Derived value** | A number that is computed rather than quoted — a bin count, a sum, a share. Permitted only with a provenance chain naming every contributing element. |
| **Prior** | A starting assumption taken from published evidence rather than intuition — "for a ranking task, a dot plot usually beats a pie chart". |
| **Weight** | How much one quality component counts toward a combined score. Learned here, never hand-picked. |
| **Pairwise** | Asking "which of these two is better?" rather than "rate this out of five". More stable across reviewers. |
| **Ledger** | An append-only file, never edited in place — so history is always recoverable. |
| **Invariant** | A condition that must always hold; if it breaks, the build fails. Stronger than a metric, which merely reports. |
| **Stratified sample** | A sample deliberately spread across categories rather than drawn at random, so no category is missed. |
| **Holdout** | Data withheld from fitting, used afterwards to check the fit generalises. |

---

## Status summary

| | Count |
| --- | --- |
| Owner decisions taken | 15 |
| Contested decisions with a recommendation | 32 |
| Decisions genuinely **open** | 3 — diagram renderer (L18), where rendering happens (L21), `callout` gating (L28, assigned to an editor agent) |
| Documented risks | 20, of which 16 fail silently |
| Metrics specified | 11 core + 6 quality additions + 10 cost + 6 extraction |


---

## 1. Architecture


---

### 1.1 Governing principle

> **The model chooses what the visual *means*. Code decides how the visual is *rendered*.**

Operationally, as amended by **D15**:

> **One larger model performs all semantic analysis; deterministic code controls data integrity and rendering afterward.**

The original wording said *"performs the semantic analysis **once**"*. That word was written to exclude a weaker **second model**, and the design still excludes one — but D1 invokes the single model twice, so "once" was literally false. It is amended rather than quietly ignored; §5 audits the full principle clause by clause.

#### 1.1.1 Ownership boundary

| The model owns | Code owns |
| --- | --- |
| Understanding the article | Tier 1 element values — byte-exact, never model-authored |
| Selecting which elements matter | Validation |
| Naming semantic relationships (Tier 2 labels) | Numeric integrity, including derived-value provenance |
| Choosing the visual purpose | Canonicalisation and the alias ledger |
| Choosing the visual type | Rendering and layout |
| Explaining its choice (`why`) | Colour, typography, accessibility |
| | Publication |

Two entries deserve emphasis because they are where the boundary is thinnest:

- **Tier 2 labels sit on the model's side.** `measure`, `dimension`, `entity` and `time` are judgements a regex cannot make. Calling the whole extraction "deterministic" would be false — see §2.
- **Diagram edges also sit on the model's side.** Deciding whether a sentence *asserts* that A precedes B is judgement, not pattern matching. See R10.

This is a stronger boundary than the current division, which is effectively *"the model chooses bars; Python decides everything else."* The model's responsibility moves **up one level** — from *"which bars?"* to *"what is the best representation of this information?"*

The existing repository already has the right instinct that **numbers must not come from unconstrained model output**. That instinct is preserved and generalised, not weakened.

---

### 1.2 End-to-end flow

```text
                    ┌────────────────────────────────┐
                    │            ARTICLE             │
                    └───────────────┬────────────────┘
                                    │ deterministic extraction + model labelling
                    ┌───────────────▼────────────────┐
                    │       TRUSTED ELEMENTS         │
                    │        (source of truth)       │
                    ├────────────────────────────────┤
                    │ Tier 1  element_id  kind       │
                    │         value  unit  raw  span │
                    │ Tier 2  entity  time           │
                    │         measure  dimension     │
                    └───────┬───────────────┬────────┘
                            │               │
                            │               └──────────────┐
                            │                              │
                ┌───────────▼────────────┐     ┌───────────▼───────────┐
                │     SEMANTIC MODEL     │     │  ARTICLE POTENTIAL    │
                │  ONE MODEL · TWO CALLS │     │  (deterministic)      │
                ├────────────────────────┤     ├───────────────────────┤
                │ call 1 → summary       │     │ chartable   singular  │
                │ call 2 → visual plan   │     │ processual  narrative │
                │  (KV cache reused)     │     │ comparative           │
                ├────────────────────────┤     └───────────┬───────────┘
                │ • understand the story │                 │
                │ • summarise            │                 │ denominator for
                │ • identify key facts   │                 │ every rate in 05
                │ • assess visual need   │                 │
                │ • choose the form      │                 │
                │ • select elements      │                 │
                │ • explain the choice   │                 │
                └───────────┬────────────┘                 │
                            │ constrained semantic JSON    │
                ┌───────────▼────────────┐                 │
                │      VISUAL PLAN       │                 │
                ├────────────────────────┤                 │
                │ decision   purpose     │                 │
                │ type       encodings   │                 │
                │ element_ids  labels    │                 │
                │ annotations  why       │                 │
                │ title  caption         │                 │
                │ NO geometry            │                 │
                │ NO literal values      │                 │
                │ NO authored text       │                 │
                └───────────┬────────────┘                 │
                            │                              │
                ┌───────────▼────────────┐                 │
                │    VISUAL VALIDATOR    │                 │
                │     (deterministic)    │                 │
                ├────────────────────────┤                 │
                │ elements exist?        │                 │
                │ semantically compatible│                 │
                │ units compatible?      │                 │
                │ roles valid for type?  │                 │
                │ enough data?           │                 │
                │ no duplicates?         │                 │
                │ no invented values?    │                 │
                │ numerals matched?      │                 │
                └──┬──────────────────┬──┘                 │
              fail │                  │ pass               │
    ┌──────────────▼───────┐  ┌───────▼────────────────┐   │
    │  DOWNGRADE LADDER    │  │    VISUAL COMPILER     │   │
    │  depth 1: median bar │  │  chart · diagram ·     │   │
    │  depth 2: p75 + note │─▶│  infographic templates │   │
    │  depth 3: refuse     │  │  → renderable spec     │   │
    └──────────┬───────────┘  └───────────┬────────────┘   │
       refused │                          │                │
               │              ┌───────────▼────────────┐   │
               │              │    PUBLISHED VISUAL    │   │
               │              └───────────┬────────────┘   │
               │                          │                │
               ▼                          ▼                ▼
    ╔══════════════════════════════════════════════════════════════╗
    ║                        MACHINE LOOP                          ║
    ║  every article · automatic · free · GATES PUBLICATION        ║
    ║  plan → validation → metrics → failure diagnostics           ║
    ╚══════════════════════════════════════════════════════════════╝
                              │
                     sampled  │  queue: published + rejected +
                              │  config-B variants + `none` arm
                              ▼
    ╔══════════════════════════════════════════════════════════════╗
    ║                         HUMAN LOOP                           ║
    ║  periodic · sampled · costly · GATES NOTHING                 ║
    ║  review → keep / useful / appropriate / accurate / faithful  ║
    ║  → quality baseline → learned weights                        ║
    ╚══════════════════════════════════════════════════════════════╝
```

**Read the two loops as inner and outer.** The Machine Loop is fast, free, runs on everything, and is the gate. The Human Loop is slow, costly, runs on a sample, and is the scoreboard. Because human answers are stored against the same metadata the machine metrics use, the Human Loop is what eventually lets you *validate the machine metrics themselves*. Until that correlation is measured, no composite score may gate anything.

**A rejected plan is never silently dropped.** It carries a typed rejection reason into the Machine Loop, and a sample of rejections is rendered into `review/` (never published) so weight-fitting sees the full distribution rather than only survivors — D12, R3.

---

### 1.3 What changes

#### Today

```text
primary-model summary
        ↓
secondary router model
        ↓
index selection
        ↓
hard-coded bar renderer
```

The renderer is hard-coded as a bar chart, and the model is instructed to choose "a chart" first, after which code turns that choice into bars.

#### Target

```text
semantic understanding
        ↓
visual intent (Visual Plan)
        ↓
deterministic compilation
```

That is the whole conceptual shift. Everything else is consequence.

| Dimension | Today | Target |
| --- | --- | --- |
| Models | Two — a summariser and a smaller router | **One** |
| Semantic authority | Split across both | **One model, both calls** |
| Visual contract | `ChartPoint {label, fact_index}` | `VisualPlan` with per-type encoding roles |
| Element references | Positional index | Stable `element_id` |
| Renderable output | Bar only | Chart, diagram and infographic families |
| Trust model | Implicit, unit-equality based | Two explicit tiers with spans |
| Failure handling | Undefined | Downgrade ladder with an escalating bar |
| Measurement | Chart rate | Machine + human loops, per potential class |

---

### 1.4 Non-goals

| Non-goal | Reason |
| --- | --- |
| The model generating a render specification directly | Rendering is code's job. Free-form spec generation reintroduces the value-invention risk this design exists to close. |
| Keeping `ChartPoint {label, fact_index}` | Too narrow, and positional references break silently. |
| **An unbounded vocabulary** | Every visual type must arrive with its own validator rule set and its own compiler template. A type without both is not in the vocabulary, however appealing it looks. *(This replaces the original "no more than ~10 chart types" framing: the constraint that matters is rules-per-type, not the count.)* |
| Reducing visual quality to one magic number | The quality index is an engineering diagnostic, never a truth score, and never a gate. |
| Using another LLM as the judge of visual quality | Human ground truth only, on a sample. |
| Unit equality as a proxy for semantic equality | The current fallback, and it is wrong. See §2. |
| Consumer-facing telemetry | The application is static and serverless. Reader behaviour cannot be measured; do not design as if it can. See §6. |

---

### 1.5 Compliance audit of the governing principle

The principle is this document's own commitment, so it is scored rather than asserted.

> *"One larger model performs all semantic analysis; deterministic code controls data integrity and rendering afterward."*

| Clause | Status | Evidence | Deviation |
| --- | --- | --- | --- |
| **One larger model** | ✅ Compliant | One set of weights. The secondary router is deleted, not shrunk | None |
| **performs all semantic analysis** | ✅ Compliant *(as amended by D15)* | All seven semantic jobs sit with that one model, across two invocations | Amended wording — see below |
| **deterministic code controls data integrity** | ⚠️ Partial | Tier 1 values, validation, derived-value provenance and the numeral check are fully deterministic. Tier 2 labels and diagram edges are model-assigned | **Deviation A** |
| **and rendering afterward** | ⚠️ Open in practice | Code owns the spec→pixels path. Whether pixels are produced at build time or in the browser is undecided | **Deviation B** — L21 |

#### 1.5.1 The amendment (D15)

"Once" was opposition to a *two-stage, two-model* pipeline in which a weaker second model made a second semantic judgement. Under D1 there is still exactly one semantic authority; it is invoked twice, the second call conditioned on the first.

That distinction is real but not free, and §5 prices it: two calls prefill the article twice unless the KV cache is reused. **Measure the call-1/call-2 `prefill_ms` ratio.** If it lands near 1.0, the cache is not being reused and D1 costs roughly double for failure isolation alone — which is the strongest available argument for reverting L1 to a single call.

What is not acceptable is leaving the principle stated as "once" while the implementation does it twice. A design document whose headline claim is contradicted by its own decision log stops being trustworthy on everything else.

#### 1.5.2 Deviation A — data integrity

Inherent, not incidental: a regex can locate `4,200 tonnes` but cannot know it means *exports* rather than *production*. Under D3 those labels are model-assigned by design.

What still holds:

| Guarantee | Holds? |
| --- | --- |
| No displayed **value** originates from the model | ✅ Tier 1 only, plus derived values computed by code from an explicit provenance chain |
| No displayed **text** is model-authored | ✅ Labels are element references; quotes and claims are verbatim spans |
| No **number in prose** is unmatched to an element | ✅ D7, covering title, caption, alt text and key points |
| Every **semantic label** is deterministic | ❌ Model-assigned, span-anchored, consistency-validated |
| Every **diagram edge** is deterministic | ❌ Span-anchored, but whether a span *asserts* a relation is judgement — R10 |

The precise, defensible claim is therefore narrower than the slogan:

> **Deterministic code controls every displayed value and every displayed string. Model judgement is confined to selection and labelling, and is span-anchored throughout.**

Use that formulation in any external description of the system.

#### 1.5.3 Scorecard

| | |
| --- | --- |
| Clauses fully compliant | 2 of 4 |
| Clauses partially compliant | 2 of 4 |
| Undisclosed deviations | 0 |
| Action | Principle amended per D15; deviations A and B carried openly rather than weakening the implementation to fit a slogan |


---

## 2. Data model


The Trusted Element store is the source of truth for everything a visual displays. If this layer is wrong, every metric downstream is measuring the wrong thing while looking healthy.

---

### 2.1 The Trusted Element

**Decision D14.** The earlier name "Trusted Fact" encoded an assumption — that the thing worth showing is a number. It is not. The stated goal is **information compression**, and a number is one carrier of information among several. Many articles in a news corpus contain little or no numeric data and are still highly compressible.

`kind` is the discriminator. Everything else is shared.

| `kind` | Payload | Tier 1 guarantee | Notes |
| --- | --- | --- | --- |
| `quantity` | `value`, `unit` | Byte-exact numeral and unit | The classic Trusted Fact, unchanged |
| `entity` | `name`, `entity_type` | Verbatim surface form | Person, organisation, product |
| `date` | `normalised`, `granularity` | Verbatim surface form only | `"last spring"` → a range, and that normalisation is Tier 2 |
| `quote` | `text`, `speaker_element_id` | **Verbatim span, no paraphrase** | The strongest guarantee in the system |
| `claim` | `text` | **Verbatim span only** | See §1.3 — the highest-risk kind |
| `place` | `name`, `geo_hint` | Verbatim surface form | Coordinate resolution is Tier 2 and out of v1 scope |

#### 2.1.1 Record shape

```json
{
  "element_id": 17,
  "kind": "quantity",

  "value": 4200,
  "unit": "tonnes",
  "raw": "4,200 tonnes",
  "span": [1842, 1855],
  "span_excerpt": "4,200 tonnes",
  "source_text_hash": "sha256:9f2c…",

  "entity": "India",
  "time": "2025",
  "measure": "exports",
  "measure_canonical": "exports",
  "dimension": "product",
  "label_source": "model",

  "context": "India exported 4,200 tonnes of refined product in 2025…"
}
```

`span_excerpt` and `source_text_hash` are not decoration — see §1.4.

#### 2.1.2 Two tiers of trust

"Deterministic extraction" is true of only half this record. A regex can find `4,200 tonnes`; it cannot know the quantity is *exports* rather than *production*. Say so in the data model rather than pretending.

| Tier | Fields | Produced by | Guarantee |
| --- | --- | --- | --- |
| **Tier 1 — deterministic** | `value`, `unit`, `raw`, `span`, `span_excerpt`, `kind`, verbatim `text` | Rule-based extraction | Byte-exact to the article. Never model-authored. This is what makes "no invented values" enforceable |
| **Tier 2 — semantic labels** | `entity`, `time`, `measure`, `dimension`, `granularity`, `entity_type` | The semantic model | Model-assigned, span-anchored to an existing Tier 1 element, validated for internal consistency, stamped with `label_source` |

**Telemetry must never aggregate the two tiers into one "trusted" number.** A Tier 2 error is a *labelling* error, fixable by prompt or fine-tune. A Tier 1 error is a *correctness* bug and must fail the build. Collapsing them hides the difference between "we mislabelled it" and "we made it up".

#### 2.1.3 The `claim` element — where fabrication re-enters

A quantity is safe because a number either matches the article or does not. **A claim is prose, and a model asked for "the key claim" will paraphrase** — producing something that reads as sourced, renders as authoritative, and is nowhere in the article.

> **Rule: a `claim` element is a verbatim span or it is rejected.**

The model selects *which* span. It never writes the text. If a claim must be shortened to fit a card, the **compiler** truncates deterministically with an ellipsis; the model does not rewrite it.

Expect sustained pressure to relax this — real sentences are rarely card-shaped, and "let it tidy the wording slightly" will sound reasonable every single time. That pressure is the risk. This is the easiest route to reintroducing fabrication after every other route has been closed (L32).

#### 2.1.4 Spans are worthless without their normalisation

A span is two integers indexing *some* rendering of the article. Raw HTML, cleaned text, entity-decoded, unicode-normalised — these produce different offsets. **If an upstream cleaning step changes, every stored span shifts and now points at the wrong text, and nothing notices, because a span is just two integers and validation still passes.**

Three requirements, all mandatory:

1. **`source_text_hash`** — a hash of the exact normalised text the spans index into, stored per article.
2. **`span_excerpt`** — the short text the span covered at extraction time.
3. **A build-time invariant** — for every element, `text[span] == span_excerpt`. Mismatch fails the build.

This is R5, and it is a corpus-wide silent corruption vector without these three.

---

### 2.2 Label vocabulary is open, not enumerated

**Decision D3.** `measure`, `dimension` and `entity` are free strings fitted to the article. A closed enum cannot cover an open news corpus — the tail of measures (`bycatch`, `settlement value`, `patient-days`, `spectrum allocation`) is unbounded.

#### 2.2.1 The cost, stated plainly

`semantic_coherence` asks "do these elements share the same measure?" With an open vocabulary that becomes string comparison, and `"exports"` will not equal `"export volume"`. **The metric then fails silently** — reporting incoherence where there is none, and suppressing perfectly good charts.

Two mitigations, both required. Without them D3 quietly disables one of the five quality components.

| Mitigation | Detail |
| --- | --- |
| **Canonicalisation pass** | After labelling, normalise labels **within a single article only** — case-fold, lemmatise, strip qualifiers — and emit `measure_canonical` alongside `measure`. Comparison happens on the canonical form; the model's original wording is preserved for display |
| **Corpus alias ledger** | A growing, reviewable alias map (`export volume → exports`) built from observed labels. It is **data, not code**, it is versioned, and the model never writes to it unreviewed |

#### 2.2.2 The failure direction nobody expects

Fragmentation is the obvious risk. **Over-merging is the dangerous one.**

| Failure | Symptom | Detectability |
| --- | --- | --- |
| Under-merging (`exports` ≠ `export volume`) | Good charts rejected | **Loud** — shows up as rejections |
| Over-merging (`revenue` = `gross revenue` = `net revenue`) | Charts mix incomparable quantities **while scoring perfectly on coherence** | **Silent** — the metric goes green |

Therefore: canonicalisation must be **conservative**. Log every merge, report `merge_rate`, and **prefer a rejection over a merge whenever uncertain.** This is R4.

#### 2.2.3 The ledger breaks historical comparability

Adding `export volume → exports` in month 3 changes what month 1's coherence score *would have been*. Stamp `ledger_version` on every computed score, and never compare scores across ledger versions without re-scoring. This is R6.

---

### 2.3 Derived values

Some legitimate visuals display numbers that appear nowhere in the article: a histogram shows **bin counts**; a pie shows **shares of a whole**. Under a strict reading of "every displayed value is a Trusted Element", neither could ever be rendered.

This is not a reason to ban them. It is a reason to be explicit, because the same problem recurs for any future aggregate type.

#### 2.3.1 The Derived Value contract

```json
{
  "derived_id": "d1",
  "fn": "count",
  "bin": [4000, 4500],
  "from_element_ids": [3, 7, 11, 14],
  "value": 4
}
```

| Condition | Requirement |
| --- | --- |
| Function | From a **closed allow-list**: `count`, `sum`, `share_of_declared_whole`. Never an arbitrary expression, never model-authored |
| Computed by | **Deterministic code**, from element ids the model selected. The model chooses *what* to aggregate; it never computes |
| Binning | A deterministic rule, versioned in config, identical across the corpus. A model-chosen bin boundary is a model-chosen conclusion |
| Provenance | Every derived value names every contributing `element_id`. A derived value without a complete chain is rejected |
| Telemetry | Counted by `derived_value_rate`, **separately** from trusted values — see §3.2 |

#### 2.3.2 Reconciling this with the integrity invariant

An earlier draft declared `trusted_data_ratio` a build-failing invariant that is structurally `1.0` forever. **Derived values break that as literally stated**, and the contradiction must be resolved rather than left for someone to discover.

The invariant is restated at the correct level:

> **Invariant (build-failing): every displayed value resolves either to a Tier 1 element, or to a derived value with a complete provenance chain over Tier 1 elements. There is no third case.**

And the two reporting metrics sit beneath it:

| Metric | Meaning | Expected |
| --- | --- | --- |
| `trusted_data_ratio` | Displayed values resolving **directly** to a Tier 1 element ÷ all displayed values | < 1.0 wherever histograms or pies are published — and that is correct, not a defect |
| `derived_value_rate` | Displayed values that are derived ÷ all displayed values | Small. A rise means aggregate types are becoming common; read it beside `chart_type_distribution` |

Neither is a gate. **The invariant is the gate**, and it is absolute.

---

### 2.4 Article Visual Potential

Every metric in §5 is a rate over articles, and **articles are not comparable**. A three-paragraph diary piece and a twelve-figure market report cannot be held to one `visual_decision_rate`.

Without a denominator reflecting what was *possible*, every rate is uninterpretable — and `missed_visual_rate` is meaningless, because it cannot distinguish *"nothing was visualisable"* from *"we failed to visualise it."*

#### 2.4.1 Signals — computed deterministically from elements, no model call

```text
numeric_density      comparable quantities sharing measure_canonical + unit
measure_diversity    distinct measure_canonical values
temporal_structure   dated elements forming a sequence
entity_count         distinct entities
comparison_signal    contrastive language between entities
process_signal       sequencing language between actions
quote_density        attributable verbatim statements
```

#### 2.4.2 Classes

| Class | Signature | Expected family |
| --- | --- | --- |
| `chartable` | ≥ 2 comparable quantities sharing measure and unit | Chart |
| `processual` | process signal + ≥ 3 ordered actions | Diagram |
| `comparative` | ≥ 2 entities with contrasting attributes | Infographic — `comparison` |
| `singular` | exactly one striking quantity or claim | Infographic — `callout` |
| `narrative` | none of the above | Legitimately `none` |

A profile, not a score. An article may be both `chartable` and `comparative`; record all classes that apply and report the primary.

#### 2.4.3 Why this is the highest-leverage measurement change

**Every rate in the KPI set is reported per class.** A 4% chart rate on `narrative` articles is correct behaviour; the same rate on `chartable` articles is a defect. Today those two are indistinguishable — and that single confound probably invalidates more of the KPI set than any other issue in this document (L35).

It also resolves R19: **stratify the human sample by potential class, not by the planner's own type choice.** Stratifying on a planner output confounds the type with the article — `bubble` keep-rate would measure unusual articles, not bubbles.

#### 2.4.4 The classifier is itself a tuning surface

Its thresholds (what counts as "comparable", how many ordered actions make a process) are configuration, and nobody owns them by default. **Assign an owner, version the thresholds, and record `potential_classifier_version` on every article** — otherwise a threshold change silently re-baselines every rate in the system.


---

## 3. The Visual Plan and the visual vocabulary


---

### 3.1 What the plan is

The Visual Plan is the **only** thing the model emits about the visual. It expresses **meaning**, never rendering.

#### It says

```text
type      = line
time      = elements 3, 5, 7
quantity  = elements 3, 5, 7
```

#### It never says

```text
x = 420
y = 300
width = 512
mark = ...
colour = #1f77b4
label = "4,200 tonnes"
```

Code owns all of that.

#### 3.1.1 Required fields

```text
decision           chart | diagram | infographic | none
confidence         high | medium | low
purpose            trend | ranking | relationship | composition |
                   distribution | process | sequence
type               the visual type within the chosen family
title              the visual's own title
caption            one line beneath the visual
alt_text           accessibility text
why                the model's rationale, in its own words
encodings          per-type role map — §2
element_ids        every element the visual draws on
labels             element_ids whose entity/time strings label marks
annotations        [{ element_id, reason }]
plan_version       contract version
```

| Field | Status | Note |
| --- | --- | --- |
| `confidence` | **Recorded, never gating** | Self-reported model confidence is not calibrated and must not gate publication. It is logged so its correlation with `visual_keep_rate` can be *tested*. If uncorrelated, delete the field rather than keep a decorative one (L23) |
| `title`, `caption`, `alt_text` | Required | All three fall under D7 numeral enforcement. `alt_text` is the one most often forgotten and is a caption by another name — R11 |
| `why` | Required, free text | **Never parsed, never gating, and never shown to a human reviewer.** It exists so an engineer reading a rejected plan can see what the model believed it was doing. A reviewer who reads the model's justification before judging is anchored by it and the label is contaminated — R14 |
| `labels` | Optional | Mark labels are drawn from element `entity` / `time` strings **by reference**. The model may never author label text |
| `element_ids` | Required | Stable ids, never positional indexes. A positional index breaks silently when extraction changes: the plan still validates while pointing at different data |

**Absolutely excluded:** literal values, geometry, colour, axis ranges, authored label text, authored quote or claim text.

---

### 3.2 Encoding roles are per type

A fixed `x` / `y` / `series` triple is a bar-and-line assumption in disguise. A pie has no x-axis. A slope has two value columns and no axis. A bubble has three quantitative channels. So the plan carries an `encodings` **map whose permitted keys are determined by `type`**, and the validator enforces the key set.

#### 3.2.1 Chart family roles

| `type` | Required roles | Optional |
| --- | --- | --- |
| `bar` | `category`, `quantity` | `series` |
| `dot` | `category`, `quantity` | `series` |
| `line` | `time`, `quantity` | `series` |
| `area` | `time`, `quantity` | `series` |
| `scatter` | `quantity_x`, `quantity_y` | `series`, `label` |
| `bubble` | `quantity_x`, `quantity_y`, `size` | `series`, `label` |
| `slope` | `entity`, `value_before`, `value_after` | — |
| `stacked_bar` | `category`, `part`, `quantity` | — |
| `pie` | `part`, `quantity`, `whole` | — |
| `histogram` | `quantity`, `bins` *(derived)* | — |
| `timeline` | `time`, `event_label` | `entity` |
| `table` | `columns[]` — ordered role list | — |

#### 3.2.2 Diagram family roles

| `type` | Required roles |
| --- | --- |
| `flow` | `nodes[]` — node ids · `edges[]` — edge ids |

#### 3.2.3 Infographic family roles

| `type` | Required roles | Optional |
| --- | --- | --- |
| `callout` | `figure`, `context` | `entity` |
| `keyfacts` | `items[]` — 3 to 5 element ids | — |
| `quotecard` | `quote`, `speaker` | `context` |
| `comparison` | `entities[]`, `attributes[]` | — |
| `whowhat` | `pairs[]` — entity + claim | — |

Every role value is a list of `element_id`s. **No role ever carries a literal.**

#### 3.2.4 Why this matters — the same elements under two types

```json
"type": "line",
"encodings": {
  "time":     { "element_ids": [3, 5, 7] },
  "quantity": { "element_ids": [3, 5, 7] }
}
```

```json
"type": "pie",
"encodings": {
  "part":     { "element_ids": [3, 5, 7] },
  "quantity": { "element_ids": [3, 5, 7] },
  "whole":    { "element_id": 11, "declared": true }
}
```

The pie case shows the point. **A part-to-whole chart is only honest if the whole is a stated fact.** If no element represents the total, `pie` and `stacked_bar` are rejected rather than having the total silently summed from the parts — the parts may not be exhaustive.

---

### 3.3 What Visual Planning decides

Five questions, in order:

```text
1. Should there be a visual at all?
2. What is it trying to communicate?
3. What form communicates that best?
4. Which trusted elements support it?
5. What annotation or context is necessary?
```

Materially more than today's three-way `chart / diagram / none`, in which the model picks "chart" and code turns that into bars.

#### 3.3.1 Purpose → form (examples)

| Purpose | Example plan |
| --- | --- |
| Trend | `{ "decision": "chart", "purpose": "trend", "type": "line" }` |
| Ranking | `{ "decision": "chart", "purpose": "ranking", "type": "dot" }` |
| Relationship | `{ "decision": "chart", "purpose": "relationship", "type": "scatter" }` |
| Composition | `{ "decision": "chart", "purpose": "composition", "type": "stacked_bar" }` |
| Distribution | `{ "decision": "chart", "purpose": "distribution", "type": "histogram" }` |
| Process | `{ "decision": "diagram", "purpose": "process", "type": "flow" }` |
| Comparison | `{ "decision": "infographic", "purpose": "ranking", "type": "comparison" }` |
| Nothing useful | `{ "decision": "none" }` |

The purpose→type mapping is a **learned prior**, not a hard rule — seeded from published evidence, then fitted. See §5.

---

### 3.4 The three families

Three families, one plan contract, one validator, one compiler with three back-ends.

| Family | `decision` | Carrier | Needs numbers | Ships |
| --- | --- | --- | --- | --- |
| **Chart** | `chart` | Quantities | Yes | Wave 1 |
| **Diagram** | `diagram` | Nodes and edges | No | v1, D11 |
| **Infographic** | `infographic` | Text elements, typeset | No | v1, gated on L28 |

**`chart_type_distribution` splits three ways and the families are never blended.** A blended distribution is uninterpretable — the families answer different questions on different articles.

#### 3.4.1 Chart vocabulary

| Type | Primary use |
| --- | --- |
| `bar` | Category comparison |
| `line` | Time series |
| `dot` | Ranking / comparison |
| `scatter` | Two-variable relationship |
| `bubble` | Three-variable comparison |
| `slope` | Before / after |
| `stacked_bar` | Composition |
| `area` | Cumulative magnitude over time |
| `histogram` | Distribution of many like values |
| `pie` | Part-to-whole where the whole is stated |
| `timeline` | Dated events |
| `table` | Precise multi-dimensional facts |

**Gates on the perceptually weaker types.** Cleveland & McGill place angle and area judgements below position and length in accuracy, so these carry extra conditions rather than a ban:

| Type | Additional conditions |
| --- | --- |
| `pie` | `purpose` = `composition`; ≤ 5 parts; a `whole` element must exist and be **declared, not summed**; parts share one `measure_canonical` and one unit |
| `bubble` | `purpose` = `relationship`; ≥ 5 points; `size` is a positive ratio-scale quantity |
| `stacked_bar` | Parts exhaustive against a declared whole, or downgraded to grouped `bar` |
| `area` | `purpose` = `trend`; the quantity must be a **stock or cumulative** measure, never a rate — a filled area under a rate line asserts a total that was never stated |
| `histogram` | ≥ 12 comparable elements sharing measure and unit; deterministic versioned binning; derived values under the §2.3 contract. Below 12, `dot` is the honest choice |

Both `pie` and `bubble` are flagged in telemetry so their keep-rate can be compared directly against the position/length types. If `pie` under-performs over a meaningful sample, that is an empirical result, not an argument (L3).

#### 3.4.2 Diagram vocabulary

**v1 scope: `flow` only** — linear or lightly branching process and sequence. `hierarchy`, `state` and `mindmap` are out until each has its own validator rules.

`decision: "diagram"` is **not** a chart type and is never aggregated into the chart distribution.

###### Trusted Nodes and Edges

Everything in §2 protects values. A diagram has none. Shipping `diagram` under the chart rules would leave the model free to invent steps, orderings and causal links with nothing checking them — reopening, in a different shape, the exact hole this architecture exists to close.

**A process diagram that invents a step is arguably a worse failure than a bar chart that invents a value.** It asserts causality, it looks authoritative, and nobody audits arrows.

```json
{ "node_id": 4, "label": "Customs clearance", "span": [2210, 2228], "kind": "step" }
{ "edge_id": 2, "from": 4, "to": 5, "relation": "precedes", "span": [2229, 2264] }
```

| Rule | Reason |
| --- | --- |
| Every node label derives from a span | The same guarantee Tier 1 gives charts |
| **Every edge is span-anchored too** | The ordering or causality must be *asserted by the article*, not inferred. The most important rule here, and the one most likely to be quietly skipped |
| Node labels containing numerals fall under D7 | Consistency |
| `purpose` must be `process` or `sequence` | Stops `diagram` becoming the escape hatch for "no good chart available" |
| No cycle unless the article asserts one | An invented feedback loop is an invented claim |
| Node count bounded by config, set from observation | Provisional ceiling, explicitly labelled provisional (L20) |

A diagram whose edges cannot be span-anchored is **rejected**, and it downgrades to `none` — never sideways into a chart.

> **Honesty note (R10):** edges are **Tier 2 with a span**, not Tier 1. Natural language asserts sequence at many strengths — "then" is explicit, "subsequently" is weaker, paragraph adjacency asserts nothing. Deciding which spans count is model judgement. Publish the decision procedure, sample edges for human audit, and do not describe edge anchoring as deterministic.

#### 3.4.3 Infographic vocabulary

Typography and layout over Trusted Elements. Nothing invents text. Cheap to render, and they work on articles a chart cannot touch.

| Type | Shows | Elements | Compression argument |
| --- | --- | --- | --- |
| `comparison` | Qualitative attributes across 2–4 entities | *n* × *m* grid | **The highest-value non-numeric type.** "Who does what differently" is a table the prose must serialise across paragraphs |
| `callout` | One striking figure or fact with its context line | 1 `quantity` or `claim` + 1 context | Puts the single load-bearing number where the eye lands first. **Gating is open — L28** |
| `quotecard` | An attributed statement | 1 `quote` + 1 `entity` | The safest type in the system: verbatim span, named source |
| `whowhat` | Actors and their roles | `entity` + `claim` pairs | For multi-party stories where the reader loses track |
| `keyfacts` | 3–5 structured takeaways | 3–5 elements | Replaces a paragraph of scanning with parallel structure. **Weakest — see below** |

###### This is not a licence to decorate

The obvious objection: a `keyfacts` box is the summary reformatted, which is exactly the redundancy the metrics penalise. Correct — and the existing machinery applies unchanged:

| Guard | Applied to infographics |
| --- | --- |
| `information_delta` | An infographic restating the summary scores near zero, exactly as a redundant chart does |
| Redundancy component | Becomes the **binding constraint** for this family, not a footnote |
| D7 numeral enforcement | Every numeral in a card matches a Tier 1 element |
| Verbatim rule | `quote` and `claim` are spans, never model prose |
| `visual_keep_rate` | The same human question decides. If reviewers do not keep them, they do not ship |

> **Recorded prediction, so it can be checked (L33):** `keyfacts` will show a **high decision rate and a poor keep rate** — the easiest type for a model to justify and the least informative for a reader. If that holds, drop `keyfacts` and keep `comparison`. Pre-committing to the kill criterion now is cheaper than defending it later.

###### One hard boundary

**An infographic is never a downgrade target for a failed chart.** Falling back from a rejected chart to a `keyfacts` box is precisely the "valid but pointless" outcome the downgrade ladder exists to prevent. See §4.

---

### 3.5 Worked example

The reference an implementer should code against — fully populated, no placeholders.

```json
{
  "plan_version": 3,

  "summary": {
    "title": "India's oil exports climbed for a third straight year",
    "standfirst": "Shipments reached 4,200 tonnes in 2025, the largest annual rise in the period.",
    "key_points": [
      "Exports rose in each year from 2023 to 2025.",
      "The 2025 total of 4,200 tonnes was the highest recorded.",
      "The steepest year-on-year increase came in 2025."
    ]
  },

  "visual": {
    "decision": "chart",
    "confidence": "high",
    "purpose": "trend",

    "type": "line",
    "title": "Indian oil exports, 2023–2025",
    "caption": "Annual export volume in tonnes.",
    "alt_text": "Line chart of Indian oil export volume rising each year from 2023 to 2025.",
    "why": "Three comparable annual totals for one entity and one measure; a line makes the direction and the acceleration visible at once.",

    "encodings": {
      "time":     { "element_ids": [3, 5, 7] },
      "quantity": { "element_ids": [3, 5, 7] }
    },

    "labels": { "element_ids": [3, 5, 7] },

    "annotations": [
      { "element_id": 7, "reason": "largest year-on-year increase" }
    ]
  }
}
```

**Note what is absent and must stay absent:** no `4200`, no `2025` as a plotted value, no pixel geometry, no colour, no axis range, no label strings. Every displayable value is reached through an `element_id`.

---

### 3.6 Schema lineage

Three drafts preceded this contract. Every field in all three is accounted for — adopted, renamed with a reason, or rejected with a reason.

| Draft field | Disposition | Rationale |
| --- | --- | --- |
| `summary.title` / `standfirst` / `key_points` | Adopted unchanged | — |
| `decision` | Adopted over `kind` | "Decision" names an act the model performed and is auditable; "kind" names a category and invites treating `none` as a type rather than a judgement |
| `confidence` | Adopted, non-gating | Uncalibrated self-report |
| `purpose` | Adopted, **enumerated** | Free text (`"show change over time"`) cannot be aggregated, so the purpose→type prior would be unfittable |
| `chart.type` | Adopted as flat `type` | The nested object bought nothing and made the diagram branch awkward |
| `chart.title` | Adopted | Was missing from an earlier field list — a genuine omission |
| `x` / `y` / `series` | **Replaced** by per-type `encodings` | A fixed triple is a bar-and-line assumption |
| `semantic_role` | Adopted **as the encoding key itself** | The draft had the right instinct; making the role the key rather than a property of an axis is strictly stronger |
| `fact_indexes` | **Rejected** → `element_ids` | Positional indexes break silently while still validating. The single most dangerous field in the drafts |
| `labels` | Adopted, **references only** | Never model-authored text |
| `annotations` | Adopted, `reason` required | — |
| `why` | Adopted | The drafts' best contribution: costs nothing, never parsed, fastest route to understanding a bad plan |
| `area`, `histogram` | Adopted with conditions | §4.1 |


---

## 4. Validation, failure handling and rendering


---

### 4.1 The Visual Validator

Deterministic code. Accepts or rejects a Visual Plan against the Trusted Element store, and emits a **typed rejection reason** on failure. This replaces today's bar-specific checks such as `same_unit_bars()`.

#### 4.1.1 Universal rules — every family

| Check | Failure means |
| --- | --- |
| Every `element_id` exists | The plan references data that is not there |
| No duplicate elements within one role | Padding a chart to meet a minimum |
| Roles present exactly match the type's required set | Wrong contract for the chosen type |
| No literal value anywhere in the plan | A value-invention attempt |
| No authored text in `labels`, `quote` or `claim` roles | A text-invention attempt |
| Every numeral in `title`, `caption`, `alt_text`, `key_points` matches a Tier 1 element or the allow-list | D7 |
| Every displayed value resolves to a Tier 1 element **or** a complete derived-value chain | The integrity invariant — §2.3.2 |
| `plan_version` is current | Contract drift |

#### 4.1.2 Chart-family rules

| Check | Notes |
| --- | --- |
| Elements share a compatible `measure_canonical` | Compared on the canonical form, never the raw label |
| Units compatible | Convertible or identical — not merely equal strings |
| Dimensions compatible | — |
| Role semantics coherent | A `time` role holds `date` elements; a `quantity` role holds `quantity` elements |
| Minimum point count for the type | Per-type, config-versioned |
| Type-specific gates | `pie`, `bubble`, `area`, `histogram`, `stacked_bar` — §3.4.1 |

#### 4.1.3 Diagram-family rules

| Check |
| --- |
| Every node label is span-anchored |
| **Every edge is span-anchored** — an unanchored edge is an invented causal claim |
| No cycle unless the article asserts one |
| Node count within the configured bound |
| `purpose` is `process` or `sequence` |

#### 4.1.4 Infographic-family rules

| Check |
| --- |
| `quote` and `claim` payloads are **byte-identical to their span** |
| Element count within the type's range — e.g. `keyfacts` takes 3 to 5 |
| `comparison` grids are rectangular: every entity has a value for every attribute, or the cell is explicitly marked absent |
| `callout` gating — **open, L28** |

#### 4.1.5 The allow-list is an attack surface

D7's allow-list permits ordinals, decades and counts of listed items, so "three reasons" and "the 1990s" pass. That means a *fabricated* decade or count also passes. Keep the list **minimal and versioned**, and report `allowlist_hits` in telemetry so its growth is visible rather than gradual.

---

### 4.2 Failure handling — the downgrade ladder

**Decision D6.** A validation failure must not silently cost the article its visual, and must not become a licence to draw something pointless instead.

#### 4.2.1 Three rules that stop a downgrade being a new visual

A downgrade is **the same claim re-rendered in a weaker form**. It is never permission to go and find something else to draw.

1. **The element set may not change.** A downgrade renders the identical `element_ids`. If a type only fits after dropping elements, it is not a downgrade — it is a different, weaker visual, and it is rejected. This single rule closes the most common route to a technically-valid-but-pointless visual.
2. **The `purpose` must survive.** Downgrade edges are declared in a static table together with the purposes each preserves. `line → bar` preserves `trend` only where the time axis is safely categorical. `slope → bar` destroys the before/after pairing and is therefore **not an edge at all**.
3. **The bar rises with depth** — §2.2.

#### 4.2.2 Escalating scrutiny

| Depth | What it is | Acceptance floor |
| --- | --- | --- |
| 0 | The planner's chosen type | Validator only |
| 1 | First downgrade | Validator **plus** component floors at the corpus **median** for the target type |
| 2 | Second downgrade, or fallback to `table` | Validator **plus** floors at the corpus **75th percentile**, **plus** a non-empty `annotations` entry |
| 3+ | — | Not permitted. Emit `none` |

**Floors are computed from depth-0 published visuals only, over a rolling window, and stored as versioned config — not constants.** Including downgrades in the window creates a feedback loop: downgrades score lower, drag the median down, lower the floor, and permit more downgrades. The bar would loosen precisely as quality fell (R8).

#### 4.2.3 Cross-family downgrades are forbidden

| From | To | Allowed |
| --- | --- | --- |
| `line` | `bar` | ✅ if the time axis is safely categorical |
| `bubble` | `scatter` | ✅ drops the size channel, keeps the relationship |
| `stacked_bar` | grouped `bar` | ✅ when parts are not exhaustive |
| any chart | `table` | ✅ at depth 2 only, with an annotation |
| any chart | any infographic | ❌ **never** — this is the pointless-visual outcome the ladder exists to prevent |
| `diagram` | any chart | ❌ never |
| `diagram` | `none` | ✅ the only diagram fallback |

#### 4.2.4 The justification requirement

At depth ≥ 1 the rendered visual must carry a machine-checkable justification: the surviving `purpose`, the edge taken, and the annotation element that makes the weaker form still worth showing. **A downgrade with no annotation fails.** This is what prevents depth 1 from quietly becoming the default path.

#### 4.2.5 The flag

```text
VISUAL_DOWNGRADE = ladder | off
```

`off` reverts to strict no-visual-on-failure: the first rejection ends it. The flag state is recorded on every visual, so the two regimes are **compared on `visual_keep_rate`** rather than argued about.

> **The metric that decides whether the ladder was a good idea:** `visual_keep_rate` at depth ≥ 1 against depth 0. If downgraded visuals are kept materially less often, the ladder is manufacturing exactly the pointless visuals it was gated against, and the flag goes to `off` — the ladder is deleted, not tuned.

---

### 4.3 The Visual Compiler

Deterministic templates, one per type, turning a validated Visual Plan into a renderable specification.

```text
VisualPlan  →  specification  →  rendered visual
```

**The model chooses the semantic type; code chooses the implementation.** That principle holds regardless of which specification format is chosen in §4.

#### 4.3.1 Wave plan (D2)

The full vocabulary is declared from day one so telemetry sees every planner choice. Templates ship in waves; a planned type with no template downgrades deterministically and the downgrade is logged.

| Wave | Types |
| --- | --- |
| 1 | `bar`, `line`, `dot`, `table` |
| 2 | `scatter`, `slope`, `stacked_bar`, `area` |
| 3 | `histogram`, `pie`, `timeline`, `bubble` |
| Family 2 | `flow` — gated on L18 |
| Family 3 | `comparison`, `quotecard`, `whowhat`, `keyfacts`, `callout` — `callout` gated on L28 |

> **The wave mechanism launders planner errors as successes if you let it.** `planned_type` and `rendered_type` are **separate telemetry fields and both must be reported**. Distribution computed only on `rendered_type` measures the downgrade table, not the planner — the opposite of what the metric exists for (L2).

#### 4.3.2 Compiler responsibilities

| Owns | Does not own |
| --- | --- |
| Layout, geometry, scales, axis ranges | Which elements appear |
| Colour and typography | What the visual means |
| Deterministic truncation of long quotes and claims | Rewriting any text |
| Derived-value computation from the provenance chain | Choosing what to aggregate |
| Alt-text assembly from plan + elements | Authoring prose |
| Accessibility: contrast, focus order, screen-reader structure | — |

**Alt text is generated deterministically** from the plan and the elements, never as free model prose. It is the last unguarded prose channel in the system if it is not (R11).

---

### 4.4 Rendering and frontend — OPEN

**Status: deliberately unresolved.** This decision depends on what the repository already builds, what the published site already ships, and what the frontend can do — context this document does not have. **Do not freeze it without that context.** L18 and L21.

#### 4.4.1 Stated requirements

| Requirement | Means | Constrains |
| --- | --- | --- |
| **Extreme fidelity** | Faithful, high-resolution, no approximation or artefacts at any viewport | Output format and renderer |
| **High visual information compression** | Maximum meaning per unit of screen area — dense, not decorative | Compiler templates; this is the same property `structural_efficiency` measures |
| **Rich colour** | A broad, controllable palette rather than a fixed default | A theming layer, still subject to contrast and colour-vision safety |
| **Some interactivity** | Hover, focus, filter, reveal-on-demand | **This is the requirement that conflicts with the design as literally written** |

#### 4.4.2 The tension, and how to dissolve it

§1 says code owns rendering and the flow terminates in a static artifact that can be validated, diffed and archived. Interactivity is incompatible with that *as literally written*. The resolution is one distinction:

> **Determinism belongs to the specification, not to the pixels.** Code must deterministically produce the visual *spec* from validated elements. Where that spec becomes pixels — at build time, in the browser, or both — is a separate decision that does not weaken the integrity guarantee.

| Shape | How | Fidelity | Interactive | Archivable | Cost |
| --- | --- | --- | --- | --- | --- |
| Build-time static only | Compiler emits the image; ship the file | High | ❌ | ✅ | Lowest |
| Client-side | Ship the spec; the browser renders | High | ✅ native | Spec only | A JS payload on every page |
| **Progressive enhancement** | Bake static at build for fidelity, accessibility, no-JS readers and archival; hydrate into an interactive view where JS is available | High | ✅ | ✅ | Two paths to build and keep in sync |

#### 4.4.3 Renderer candidates

| Option | Build dependency | Interactivity | Note |
| --- | --- | --- | --- |
| Vega-Lite, build-time | Node toolchain | None baked | Already the natural chart target; **carries an interaction grammar natively** |
| Vega-Lite, client-side | JS payload | ✅ | Interactivity is close to free on the chart path |
| Graphviz `dot` | One native binary | None | Mature layout, diffable, no browser; harder to style to a house design |
| Mermaid via CLI | Headless Chromium at build | None | A browser in the build to draw boxes and arrows |
| Mermaid client-side | JS bundle | Limited | Output stops being a build artifact you can validate |
| Hand-rolled emitter | None | Whatever you build | Full control over fidelity, compression and colour; most work |

> **Asymmetry the next agent must not miss:** interactivity is nearly free on the **chart** path because Vega-Lite has an interaction grammar. The **diagram** path has no equivalent — `dot` and Mermaid output have no interaction model at all, so interactive diagrams mean a hand-built emitter or a frontend graph library. **The two paths do not cost the same.**

#### 4.4.4 Questions requiring repository context

1. Is interactivity required on **charts, diagrams, or both**? The cost difference is large.
2. Does the published site already ship JS? If not, does adding it break the static-hosting constraints the project already operates under?
3. Is the archival requirement — a diffable artifact per published visual — binding? If yes, progressive enhancement is effectively forced.
4. Does "rich colour" mean per-article palettes, a house palette with wide range, or reader-selectable themes? Each puts the theming layer somewhere different.
5. Where does accessibility live — baked into the static output, or re-derived client-side? Splitting it across both is how it silently regresses.

#### 4.4.5 Consequences to handle before, not after

- **Pin renderer versions.** A minor version bump changes pixel output, archived artifacts stop reproducing, and diffs fill with noise until nobody trusts them. Record `renderer_version` per visual and treat a bump as a corpus event requiring an intentional re-render (R17).
- **Split `compile_ms` from `render_ms` now**, not after rendering moves client-side. A single `render_time` field becomes ambiguous the moment the split happens.
- **A candidate worth evaluating:** Draco (Moritz et al., InfoVis 2019) models visualization design knowledge as weighted constraints solved with ASP, emitting Vega-Lite. It could replace part of the Visual Validator rather than being written from scratch. See §7.


---

## 5. Measurement


Four families of measurement, in the order they should be built:

| # | Family | Answers | Cost |
| --- | --- | --- | --- |
| 1 | **Upstream** (§1) | Is the input any good? | Free, plus a quarterly manual sample |
| 2 | **Machine quality** (§2) | Is the visual structurally sound and factually safe? | Free |
| 3 | **Cost** (§3) | What does this pipeline actually cost? | Free |
| 4 | **Human** (§4) | Does the visual help a reader? | Expensive, sampled |

**Every rate in every family is reported per Article Visual Potential class** (§2.4). A rate over all articles mixes populations that were never comparable.

---

### 5.1 Upstream — extraction and article potential

**Decision D13.** Every visual metric is conditioned on extraction quality. Without this family, a planner "regression" and an extractor that started missing numbers are indistinguishable — and the planner gets blamed for both. This is R2, rated the largest blind spot in the design.

#### 5.1.1 Metrics

| Metric | Cost | Catches |
| --- | --- | --- |
| `elements_per_article` by `kind` | Free | Collapse or drift in extraction volume |
| `tier2_label_completeness` | Free | Quantities missing `measure` / `entity` / `time` — unusable for charts |
| `span_integrity_rate` | Free | Span drift. Every stored excerpt must still match its offsets (R5) |
| **`extractable_but_unused_rate`** | Free | **Elements extracted but never selected by any plan.** When it rises, the planner is under-reading the table, not the extractor under-producing. The most useful free diagnostic in the system |
| `merge_rate` | Free | Canonicalisation aggressiveness (R4) |
| `tier1_recall` / `tier1_precision` | Manual | Whether the extractor finds what is there |
| `tier2_label_accuracy` | Manual | Whether `measure` / `dimension` labels are right |

#### 5.1.2 Validation in three tiers

A varied corpus defeats any single validation method. Use three, ascending in cost.

| Tier | Method | Cadence | Catches | Cost |
| --- | --- | --- | --- | --- |
| **1 — Canary fixtures** | A small fixed set of articles with hand-verified complete element tables. Extraction must return exactly those | Every build | Regression and collapse, instantly | Free after setup. **Reuse the project's existing canary mechanism; do not build a second** |
| **2 — Free proxies** | The five free metrics above, per potential class | Every build | Drift, planner under-reading, span corruption | Free |
| **3 — Manual ground truth** | 50 articles **stratified across potential classes**, double-annotated, agreement reported, refreshed quarterly | Quarterly | Actual recall and precision | Real and recurring |

> **The stratification in tier 3 is the part most likely to be skipped and the most important.** Fifty randomly drawn news articles will be overwhelmingly `narrative` and will say nothing about extraction quality on the `chartable` articles where it matters most.

#### 5.1.3 Improvement order

1. **Tier 2 label completeness.** A quantity without a `measure` is invisible to the planner — worse than a missed number, because it occupies a slot while being unusable.
2. **Recall on `chartable` articles.** Precision is partly self-correcting; a wrong element tends to fail validation. A missed element is silent.
3. **Non-numeric kinds.** Entities and quotes are new surface and will start weak.
4. **Normalisation** (`time`, `unit`) last — it only matters once the elements exist.

---

### 5.2 Machine quality

#### 5.2.1 The five components

Each is computed from the plan, the elements and the frozen summary. All are pure functions, versioned as `components_version`.

| # | Component | Definition | Target |
| --- | --- | --- | --- |
| **A** | `data_coverage` | Displayed values resolving to Tier 1 elements ÷ all displayed values | See the invariant note below |
| **B** | `relationship_score` | Whether the selected elements form a meaningful structure: `time → quantity`, `entity → quantity`, `x → y`, `category → quantity`, `before → after`. Deterministic from Tier 2 metadata | 1 when all selected elements share measure, compatible units, compatible dimension and an appropriate time/entity relationship |
| **C** | `structural_efficiency` | `distinct_supported_elements ÷ visual_encoding_elements` | Higher is better. A visual with 3 elements and 14 decorative encodings scores worse than one with 8 elements and 5 meaningful ones |
| **D** | `redundancy` | Elements already explicitly stated in the summary ÷ elements communicated by the visual | High redundancy is not automatically bad, but a visual adding no new relationship is weak |
| **E** | `information_delta` | Relationships visible in the visual − relationships explicitly represented in the summary | The machine approximation of "would this add anything beyond prose?" |

**Note on A.** An earlier draft called `trusted_data_ratio` a build-failing invariant fixed at 1.0 forever. Derived values break that as literally stated. The corrected position is in §2.3.2: **the invariant is that every displayed value resolves to a Tier 1 element or a complete derived chain**, and `data_coverage` is a *report*, expected below 1.0 wherever histograms or pies publish.

*Illustrative — high delta:*

```text
summary:  "Exports rose substantially."
visual:   2023 < 2024 < 2025
```

The visual contributes the comparative structure.

*Illustrative — low delta:*

```text
summary:  "Exports were 2.9m, 3.1m and 4.2m."
visual:   an identical three-bar chart
```

#### 5.2.2 Every component has a pathology

Pushed to its extreme, each produces a failure. Ship the counterweight with the component.

| Component | Pushes toward | Pathological extreme | Counterweight |
| --- | --- | --- | --- |
| `data_coverage` | Plot only extracted values | Refuses any visual needing a total or share | Derived values with provenance, counted separately |
| `relationship_score` | Homogeneous element sets | Refuses legitimate two-measure comparisons | An explicit multi-measure plan type with its own rules |
| `information_delta` | Visuals that say what prose does not | **Summaries stripped of numbers so the visual scores higher** | Compute against a **frozen** summary; the planner never sees the score; add summary informativeness (R7) |
| `structural_efficiency` | Minimal chrome | Strips axis labels, units, sources | Accessibility and attribution elements are **exempt from the denominator** |
| `redundancy` | Novelty over clarity | Penalises a visual that usefully repeats the headline number | Read beside keep-rate, never alone |
| `semantic_coherence` | Elements of the same kind | Rejects any article whose labels vary in wording | Canonicalisation + alias ledger, conservatively tuned |

#### 5.2.3 The quality index

**Decision D5. The `0.30 / 0.25 / 0.20 / 0.15 / 0.10` vector is withdrawn.** Those coefficients were chosen because they look reasonable and sum to 1. No experiment produced them. A weighted sum of five partly-correlated proxies with invented coefficients yields a number that moves without being interpretable — and once it is on a dashboard, the team optimises the guess.

###### What the index is for

A per-visual score in `[0,1]` answering: *how much genuine structural information does this visual add, relative to the machinery it spends and what the prose already said?* A **triage instrument**, not a verdict.

| For | Not for |
| --- | --- |
| Ranking a day's visuals so reviewers see the worst and best first | Gating publication |
| Detecting regression across builds | Declaring one visual better than another of a different type |
| Isolating failure classes — "every `slope` scores low on relationship" | Proving a visual is good |

###### How it changes visuals — three paths, all deliberate

| Path | Mechanism | Risk |
| --- | --- | --- |
| **Review triage** | Low-scoring visuals surface to reviewers first | None. The safe path — adopt it first |
| **Validator thresholds** | Component floors become reject conditions | Depresses publish rate; change one threshold per release |
| **Planner feedback** | Aggregate failure classes inform prompt or fine-tune changes | **The planner must never see its own score.** Scoring the thing being optimised, inside the loop, is reward hacking |

###### Learning the weights instead of picking them

This is not novel. **Draco** (Moritz, Wang, Nelson, Lin, Smith, Howe & Heer, IEEE InfoVis 2019, Best Paper) models visualization design knowledge as a constraint collection and *learns the weights on its soft constraints from experimental data* — including weights learned directly from graphical-perception experiments — then solves and emits Vega-Lite, the same target as the Visual Compiler. The mechanism transplants directly.

1. **Collect pairwise preferences, not absolute ratings.** Cheaper to obtain and far more stable across reviewers than a 1–5 scale.
2. **Fit a linear ranking model** — RankSVM, Bradley–Terry, or logistic regression on component *differences* between pair members. The fitted coefficients **are** the weights.
3. **Refit on a schedule**, not per batch — monthly, or every *N* new pairs, whichever is later.
4. **Guardrails.** Hold out 20% of pairs. Refuse to promote weights unless holdout ranking accuracy improves. Clamp per-refit coefficient movement. Keep the previous version for instant rollback. Stamp `weight_version` on every scored visual, forever.
5. **Cold start with equal weights (0.20 each).** Equal weighting is an honest statement of ignorance. The old vector was a false statement of knowledge.

```text
visual_score.py
  components(plan, elements, summary) -> dict[str, float]   # pure, deterministic, versioned
  score(components, weights)          -> float              # linear, no branching

weights.json
  { "weight_version": 7, "fitted_at": "…", "n_pairs": 412,
    "holdout_accuracy": 0.71, "coef": { … } }

fit_weights.py                                              # reads the ledger, writes a NEW version
```

**Version `components()` separately from `weights.json`.** If both change in one release, historical scores become incomparable and the entire time series is lost.

> **Fitting on survivors is a defect (R3, D12).** The labelled set must include a sample of **rejected** plans rendered into `review/` but never published. Fitting only on visuals that passed validation is selection on the dependent variable: the weights end up miscalibrated exactly at the accept/reject boundary they inform.

#### 5.2.4 Comparing scores across articles

A raw score is **not** comparable between a two-number diary piece and a twelve-number market report.

- Report **percentile rank within the corpus**, never the raw score.
- **Stratify** by potential class, family and element-count band; z-score within stratum before aggregating.
- Publish a **rolling 28-day median** as the headline, never a per-article number.
- Track the **distribution**, not the mean — a bimodal distribution is the interesting finding and a mean hides it.

#### 5.2.5 Literature anchors

**Stated plainly: there is no published industry average for "chart keep rate" or for any composite visual-quality score.** These metrics are bespoke. Any figure quoted from the internet as a benchmark for them is quoting nothing. What *does* exist is measured evidence for the **components**:

| Anchor | Establishes | Use here |
| --- | --- | --- |
| Cleveland & McGill, *Graphical Perception*, JASA 79(387), 1984 | The empirical accuracy ranking of elementary perceptual tasks: position on a common scale, then position on non-aligned scales, then length / direction / angle, then area, then volume / curvature, then colour saturation | Fixed prior on type effectiveness; the evidential basis for gating `pie` (angle) and `bubble` (area) |
| Saket, Endert & Demiralp, *Task-Based Effectiveness of Basic Visualizations*, IEEE TVCG (arXiv:1709.08546) | Crowdsourced effectiveness of Table, Line, Bar, Scatterplot and Pie across ten tasks at 5–34 data points | Seeds the `purpose` → `type` prior empirically. Our visuals sit in the same data-size band, so the results transfer |
| Moritz et al., *Draco*, IEEE InfoVis 2019 | Design knowledge as weighted constraints with weights learned from perception experiments | The weight-learning mechanism above; a candidate replacement for part of the validator |
| Tufte, data-ink ratio | Proportion of ink devoted to data | The operational definition behind `structural_efficiency` |

#### 5.2.6 Tuning order

1. **`purpose` → `type` prior** — the largest single lever on keep-rate. Seed from Saket et al.
2. **Validator thresholds** — controls publish rate directly.
3. **Index weights** — last. They cannot be fitted before labels exist.

**Never tune the summary prompt and a visual metric in the same release.** You lose attribution and cannot tell which change moved the number.

---

### 5.3 Cost and performance

The central architectural claim — one larger model doing more beats two smaller models doing less — is an **efficiency claim**, and an efficiency claim with no cost instrumentation is unfalsifiable.

| Metric | Definition | Decides |
| --- | --- | --- |
| `wall_clock_total` | End minus start, per article and per run | The only user-relevant figure. Everything below explains movements in it |
| `model_startup_ms` | Load weights to first-token readiness | **Proves or refutes the one-model claim.** The prior architecture paid startup twice; this should pay once. If it does not, the headline benefit is not realised |
| `prefill_ms` | Input processing before the first output token, **per call** | **Prices D1** — §3.1 |
| `decode_ms` | Output token generation | The direct price of a wider schema |
| `tokens_in` / `tokens_out` | Per call, split by stage (`summary`, `plan`) | Makes combined-output overhead visible. A schema growing quietly shows here first |
| `schema_retry_count` | Constrained-decoding failures forcing a retry | A silent latency multiplier |
| `compile_ms` | Plan → specification | Should be negligible. If not, a template is doing something it should not |
| `render_ms` | Specification → rendered visual | **Split from `compile_ms` before any move to client-side rendering**, not after |
| `validation_ms` | Validator wall time | Cheap now; grows with each rule |
| `evaluation_cost` | Config-B plans, rejected-plan renders, review queue generation | **Reported separately.** D9 and D12 add real inference and render cost that publication metrics do not see (R15) |
| `cost_per_published_visual` | `wall_clock_total` ÷ published visuals | The efficiency figure that matters. A run that doubles in cost and triples in published visuals got cheaper |

All stage timings must **sum to `wall_clock_total`**, with any residual reported as `unattributed_ms`. A timing set that does not reconcile is how invisible costs survive.

#### 5.3.1 The prefill question — D1's real price

D1 splits one inference into two, so the article is prefilled twice unless the KV cache is reused. On a long article prefill dominates, so the naive implementation could cost close to **double** the model time for a benefit that is about failure isolation rather than speed.

| Implementation | Prefill cost | Note |
| --- | --- | --- |
| Two independent calls | ≈ 2× | The naive path. Measure it; do not ship it without knowing the number |
| **Two calls, KV cache reused** | ≈ 1× + delta | **The intended implementation.** Call 2 continues call 1's context rather than rebuilding it |
| One call, joint schema | 1× | Cheapest, and why L1 remains genuinely open |

> **Report the `prefill_ms` ratio between call 1 and call 2 explicitly.** Near 1.0 means the cache is not being reused, and D1 is costing roughly double for failure isolation alone — the strongest available argument for reverting to a single call. A measurement, not a debate (L27).

#### 5.3.2 Retries must perturb something

A retry against identical context reproduces the identical failure. `schema_retry_count` then goes bimodal — 0 or the cap — and the retries buy only latency. **Every retry must change something**: the rejection reason fed back, or the temperature (R9).

#### 5.3.3 Budget

No threshold is set here; setting one now would repeat the mistake §2.3 corrects.

1. Record every metric from the first build, **before** any optimisation.
2. After one corpus month, set the budget at an observed percentile of the run's own distribution and version it.
3. On breach, escalate cheapest-first: **schema width → retry rate → KV cache reuse → call topology (L1) → model size.**

**Model size is the last lever, not the first.** It is the most disruptive change available and the one most often reached for out of habit.

---

### 5.4 The human instrument

No LLM judges the visual. Humans answer a small set of questions — but **bare questions produce bare disagreement.** Two reviewers read "moderately" differently, and the resulting keep-rate measures the reviewers more than the visuals. The rubric is not optional polish.

#### 5.4.1 The core instrument — six questions, fixed order

Reviewers see the **article and the visual only**. Never the plan, never `why`, never the machine scores.

###### Q1 — Comprehension · *scale 1–5*

| | |
| --- | --- |
| **Purpose** | Whether the visual reduced the effort of understanding the article |
| **1 — not at all** | You understood the article the same with or without it |
| **3 — moderately** | It saved you re-reading a passage |
| **5 — essential** | Without it you would have had to reconstruct the relationship yourself from scattered sentences |
| **Not asking** | Whether it is attractive, or whether the article is good |

###### Q2 — Structural contribution · *yes / no*

| | |
| --- | --- |
| **Purpose** | Whether the visual carries a relationship the prose leaves implicit |
| **Yes** | Prose says "exports rose sharply"; the visual shows the rise was concentrated in one year |
| **No** | Prose lists three numbers; the visual shows the same three as bars |
| **Not asking** | Whether the relationship is interesting — only whether the visual is where you found it |

###### Q3 — Form appropriateness · *yes / no*

| | |
| --- | --- |
| **Purpose** | Whether the type suits the data shape |
| **Yes** | Time series drawn as a line |
| **No** | Ranking drawn as a pie; two unrelated measures on one axis |
| **Not asking** | Whether a *different* visual would be marginally better. Answer No only if the chosen form actively obstructs the reading |

###### Q4 — Faithfulness · *yes / no*

| | |
| --- | --- |
| **Purpose** | Whether the visual asserts anything the article does not |
| **No if** | A value differs from the article; a category is invented; an axis implies a total never stated; an arrow asserts causality the article does not |
| **Not asking** | Whether the *article* is correct — only whether the visual is faithful to it |
| **Escalation** | Any `No` is a **defect, not a rating**. It files a record naming the offending `element_id` or `edge_id` |

###### Q4b — Relationship correctness · *yes / no*

| | |
| --- | --- |
| **Purpose** | Whether the visual compares things that are actually comparable |
| **No if** | Revenue plotted against headcount as one series; two units on one axis; parts charted against a whole they are not part of |
| **Why separate from Q4** | A faithful visual can still assert a false *relationship*. Every value may be correct while the comparison is meaningless — the more serious semantic error |

###### Q5 — Keep · *yes / no*

| | |
| --- | --- |
| **Purpose** | The headline decision, asked **last**, after the reviewer has reasoned through Q1–Q4b |
| **Not asking** | Whether it could be improved. Only: ship it as it stands, or drop it |

> **Order is enforced and answers lock.** A reviewer who commits to "keep" first will rationalise Q1–Q4 to match. The review page does not allow revisiting earlier answers after Q5.

#### 5.4.2 The `none` control arm

For queue items the planner declined to illustrate, the instrument is a different question and its answers are **never aggregated with Q1–Q5**:

> **Would a visual have helped this article?**
> `No` / `Maybe` / `Yes — and I can say what it would show`

The third option's free text is the most valuable label in the system: it names a visual the planner failed to imagine.

#### 5.4.3 Measuring compression directly — the timed arm

Preference is a proxy. Compression is a **cost of comprehension**, and it can be measured directly even on a static site, because the review page runs JavaScript locally and exports what it records.

For a sampled article the reviewer is assigned one condition:

```text
Condition A:  article prose only
Condition B:  article prose + the visual
```

Then one factual comprehension question whose answer requires the key relationship. The page records **time-to-answer** and **correctness** in `localStorage` and exports them with the labels. No network, no server.

```text
comprehension_time_delta      =  median(time | A)  −  median(time | B)
comprehension_accuracy_delta  =  accuracy(B)  −  accuracy(A)
```

| Requirement | Reason |
| --- | --- |
| **Between-subjects** — a reviewer sees a given article in one condition only | Having read it once, they cannot un-know it |
| Assignment seeded and recorded on the queue | Reproducibility, and so the split can be checked for balance |
| The question is authored from the **elements**, not from the visual | A question written from the visual is one the visual is guaranteed to answer |
| Timing starts on render, stops on submit | Anything else measures reading speed |
| Report medians and *n*, never means | Small samples with a long right tail |
| Discard sessions with implausible timings | Interruptions dominate unsupervised review |

**Honest limits:** small *n*, reviewers are not readers, and answering a comprehension question is not the same as being informed. It remains a large improvement on stated preference alone, at the cost of one extra page in `review/`.

#### 5.4.4 Headline human metrics

```text
visual_keep_rate  =  reviewers answering "yes, keep it"  ÷  total reviewed visuals
```

Far more meaningful than "chart rate". *Illustrative only — these are placeholders for measurement, not targets:*

| System | Chart rate | Keep rate |
| --- | --- | --- |
| Current | 15% of articles get a visual | 42% worth keeping |
| Target | 12% get a visual | 81% worth keeping |

The second system is clearly better despite the lower rate. That is the whole argument for measuring keep-rate.

```text
human_visual_gain  ←  "Without the visual, would you understand the key
                       relationship equally quickly?"
                       No difference / Slightly worse / Moderately worse / Much worse
```

---

### 5.5 The KPI set

Reported per potential class, and **never blended across families**.

#### 5.5.1 Machine

| Metric | Tells us |
| --- | --- |
| `visual_decision_rate` | How often the model proposes a visual |
| `visual_publish_rate` | How often a proposal survives validation |
| `visual_rejection_rate` | Whether plans are structurally invalid |
| `data_coverage` | Share of displayed values resolving directly to Tier 1 elements |
| `derived_value_rate` | Share that are derived — read beside type distribution |
| `semantic_coherence_rate` | Whether selected elements represent one analytical relationship |
| `type_distribution` × family | Whether one type is over-used. Computed on **`planned_type`**, with `rendered_type` reported alongside |
| `planned_type_entropy` | **Read jointly with rejection rate** — see §5.4 |
| `visual_information_delta` | Structure added beyond prose |
| `downgrade_rate` | Share published below the planner's choice |
| `summary_faithfulness` | **Regression guard** — did pursuing a visual degrade the summary? |
| `summary_informativeness` | Fact coverage of the summary against the element table (R7) |
| `allowlist_hits` | Growth of the D7 numeral allow-list |

#### 5.5.2 Human

| Metric | Tells us |
| --- | --- |
| `visual_keep_rate` | Whether people want the visual |
| `human_visual_gain` | Whether it materially improves comprehension |
| `chart_appropriateness` | Whether the representation is right — Q3 |
| `visual_factual_accuracy` | Whether it faithfully represents the article — Q4 |
| `relationship_correctness` | Whether the comparison is valid — Q4b |
| `missed_visual_rate` | Articles that deserved a visual and got none |
| `comprehension_time_delta` | Objective compression signal |
| `inter_reviewer_agreement` | **A keep-rate published without this beside it is not quotable** |

#### 5.5.3 `summary_faithfulness` is the most important addition

Every other metric asks whether the visual is good. This one asks whether **pursuing** the visual made the summary worse — the regression this architecture is most likely to cause and least likely to notice, because nothing else in the set looks at the summary at all.

If the project already runs a faithfulness scorer, **wire it in as-is** and report it beside the visual metrics. Do not build a second (L25).

Faithfulness alone is not sufficient. Under D1 one model writes the summary then the plan; if terser summaries yield higher `information_delta`, the incentive to strip numbers from prose is structural — and a summary with fewer claims is *more* faithful, so faithfulness passes. `summary_informativeness` is the companion that catches it (R7).

#### 5.5.4 The two metrics that must never be read alone

| Metric | Alone it says | Jointly it says |
| --- | --- | --- |
| `visual_rejection_rate` falling | "The planner improved" | Falling **with** `planned_type_entropy` falling = the planner has learned to propose only what passes and stopped exploring. Capitulation, not improvement (R1) |
| `type_distribution` concentrating | "We over-use bar charts" | Read beside `chart_appropriateness` and potential class. **Uniform is the wrong ideal** — most news quantities genuinely are category comparisons, so a large `bar` share may be correct (L11) |

**Never set a diversity target.** Making entropy a goal invites the planner to diversify into wrong types: better entropy, worse visuals.

*Illustrative failure signature:*

```text
bar       94%
line       4%
dot        1%
scatter    1%
```

That distribution alone shows the architecture is not exercising visual intelligence. No human evaluator is needed to discover it.

---

### 5.6 The two loops

| | Machine Loop | Human Loop |
| --- | --- | --- |
| **Runs on** | Every article | A stratified sample |
| **Cadence** | Every build | Periodic |
| **Cost** | Free | Real, recurring |
| **Gates** | **Publication** | Nothing |
| **Answers** | Is it structurally sound and factually safe? | Does it actually help a reader? |
| **Inputs** | Plan, elements, validation result | Published visuals, rejected samples, config-B variants, `none` arm |
| **Outputs** | Metrics, typed rejection reasons, failure classes | Keep-rate, gain, agreement, learned weights |

**How they interlock.** The Machine Loop is the fast inner loop and the gate; the Human Loop is the slow outer loop and the scoreboard. Because human answers are stored against the same metadata the machine metrics use, the Human Loop is what eventually lets you **validate the machine metrics themselves** — testing whether `information_delta` actually predicts `visual_keep_rate`. Until that correlation is measured, the quality index stays a diagnostic and never a gate.

#### 5.6.1 Withdrawing the human, in phases

| Phase | Human role | Machine role | Exit condition |
| --- | --- | --- | --- |
| **Bootstrap** | Labels every sampled item using the Q1–Q5 rubric | Emits components only; no composite score | ~200 labelled visuals, stratified by potential class |
| **Calibrate** | Pairwise judgements only | Fits weights; reports holdout ranking accuracy | Holdout accuracy stable across two consecutive refits |
| **Automate** | Audits a shrinking random sample; adjudicates disagreements | Scores everything; triages the review queue | Machine–human rank correlation above an agreed floor |
| **Steady state** | Periodic drift check | Full scoring; scheduled refits | Ongoing |

The human is never removed entirely — they become the drift detector.


---

## 6. Operations


---

### 6.1 Telemetry — one canonical event

**There is exactly one telemetry event per visual attempt, and this is its schema.** Earlier drafts carried two overlapping lists that had already diverged; if a field is not here, it is not recorded.

```text
# identity and versioning
visual_id
article_id
plan_version
components_version
weight_version
ledger_version
potential_classifier_version
renderer_version
compiler_wave

# article context
potential_classes[]            all classes that apply
potential_primary              the class rates are reported against
elements_total  by kind
elements_tier2_complete

# the decision
decision                       chart | diagram | infographic | none
family
purpose
confidence
planned_type                   what the planner chose
rendered_type                  what was actually drawn
downgrade_depth                0 = no downgrade
downgrade_reason
downgrade_edge                 e.g. "line->bar"
gate_floor_applied
element_ids[]

# validation
validation_result              pass | fail
rejection_reason               typed enum, never free text
rejection_stage
allowlist_hits

# integrity
displayed_values_total
values_from_tier1
values_derived
derived_provenance_complete    invariant — must always be true
span_integrity_pass            invariant — must always be true

# quality components (never a composite unless weight_version is set)
data_coverage
relationship_score
structural_efficiency
redundancy
information_delta
semantic_coherence

# summary regression guards
summary_faithfulness
summary_informativeness

# cost
model_startup_ms
prefill_ms_call1
prefill_ms_call2
decode_ms_call1
decode_ms_call2
tokens_in_call1   tokens_out_call1
tokens_in_call2   tokens_out_call2
schema_retry_count
validation_ms
compile_ms
render_ms
wall_clock_total
unattributed_ms                must reconcile to zero within tolerance

# flags in force
VISUAL_DOWNGRADE
REVIEW_MODE
none_arm_ratio
```

#### 6.1.1 Rules

| Rule | Reason |
| --- | --- |
| `planned_type` and `rendered_type` are **both** always recorded | Distribution on `rendered_type` alone measures the downgrade table, not the planner |
| `rejection_reason` is a **typed enum**, never free text | Free-text reasons cannot be aggregated into failure classes |
| Tier 1 and Tier 2 counts are **never summed** into one "trusted" figure | A labelling error and a correctness bug are different incidents |
| Timings must reconcile: `unattributed_ms` ≈ 0 | Unreconciled timings are how invisible costs survive |
| A composite score is emitted **only** when `weight_version` is set | Before weights are fitted, there is no composite — only components |
| Every published visual stores its **full input tuple** — plan, element ids, all versions | Without it, a compiler defect has an unknowable blast radius and nothing can be re-rendered (R12) |

---

### 6.2 Console — the observability dashboard

#### 6.2.1 Required panels

| Panel | Reads | Alarm condition |
| --- | --- | --- |
| Pipeline funnel: articles → elements → plans → validated → published, **per potential class** | `potential_primary`, `validation_result` | — |
| Downgrade funnel: planned → validated → depth 1 → depth 2 → rendered → `none` | `downgrade_depth` | — |
| Downgrade rate | `downgrade_depth` | Sustained high rate indicates a **planner** defect, not a rendering problem |
| Planned-vs-rendered type matrix, heatmap, all types both axes | `planned_type` × `rendered_type` | Any single edge dominating all downgrades |
| Rejection reason breakdown | `rejection_reason` | A new reason class appearing |
| **Rejection rate × planned-type entropy**, on one chart | both | **Both falling together = capitulation** (R1) |
| **Keep-rate by downgrade depth** | keep-rate × `downgrade_depth` | Depth-1 keep-rate materially below depth-0 → the ladder is manufacturing pointless visuals |
| Ladder on/off comparison | `VISUAL_DOWNGRADE` | — |
| Integrity invariants | `derived_provenance_complete`, `span_integrity_pass` | **Any failure is a build break, not an alarm** |
| Extraction health | `elements_per_article`, `tier2_label_completeness`, `extractable_but_unused_rate`, `merge_rate` | Rising unused rate = planner under-reading |
| Cost per published visual, and the call-1/call-2 `prefill_ms` ratio | cost family | Ratio near 1.0 → KV cache not reused |
| Summary regression | `summary_faithfulness`, `summary_informativeness` | Either falling after a visual-side change |
| Repetition | `visual_repetition_rate` | The same element set + type recurring across a rolling window (R18) |

#### 6.2.2 Thresholds are deliberately unset

Setting them now would repeat the mistake the quality index corrects — inventing numbers. **Run for one corpus month, then set each threshold at an observed percentile of its own distribution and version it alongside the other config** (L17).

An unset alarm catches nothing for a month. Accepted: a wrong alarm trains people to ignore alarms, which is worse and harder to undo.

---

### 6.3 Feedback capture without a server

**Binding constraint.** The application is **stateless and serverless** — a published static site. The consumer cannot click a feedback control, and there is no backend to receive one if they could. **The reviewer is a different population from the consumer.** Any design assuming in-product feedback is invalid here.

#### 6.3.1 The repository is the database

| Element | Mechanism |
| --- | --- |
| **Review queue** | The build emits `review/queue.<date>.json` — a deterministic, seeded, stratified sample carrying the Visual Plan, the Trusted Elements, the machine components and a stable `visual_id`. Same seed → same queue for every reviewer, so independent answers are joinable |
| **Review surface** | A static `review/` page shipped with the site. Loads the queue, renders each item beside its article, holds answers in `localStorage`, exports `labels.jsonl`. **No network calls, no server** |
| **Isolation from readers** | `review/` is `noindex`, unlinked from any published page, and excluded from sitemaps and feeds. It ships with the site only because that is the cheapest distribution — it is not part of the product |
| **Transport** | The reviewer commits `labels/<reviewer_id>.<date>.jsonl`. Version control provides the durable store, the audit trail and access control in one mechanism |
| **Alternative transport** | A CLI (`review.py`) writing the identical schema, for terminal-preferring reviewers |
| **Ingestion** | A scheduled job validates, de-duplicates and appends to the append-only **Feedback Ledger** |

**Rejected:** any third-party form or hosted service. It adds a dependency, splits the audit trail from the corpus, and cannot be diffed or reviewed.

#### 6.3.2 Queue composition — four item types, one queue

| Item type | Source | Instrument | Ratio |
| --- | --- | --- | --- |
| **Published visual** | Shipped output | Q1–Q5 | The bulk |
| **Rejected plan** | Failed validation, rendered into `review/` only, never published | Q1–Q5, flagged as unpublished | D12 — sized to anchor the low end of each component |
| **Config-B variant** | A second plan under a different `weights.json` / prompt version | Pairwise | D9, in `pairwise` mode |
| **`none` decision** | The planner declined | The §4.2 question in §5 | `none_arm_ratio` |

Every item carries its type. **Aggregation that ignores item type is a defect** — a rejected plan's keep-rate is not a published visual's keep-rate.

#### 6.3.3 How labels reach the model without breaking statelessness

**Nothing is learned at inference time.** The whole loop is offline and lands as static config baked into the build:

```text
Feedback Ledger  (labels/*.jsonl — append-only, in version control)
        │
        ├─ fit_weights.py      →  weights.json     (weight_version)
        ├─ fit_priors.py       →  priors.json      (purpose → type)
        └─ select_exemplars.py →  exemplars.json   (few-shot / fine-tune set)
                                        │
                          baked into the build — the runtime only READS
```

The runtime never writes. Statelessness holds because **all state lives in the repository between builds**, which is also what makes every model-affecting change reviewable as a diff.

#### 6.3.4 This is not A/B testing — name it correctly

A/B testing requires assignment of readers to variants, tracking which variant each reader saw, and an outcome measured on that reader. **A static site with no server can do none of them.** Calling this loop "A/B testing" sets an expectation the architecture cannot meet, and the numbers will eventually be quoted as if readers produced them.

What is actually run is **offline paired evaluation**:

| | A/B test | Offline paired evaluation |
| --- | --- | --- |
| Who judges | Real readers, unaware | Recruited reviewers, aware |
| Assignment | Random per reader, server-side | Both variants to the same reviewer |
| Outcome | Behaviour — dwell, scroll, return | Stated preference |
| Needs a server | Yes | **No** |
| Proves | Which variant readers respond to | Which variant informed judges prefer |

The substitution is legitimate and standard. Its limitation is permanent and must be restated wherever the numbers appear: **reviewers are not readers.** They read more carefully, they know they are evaluating, and they may prefer visuals a reader would scroll past. This gap cannot be closed without a server; it can only be disclosed.

#### 6.3.5 Running a paired evaluation

| Step | Mechanism |
| --- | --- |
| Generate | The build produces variant A (published) and variant B (config-B plan). **B is written only into `review/`, never into the published article** |
| Blind | The page shows both in a seeded random left/right order, unlabelled. The variant→side mapping goes to a separate file the page never loads |
| Judge | The reviewer picks a side, or "no preference" |
| Unblind | Ingestion joins the choice to the mapping. **The reviewer never learns which config won**, so they cannot learn one config's house style and vote for it thereafter |
| Discard | A pair whose two sides came from the same config version is discarded at ingestion, not fitted on |
| Stop | Sample size is fixed **before** the run and recorded on the queue. No inspecting results mid-run and stopping when they look good — with a small corpus, that is how noise becomes a finding |

#### 6.3.6 Review mode flag

```text
REVIEW_MODE = absolute | pairwise | comprehension
```

| Mode | Instrument | Use |
| --- | --- | --- |
| `absolute` | Q1–Q5 against a single item | Interpretable, cheap, works with one reviewer. The correct **bootstrap** instrument |
| `pairwise` | Two candidates, pick one | Required by weight-learning; far more stable across reviewers |
| `comprehension` | Timed A/B with a comprehension question | The objective compression measure — §5.4.3 |

All three write the same ledger schema with an explicit `mode` field, so regimes can never silently blend in aggregation. **Treat any aggregation that omits `mode` as a defect.**

#### 6.3.7 The `none` control arm

```text
review.none_arm_ratio = 0.0 … 1.0        # config, versioned with the queue
```

| Setting | Behaviour |
| --- | --- |
| `0.0` | No control arm. `missed_visual_rate` is unmeasurable |
| `~0.05` | Collapse detector — enough to notice the planner stopping, not enough for a precise rate |
| `1.0` | Every `none` reviewed; `missed_visual_rate` exact; reviewer effort roughly doubles |

**This knob is zero-sum, not free.** Reviewer capacity is fixed: cranking toward 1.0 starves the visual-quality sample while sharpening the missed-visual rate. Set it from a **reviewer-hours budget**, not from preference (R16). The ratio is recorded on the queue so any published `missed_visual_rate` states the sampling density it was computed at.

#### 6.3.8 Reviewer identity, agreement and fatigue

Every label carries:

| Field | Purpose |
| --- | --- |
| `reviewer_id` | A repository-local alias, **never a personal name** |
| `queue_seed`, `mode`, `item_type` | Joinability and correct aggregation |
| `queue_position` | Position in the reviewer's session — makes fatigue and order effects **testable** rather than assumed away (R13) |

Overlap is manufactured by issuing the same `visual_id` to two reviewers across a defined fraction of the queue. Inter-reviewer agreement is computed from that overlap and displayed in Console beside the keep-rate. **A keep-rate published without an agreement figure beside it is not quotable.**

#### 6.3.9 Stratify by article, not by planner output

Stratifying the sample by `planned_type` confounds the type with the article, because the planner chooses the type: rare types occur only on unusual articles, so `bubble` keep-rate would measure unusual articles rather than bubbles. **Stratify by potential class**, and report keep-rate conditioned on both (R19).

#### 6.3.10 If reader signal is ever genuinely needed

All three options carry a cost the project has so far refused. Recorded so the decision is explicit rather than drifting:

| Option | Cost |
| --- | --- |
| Prefilled issue link — "was this useful?" opens a GitHub issue | Requires a reader with an account and the motivation to file: a severely self-selected sample. Cheap, and honest if reported as anecdote |
| Third-party analytics beacon | Splits the audit trail from the corpus, adds a runtime dependency and a privacy surface. Previously rejected |
| Any server | Ends the serverless property outright |

---

### 6.4 Versioning and migration

Replacing the routing contract is a **breaking change to an already-published corpus**. Without versions, no metric can be compared across the cutover and the historical baseline is destroyed.

#### 6.4.1 What carries a version

| Artefact | Version field | Changing it means |
| --- | --- | --- |
| Visual Plan contract | `plan_version` | Old plans may not deserialise |
| Component functions | `components_version` | Historical component values are incomparable |
| Learned weights | `weight_version` | Historical composite scores are incomparable |
| Alias ledger | `ledger_version` | Historical coherence scores are incomparable (R6) |
| Potential classifier | `potential_classifier_version` | **Every rate in the system re-baselines** |
| Compiler templates | `compiler_wave` | Rendered output changes |
| Renderer | `renderer_version` | Pixels change; archives stop reproducing (R17) |

**Never change `components_version` and `weight_version` in the same release.** You lose attribution and the entire score time series with it.

#### 6.4.2 Migration path

1. **Freeze a baseline.** Run the current pipeline over a fixed article set and store its outputs and metrics. This is the only "before" you will ever get.
2. **Dual-run.** Old and new pipelines over the same set; compare per potential class, not in aggregate.
3. **Cut over behind a flag**, with the old path retained for one release.
4. **Re-render the published corpus** under the new compiler in one intentional pass, recording the new versions on every visual.
5. **Mark the discontinuity** in every metric series. A chart of keep-rate spanning the cutover without a marked break is misleading, however tempting the line looks.

#### 6.4.3 Blast-radius query

Every published visual stores its full input tuple. When a defect ships, the affected set must be **queryable** — "every visual rendered by `compiler_wave` 2 using `pie`" — not reconstructed by hand. Without it, L15's promised re-render path has no way to know what to re-render (R12).


---

## 7. Decisions and risks


---

### 7.1 Risk register — second-order effects

Failure modes **not** prevented by anything in this document, ordered by how quietly they fail. A loud failure is a bug; a quiet one becomes the baseline.

| # | Risk | Mechanism | Why it is invisible | Mitigation | Severity |
| --- | --- | --- | --- | --- | --- |
| **R1** | **Planner–validator capitulation** | The planner is tuned from exemplars of what passed, so over time it proposes only what it knows will pass and stops attempting harder forms | `visual_rejection_rate` → 0, which reads as success. It is the planner giving up | Track **`planned_type_entropy` beside rejection rate**. Both falling = capitulation. Alarm on the *pair*, never on rejection alone | High |
| **R2** | **Extraction unmeasured** | Every downstream decision draws from the element table. Poor recall cripples the planner | Every visual metric is depressed and all of them blame the planner | **Addressed** — D13, extraction metrics and the three validation tiers | **Was highest** |
| **R3** | **Weights fitted on a censored sample** | Fitting on labelled *published* visuals means fitting on survivors of validation | Selection on the dependent variable. The fit never sees the component range of rejected plans, so weights are wrong exactly at the decision boundary | **Addressed** — D12, rejected plans rendered into `review/` and labelled | High |
| **R4** | **Over-merging in canonicalisation** | Too-aggressive collapsing makes `revenue` / `gross revenue` / `net revenue` one measure | Visuals mix incomparable quantities **while scoring perfectly on coherence**. Fragmentation is loud; over-merging is silent | Conservative and reviewable canonicalisation; log every merge; report `merge_rate`; prefer rejection over merge when uncertain | High |
| **R5** | **Span drift under normalisation** | Spans index *some* rendering of the article. If upstream cleaning changes, every span shifts | Validation still passes — a span is two integers | **Addressed** — `source_text_hash` + `span_excerpt` + a build-failing invariant | High |
| **R6** | **Alias ledger breaks comparability** | Adding an alias in month 3 changes what month 1 would have scored | Metrics silently stop being comparable across ledger versions | `ledger_version` stamped on every score; never compare across versions without re-scoring | Medium |
| **R7** | **Faithful but vacuous summaries** | Under D1 one model writes summary then plan. If terser summaries raise `information_delta`, stripping numbers from prose is a structural incentive | `summary_faithfulness` **passes** — a summary with fewer claims is *more* faithful | `summary_informativeness` — fact coverage of the summary against the element table. Faithfulness alone cannot detect this | High |
| **R8** | **Downgrade floors self-loosen** | Floors from a rolling corpus that contains downgrades, which score lower and pull the median down | The bar loosens exactly as quality falls, and the mechanism looks like it is working | **Addressed** — floors computed from depth-0 published visuals only | Medium |
| **R9** | **Retries are not independent** | A retry against identical context reproduces the identical failure | `schema_retry_count` goes bimodal and the retries buy only latency | **Addressed** — every retry must perturb the rejection reason or the temperature | Medium |
| **R10** | **Diagram edges are Tier 2, not Tier 1** | Deciding whether "subsequently", "after which" or paragraph order *asserts* a relation is judgement | The diagram integrity argument rests on edges being verifiable. They are model judgement wearing a span | **Addressed by disclosure** — edges reclassified as Tier 2 with a span; publish the decision procedure; sample edges for human audit | High |
| **R11** | **Alt text is an unguarded prose channel** | Accessibility is assigned to code, but alt text is prose about numbers | A caption by another name — the easiest place for an unmatched number to re-enter | **Addressed** — alt text inside D7 and generated deterministically by the compiler | Medium |
| **R12** | **No blast-radius query after a defect** | Nothing owns *detection* of which published visuals a compiler bug touched | A defect ships and the affected set is unknowable, so nothing is re-rendered | **Addressed** — full input tuple stored per published visual | Medium |
| **R13** | **Reviewer fatigue and order effects** | Item 38 of 40 is judged differently from item 2 | Indistinguishable from a real quality change | **Addressed** — `queue_position` on every label | Low |
| **R14** | **Reviewer anchoring on `why`** | A reviewer shown the model's rationale judges the argument, not the visual | Labels look normal and are contaminated | **Addressed** — `why` never shown to reviewers | Medium |
| **R15** | **Evaluation cost outside the budget** | D9 needs a second plan per sampled article; D12 needs rejected renders; the `none` arm adds review load | `cost_per_published_visual` counts publication only | **Addressed** — `evaluation_cost` reported separately and included in any total-cost claim | Medium |
| **R16** | **`none_arm_ratio` is zero-sum** | Presented as freely crankable, but reviewer capacity is fixed | Cranking toward 1.0 starves the quality sample while sharpening the missed rate | **Addressed** — set from a reviewer-hours budget, and the ratio recorded on the queue | Medium |
| **R17** | **Renderer drift breaks archives** | Minor version bumps change pixel output | Archived artifacts stop reproducing; diffs fill with noise until nobody trusts them | **Addressed** — pin versions, record `renderer_version`, treat a bump as a corpus event | Medium |
| **R18** | **Cross-article repetition** | A running story yields the same visual daily | Every per-article metric is perfect. The reader sees the same visual five days running | Fingerprint the (element set, type) pair across a rolling window; report `visual_repetition_rate` | Medium |
| **R19** | **Stratifying on planner output** | Type is chosen by the planner, so rare types occur only on unusual articles | `bubble` keep-rate measures unusual articles, not bubbles | **Addressed** — stratify by potential class; report conditioned on both | Medium |
| **R20** | **No home for a single striking number** | A lone dramatic figure is a very common news shape | Falls to `none`, or to a one-bar chart the minimum-point rule rejects. Invisible except as unexplained `missed_visual_rate` | **Partly addressed** — the `callout` type exists; its gating is open at L28 | Medium |

#### 7.1.1 The pattern behind these

Sixteen of the twenty fail **silently**, and most fail in the direction that makes a metric look *better*. That is not coincidence: **this architecture measures itself, and every self-measuring system drifts toward whatever it can measure.**

Two structural defences:

1. **Never alarm on a single metric that can be improved by giving up.** Always pair it with a diversity or coverage counter — rejection rate with planned-type entropy, keep-rate with missed-visual rate, coherence with merge rate.
2. **Keep the human loop pointed at the output, not at the metrics.** The moment reviewers see scores, they calibrate to them and the ground truth is gone.

---

### 7.2 Litigation table

**You are expected to disagree.** Every row is provisional. Argue it on evidence, record a verdict, and add rows for anything this document got wrong. Silent adoption of the recommendation column is a failed review.

| # | Decision | Options | Recommendation | Confidence | Strongest counter-argument |
| --- | --- | --- | --- | --- | --- |
| **L1** | Inference topology | (a) one call, joint JSON (b) two calls, one model (c) both behind a flag | **(b)** — D1 | Medium | Two calls roughly double model-stage latency and token cost. If p95 latency binds at corpus scale, (a) wins and failure coupling is handled by a repair pass instead. L27 makes this measurable |
| **L2** | Vocabulary size in v1 | (a) 5 types (b) all types fully implemented (c) all declared, compiler in waves with deterministic downgrade | **(c)** — D2 | Medium | A downgrade path launders planner errors as successes. If `slope` silently becomes `bar`, type distribution measures the downgrade table. Mitigated only by reporting `planned_type` and `rendered_type` separately |
| **L3** | Include `pie` | (a) exclude (b) include, gated (c) include, ungated | **(b)** | Low–Medium | Cleveland & McGill place angle below position and length in accuracy, and every gate is another rule the planner can trip. Counter-counter: exclusion is also an untested prior; gating makes it empirical |
| **L4** | Element label vocabulary | (a) closed enum (b) open, model-assigned, span-anchored | **(b)** — D3 | Medium | Open vocabulary makes coherence a string-comparison problem and it fails **silently**. The canonicalisation pass and alias ledger are not optional extras — without them D3 disables a quality component |
| **L5** | Metric weights | (a) invented vector (b) equal until fitted, then learned | **(b)** — D5 | High | Equal weights will under-perform a well-chosen prior in the first weeks. Accepted: the cost is temporary, the credibility gain permanent |
| **L6** | Trust model | (a) one class (b) two tiers | **(b)** | High | Two tiers add bookkeeping to every element. Accepted — calling model-assigned labels "deterministic" is false and would eventually be discovered |
| **L7** | Behaviour on validation failure | (a) no visual (b) downgrade ladder with escalating bar, flagged (c) one repair retry | **(b)** — D6 | Medium | The escalating floors, element-set invariance and the annotation requirement are three new rules the planner can trip, each costing publish rate. If keep-rate at depth ≥ 1 does not hold up, `VISUAL_DOWNGRADE=off` is correct and the ladder should be **deleted, not tuned** |
| **L8** | Numerals in prose | (a) free prose (b) every numeral matches a Tier 1 element, with an allow-list | **(b)** — D7 | High | The allow-list is itself an attack surface: "the 1990s" passes, so a fabricated decade passes. Keep it minimal, versioned, and report `allowlist_hits` so growth is visible |
| **L9** | Diagram family in v1 | (a) ship (b) defer, drop the enum value (c) defer, keep the value | **(a)** — D11 | Medium | The most expensive decision here: a second extractor, validator, compiler and renderer dependency for a family sharing nothing with charts. Counter-counter: a process diagram is often the only good visual for a non-numeric story, and deferring caps the system's ceiling |
| **L10** | Integrity invariant vs KPI | (a) `trusted_data_ratio` as a dashboard KPI (b) a build-failing invariant on value provenance, with coverage reported separately | **(b)** | High | **Corrected from an earlier draft**, which declared the ratio structurally 1.0 forever — derived values break that. The invariant is "every displayed value resolves to a Tier 1 element or a complete derived chain"; coverage is a report expected below 1.0 |
| **L11** | Type entropy | (a) set a diversity target (b) observe only, read jointly with appropriateness | **(b)** | High | Making entropy a target invites diversification into wrong types. Uniform is the wrong ideal: most news quantities genuinely are category comparisons, so a large `bar` share may be correct |
| **L12** | False negatives | (a) ignore (b) full control arm (c) thin sample | **(b) and (c) unified** — D10, one ratio knob | Medium | A ratio makes the metric's precision a moving target; any published `missed_visual_rate` is meaningless without the ratio it was sampled at, which is why the ratio is recorded on the queue |
| **L13** | Human loop design | (a) one reviewer, absolute (b) pairwise, stratified, ≥ 2 on overlap (c) both behind `REVIEW_MODE` | **(c)** — D8 | Medium | Two instruments means two schemas and a discontinuity at the switch. The `mode` field is the only thing preventing a silent blend — treat any aggregation omitting it as a defect |
| **L14** | Cost and latency | (a) unbudgeted (b) explicit p95 budget plus the cost family | **(b)** | High | One model doing seven jobs under constrained decoding on a wide schema has a real tail. D1 makes it two calls, which makes the budget mandatory rather than optional |
| **L15** | Versioning and migration | (a) none (b) versions on every artefact plus a documented re-render path | **(b)** | High | Replacing the routing contract breaks an already-published corpus. Without versions, no metric survives the cutover |
| **L16** | Source of the paired second item | (a) A/B across config versions (b) depth-0 vs downgraded (c) visual vs no-visual | **(a)** — D9 | Low | (a) only compares two options the system already believes are reasonable, so it can sit in a local maximum indefinitely. Periodically injecting (c) as a separate arm is the cheapest guard |
| **L17** | Console alarm thresholds | (a) set now from judgement (b) unset, derived from observed percentiles after one corpus month | **(b)** | High | An unset alarm catches nothing for a month. Accepted — a wrong alarm trains people to ignore alarms, which is worse and harder to undo |
| **L18** | Diagram renderer | (a) Mermaid CLI (b) Mermaid client-side (c) Graphviz `dot` (d) hand-rolled (e) frontend-owned | **OPEN — explicitly not decided.** Owner withheld pending repository context | — | Must be scored against the fidelity / compression / colour / interactivity requirements, not build simplicity. An earlier recommendation of (c) is **withdrawn**: it optimises build hygiene and scores badly on interactivity and colour control |
| **L19** | Diagram integrity model | (a) reuse chart rules (b) parallel Trusted Node / Edge structure with span-anchored edges | **(b)** | High | (b) is a second extractor and will reject many diagrams a reader would have accepted, because articles frequently imply ordering without asserting it. Accepted anyway: an unanchored edge is an invented causal claim, the easiest way to reintroduce fabrication into a system built to prevent it |
| **L20** | Diagram node cap | (a) fixed limit now (b) config bound from observed distribution | **(b)** | Medium | Leaves the cap effectively unbounded for a month, risking one enormous unreadable diagram. Mitigate with a generous **explicitly provisional** ceiling, not a confident-looking number |
| **L21** | Where rendering happens | (a) build-time static only (b) client-side from the spec (c) progressive enhancement | **OPEN**, though (c) is the only option satisfying every stated requirement at once | — | (c) means two rendering paths kept visually identical — a real recurring cost. (a) cannot deliver interactivity; (b) forfeits the archivable artifact and the no-JS reader. Note interactivity is cheap on the chart path (Vega-Lite has an interaction grammar) and expensive on the diagram path (no equivalent) |
| **L22** | `histogram` and derived values | (a) drop `histogram` (b) Derived Value mechanism with a closed allow-list | **(b)** | Medium | (b) opens the first legitimate route for a displayed number not in the article. The allow-list and the separate `derived_value_rate` are the only things keeping it narrow — skip either and the guarantee is gone unnoticed |
| **L23** | `confidence` field | (a) drop (b) record, never gate (c) use as a publish gate | **(b)** | High | Self-reported LLM confidence is poorly calibrated; gating would silently suppress good visuals. Recording costs nothing and makes calibration empirical — but delete the field if it proves uncorrelated, rather than keeping a decorative one |
| **L24** | Amending the principle | (a) keep "once" and revert L1 (b) amend to "all semantic analysis" (c) leave the contradiction | **(b)** — D15 | High | (b) can read as moving the goalposts. Counter: the word was written to exclude a second *model*, and it still does. Leaving (c) is far worse — a headline claim contradicted by the decision log discredits the rest |
| **L25** | `summary_faithfulness` in the visual KPI set | (a) out of scope (b) in, as a regression guard | **(b)** | High | It is genuinely a summary metric, and putting it here risks two owners for one number. Counter: this architecture's most likely unnoticed harm is degrading the summary in pursuit of a visual, and nothing else would detect it. Wire in the existing scorer; do not build a second |
| **L26** | Naming the reviewer loop | (a) call it A/B testing (b) call it offline paired evaluation and disclose the reviewer≠reader gap | **(b)** | High | (b) is less persuasive in a status update. That is precisely the problem with (a) |
| **L27** | Prefill amortisation | (a) two independent calls (b) two calls with KV cache reuse (c) revert to one call | **(b)**, with (c) triggered if measurement shows no reuse | High | An implementation constraint no spec can verify — it must be measured. The call-1/call-2 `prefill_ms` ratio is the deciding number |
| **L28** | Gating the `callout` type | (a) leave the gap (b) `purpose: magnitude` + `callout` in the infographic family (c) `magnitude` as a one-row `table` | **(b) proposed — ASSIGNED TO EDITOR AGENT.** The infographic family is admitted on independent grounds, so `callout` costs no new boundary argument | — | (b) concedes a typeset number is a "visual", weakening the prose/visual line drawn elsewhere, and it is the type most likely to be over-used — almost every article has one number worth enlarging. **Editor agent must decide:** whether `callout` requires a superlative or record-setting qualifier in the article ("largest ever", "first since") rather than merely being the biggest number present. Without that gate, expect `callout` to dominate the infographic distribution within weeks |
| **L29** | Scope of the measured pipeline | (a) planner onward (b) extend upstream to extraction | **(b)** — D13 | High | (b) requires a manually-labelled ground-truth set: real recurring cost on a stage nobody complained about. Counter: every visual metric is conditioned on extraction quality, and no planner regression is attributable while the input distribution is unmeasured |
| **L30** | Labelling rejected plans | (a) published only (b) also render rejects into `review/` and label them | **(b)** — D12 | High | (b) adds render cost and reviewer load for visuals that will never ship, and judging a deliberately-broken visual is confusing. Counter: fitting on survivors is selection on the dependent variable |
| **L31** | Trusted Fact → Trusted Element | (a) keep numeric-only (b) generalise to `kind`-discriminated elements | **(b)** — D14 | Medium | (b) widens the extractor from one job to six, each a new failure surface. Counter: a numeric-only trust model structurally excludes most of a news corpus from ever receiving a visual, contradicting the stated goal |
| **L32** | The `claim` element | (a) allow model-authored claim text (b) verbatim spans only, deterministic truncation | **(b)** | **High** | (b) produces awkward card text — real sentences are rarely card-shaped, and the pressure to "let it rewrite slightly" will be constant. **That pressure is the risk.** A paraphrased claim reads as sourced, renders as authoritative, and is nowhere in the article. The easiest way to reintroduce fabrication after every other route is closed |
| **L33** | `keyfacts` type | (a) ship (b) ship with an explicit kill criterion (c) omit | **(b)** | Medium | Predicted: high decision rate, poor keep rate — easiest for a model to justify, least informative for a reader. Ship it, but pre-commit to dropping it if the prediction holds rather than defending it afterwards |
| **L34** | Comprehension timing instrument | (a) stated preference only (b) add the timed A/B arm | **(b)** | Medium | Timing unsupervised reviewers is noisy — interruptions dominate, small *n* makes medians unstable. Counter: it is the only measurement about *comprehension cost* rather than *opinion*, at a marginal cost of one page in `review/` |
| **L35** | Article Visual Potential | (a) rates over all articles (b) every rate per potential class | **(b)** | **High** | (b) fragments every metric into thinner series, and the classifier's thresholds become a tuning surface needing an owner. Counter: without it, a 4% chart rate on narrative articles and 4% on chartable articles are indistinguishable — a confound that probably invalidates more of the KPI set than any other single issue here |

#### 7.2.1 Verdict template

```text
row:        L<n>
verdict:    accept | reject | amend
rationale:  <evidence, not preference>
evidence:   <file path, measurement, or citation>
new_rows:   <anything this document failed to consider>
```

---

### 7.3 Open questions

Unresolved and to be answered during implementation. Recorded so no decision is made silently.

| # | Question | Why it matters |
| --- | --- | --- |
| 1 | Who owns the potential-classifier thresholds, and where are they versioned? | A threshold change silently re-baselines every rate in the system |
| 2 | What is the minimum element count per type, and does `table` bypass it? | Encodes the "enough data" validator rule |
| 3 | How is `information_delta` computed against the summary — string matching, element-id overlap, or relationship extraction from the summary text? | The metric is otherwise unimplementable, and relationship extraction from prose is as hard as the original problem |
| 4 | Are `time` and `entity` free strings or normalised types? | Charting `"2025"`, `"FY25"` and `"last year"` on one axis needs normalisation |
| 5 | Sampling rate, reviewer count, and inter-rater agreement target for the Human Loop? | A keep-rate from one reviewer on five visuals is noise |
| 6 | What decision procedure determines whether a span *asserts* a diagram edge? | R10 — currently undefined, and it is the load-bearing rule of the diagram family |
| 7 | Does the existing canary mechanism support element-table fixtures, or does it need extending? | Determines whether extraction tier-1 validation is free or a build |
| 8 | Is there an existing faithfulness scorer to wire in, and what does it score against? | L25 says reuse, not rebuild — but only if it exists |
| 9 | What is the retention policy for the Feedback Ledger and rejected-plan renders? | An append-only ledger with no policy grows without bound |
| 10 | Who reviews additions to the alias ledger, and how often? | Unreviewed merges are the silent-failure path in R4 |

---

### 7.4 References

External published work cited for the metric anchors. None has been verified against the repository.

| Work | Reference |
| --- | --- |
| Cleveland, W. S. & McGill, R. — *Graphical Perception: Theory, Experimentation, and Application to the Development of Graphical Methods* | *Journal of the American Statistical Association*, 79(387), 531–554, 1984. DOI 10.1080/01621459.1984.10478080 |
| Saket, B., Endert, A. & Demiralp, Ç. — *Task-Based Effectiveness of Basic Visualizations* | IEEE TVCG; preprint arXiv:1709.08546 |
| Moritz, D., Wang, C., Nelson, G., Lin, H., Smith, A. M., Howe, B. & Heer, J. — *Formalizing Visualization Design Knowledge as Constraints: Actionable and Extensible Models in Draco* | IEEE Trans. Visualization & Comp. Graphics (Proc. InfoVis), 2019 — Best Paper. Software: `github.com/uwdata/draco` |
| Tufte, E. R. — data-ink ratio | *The Visual Display of Quantitative Information* |
