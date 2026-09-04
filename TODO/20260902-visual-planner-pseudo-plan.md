# Visual Planner - Pseudo-Plan and Decision Record

**Last Updated**: 2026-09-04
**Status**: PSEUDO-PLAN. Not execution-ready. Not a plan-doc under `docs/how-to/author-a-plan.md`.
**Level**: 5 (core design, four persisted contracts, the model pick, the trust boundary)
**Companion**: [`20260902-yen-idhazh-visual-planning-architecture.md`](20260902-yen-idhazh-visual-planning-architecture.md) - "the proposal" throughout. Section references like `P.3.4.3` mean that document's section 3.4.3; `P.L28` means its litigation row L28; `P.D1` a decision; `P.R7` a risk.

## 0. What this document is, and how to validate it

This is the single carrier of a long design conversation held on 2026-09-02, written so the context survives a session boundary. It holds every decision, every persona ruling, every correction to the proposal's own unverified claims, and a coverage matrix that maps **every** numbered item in the proposal to a work item here.

**Nothing in the proposal is descoped.** An earlier draft of this record used "v1" to defer six areas. The owner rejected that outright. Section 5 lists every one of those deferrals and reverses it.

To validate this document, check three things:

1. **Section 12** claims full coverage of the proposal. Verify every `P.D*`, `P.L*`, `P.R*`, `P.Q*` and every section of the proposal appears there with a disposition.
2. **Section 2** claims the proposal's description of the current code is wrong in named places. Verify each row against the file and line cited.
3. **Section 4** claims seven persona advisors ruled. Verify each ruling names what the reader loses (`docs/agents/guardrails.md`).

---

## 1. The architectural change, in one paragraph

The visual stops being "a chart" and becomes **a visual that complements the article at high information compression**. Code reads the article first and finds deterministically every quantity it can, with the character offsets that prove where each one came from. Then one capable model reads the same article and does the work only a model can do: it labels those numbers, names the entities and places, points at the quotes and the claims, proposes any figure the regex missed, and decides what visual would genuinely help. Code then anchors everything the model pointed at back into the article's own bytes, drops whatever will not anchor, checks the choice and renders it. **The model finds the meaning; code cuts the characters.**

> The model decides what the visual **means**. Code decides what the visual **contains** and how it is **rendered**.

That slogan is the readable version. The **defensible** version is the one the proposal narrows it to in P.1.5.2, and it is the one that binds:

> Deterministic code controls every displayed value and every displayed string. Model judgement is confined to selection and labelling, and is span-anchored throughout.

Section 10.1a reaches the same rule from the other direction - code finds and cuts every character a reader will see. The split is not clean by stage; it is decided kind by kind. Section 10.1a rules it, section 10.1b draws it.

---

## 1a. The flow, end to end

The proposal's section 1.2 draws the target architecture. This is the same flow **with every ruling in this document folded in** - the reachability gate, the retired second model, the sufficiency oracle, the per-attempt ledger, the re-validating ladder, and the console panels. Where the two disagree, this drawing wins, because the proposal predates the rulings in section 3 and section 4.

Plain ASCII, not box-drawing characters: `CLAUDE.md` section 5 is ASCII-only for every file in this repository and a diagram is not an exception.

```
   +======================================================================+
   |  STAGE 1 - EXTRACT                     zoomed in at section 10.1b    |
   +======================================================================+

                            +---------------------+
                            |       ARTICLE       |
                            +----------+----------+
                                       |
              candidate pass (code)  ->  call 1 (model)  ->  anchoring (code)
              finds numbers              labels, names,      one rule per shape,
              mints element_id           points at spans     drops what will not
                                                             anchor
                                       |
                                       v
                        +-------------------------------+
                        |       TRUSTED ELEMENTS        |
                        |  TIER 1  byte-exact, never    |
                        |          model-authored       |
                        |  TIER 2  model-assigned,      |
                        |          span-anchored        |
                        +---+-----------------------+---+
                            |                       |
                            |                       v
                            |        +---------------------------+
                            |        |     ARTICLE POTENTIAL     |
                            |        |      (deterministic)      |
                            |        |  chartable     singular   |
                            |        |  processual    narrative  |
                            |        |  comparative              |
                            |        +-------------+-------------+
                            |                      |
                            |          the denominator for EVERY
                            |          rate in stage 4. Without it,
                            |          4 percent on narrative and
                            |          4 percent on chartable are
                            |          the same number.      (row 56)
                            v
   +======================================================================+
   |  STAGE 2 - DECIDE                                                    |
   +======================================================================+

              +---------------------------+
              |     REACHABILITY GATE     |     no
              |     code, no model        |----------> plan fields suppressed
              |  Could ANY plan over      |            inside call 2, which
              |  these elements survive   |            STILL RUNS and still
              |  validation at all?       |            writes the summary.
              |                           |            It emits decision =
              |  It suppresses the plan.  |            none, none_reason =
              |  It NEVER skips a call.   |            not_reachable.
              +-------------+-------------+
                            | either way, every item
                            v
              +---------------------------+
              |      SEMANTIC MODEL       |
              |  ONE model. The 4B router |
              |  is retired outright.     |
              |  call 2, appended to      |
              |  call 1's message array,  |
              |  so the article prefills  |
              |  once.          (O17, 10.2)
              +---------------------------+
              | understand the story      |
              | summarise            ->  summary
              | identify key facts   ->  key_points
              | assess visual need   ->  decision
              | choose the form      ->  purpose + type
              | select elements      ->  element_ids
              | explain the choice   ->  why
              +-------------+-------------+
                            |
                 constrained semantic JSON
                            v
              +---------------------------+     decision = none
              |        VISUAL PLAN        |----------> none: model_declined
              | decision  purpose  type   |
              | encodings  element_ids    |
              | labels  annotations  why  |
              | title  caption            |
              | confidence  plan_version  |
              +---------------------------+
              | NO geometry               |
              | NO literal values         |
              | NO authored text          |
              | NO alt_text - the         |
              |   compiler writes it      |
              +-------------+-------------+
                            |
   +======================================================================+
   |  STAGE 3 - CHECK, DRAW, PUBLISH                                      |
   +======================================================================+
                            v
              +---------------------------+
              |     VISUAL VALIDATOR      |
              |      (deterministic)      |
              | elements exist            |
              | semantically compatible   |
              | units compatible          |
              | roles valid for the type  |
              | enough data               |
              | no duplicate in a role    |
              | no invented values        |
              | numerals matched          |
              +------+-------------+------+
                fail |             | pass
                     v             |
        +----------------------+   |
        |   DOWNGRADE LADDER   |   |
        |  depth 1  median     |   |
        |  depth 2  p75 + note |   |
        |  depth 3  refuse     |---+------> none: downgrade_exhausted
        +----------+-----------+   |
                   |               |
     a downgraded plan RE-ENTERS   |
     the same validator and the    |
     same compiler. It never goes  |
     around either.        (G8)    |
                   |               |
                   +------>>-------+
                                   v
              +---------------------------+
              |      VISUAL COMPILER      |
              |  one template per type,   |
              |  -> renderable spec       |
              |  planned_type AND         |
              |  rendered_type both kept  |
              +-------------+-------------+
                            v
              +---------------------------+
              |   RENDER - d3, one engine |
              |  INLINE SVG in the item.  |
              |  No img carrier - an SVG  |
              |  inside img cannot read   |
              |  the page's tokens, and   |
              |  that is the whole of the |
              |  dark-theme defect (row 21)
              +-------------+-------------+
                            v
              +---------------------------+     fail
              |     SUFFICIENCY BAR       |----------> none: insufficient
              |  a COMPILER ORACLE, not   |
              |  a review item     (O36)  |
              | legibility floor, 12 px   |
              | density floor             |
              | both themes resolve       |
              | one annotated mark        |
              | keyboard route to a fact  |
              | per-visual byte cap       |
              +-------------+-------------+
                            | pass
                            v
              +---------------------------+
              |     PUBLISHED VISUAL      |
              |  below the summary (O35)  |
              +-------------+-------------+
                            |
   +======================================================================+
   |  EVERY path above - published, downgraded, refused, none - writes    |
   |  ONE ROW to state/visuals/, one row per ATTEMPT.                     |
   |                                                                      |
   |    decision      published | downgraded | none | rejected            |
   |    none_reason   which gate refused it, or that call 2 was cut short |
   |    rejection_reason, rejection_stage, downgrade_depth,               |
   |    downgrade_reason, downgrade_edge, gate_floor_applied,             |
   |    planned_type, rendered_type, compile_ms, render_ms                |
   |                                                                      |
   |  There is no silent path to `none`.       (row 55, 12.7 G7, G11, E5) |
   +===================================+==================================+
                                       |
   +======================================================================+
   |  STAGE 4 - THE TWO LOOPS                                             |
   +======================================================================+
                                       |
             +-------------------------+-------------------------+
             |                                                   |
             v                                                   v
   +----------------------------+              +----------------------------+
   |       MACHINE LOOP         |              |        HUMAN LOOP          |
   |  every article, automatic  |              |  periodic, sampled, costly |
   |  free                      |              |                            |
   |  ** GATES PUBLICATION **   |              |  ** GATES NOTHING **       |
   +----------------------------+   sampled    +----------------------------+
   | plan -> validation ->      |   queue      | published + rejected +     |
   | metrics -> diagnostics     |------------->| config-B + `none` arm,     |
   +-------------+--------------+              | all four populations       |
                 |                             +-------------+--------------+
                 v                                           v
   +----------------------------+              +----------------------------+
   |          CONSOLE           |              |  review/                   |
   |  rejection reason over time|              |  a BUILD ARTIFACT.         |
   |  keep rate by downgrade    |              |  Never committed, never    |
   |    depth                   |              |  under frontend/public/    |
   |  planned_type against      |              +-------------+--------------+
   |    rendered_type           |                            v
   |  plus every existing eval  |              +----------------------------+
   |  metric, incl. band_reason |              |  quality baseline ->       |
   |                     (O11,  |              |  LEARNED WEIGHTS           |
   |                      O34)  |              |                            |
   +----------------------------+              |  A DIAGNOSTIC. Never a     |
                                               |  gate - not until          |
                                               |  information_delta is      |
                                               |  measured against          |
                                               |  visual_keep_rate.   (G9)  |
                                               +----------------------------+
```

**The four things this drawing asserts that the proposal's does not.**

| | Where it is ruled |
|---|---|
| A **reachability gate** runs before the model does any plan work, so an article that cannot be visualised costs no plan tokens. **It suppresses the plan fields inside call 2 and never skips the call**, because call 2 writes the summary (O43) | Section 14.5 gate 1, O43 |
| The ladder **re-enters** the validator and the compiler rather than routing around them | Section 12.7 G8, row 50 |
| The **sufficiency bar is a compiler oracle**, so a visual can fail for being too little, not only for being wrong | O36, Susan's mandate in `CLAUDE.md` section 14 |
| Every attempt writes a row, so a refusal is **legible rather than an absence** | Row 55, section 12.7 G7 |

---


Two consequences drive everything below. The weak router model is retired and the strong model does the semantic work. And `route.py` is replaced by `visual_planner.py`, because "route" names a dispatch decision and the thing being built is a planning decision.

---

## 2. Corrections to the proposal's account of the current code

The proposal states in its own provenance warning that every claim it makes about the existing implementation is second-hand. It is wrong or misleading in the following places. Each row below was read directly.

| # | Proposal says | Truth | Evidence |
|---|---|---|---|
| C1 | `RouteDraft` is the routing contract | `RouteDraft` and `ChartPoint` live in `route.py`, **not** in `contracts/`, so they are unversioned and free to rename. The persisted contract is `Route` in `contracts/route.py` | [backend/idhazh/route.py](backend/idhazh/route.py#L190) |
| C2 | Elements are span-anchored | **No span exists.** `NumericFact` is `value, raw, unit, context`. The regex already computes `match.start()` and `match.end()` and discards them when it builds `context` | [backend/idhazh/route.py](backend/idhazh/route.py#L89) |
| C3 | The renderer is a hard-coded bar | True, and worse: `chart_spec()` hard-codes `"color": "#4c6ef5"` and `"labelFont": "sans-serif"`, which is a live Rule #6 violation | [backend/idhazh/route.py](backend/idhazh/route.py#L437) |
| C4 | The diagram path is unbuilt | It is built - `diagram_spec()` emits Mermaid and `render/diagram.py` draws it with a hand-written layout. It is switched **off** in `visuals.enabled_kinds` | [backend/idhazh/render/diagram.py](backend/idhazh/render/diagram.py) |
| C5 | Rendering happens in the frontend | Digest visuals render in the **backend** via `vl-convert` (Rust, no browser). ECharts renders **console** charts in the frontend build. Two separate paths | [backend/idhazh/render/chart.py](backend/idhazh/render/chart.py#L35) |
| C6 | Interactivity needs a new JS payload | The console already prerenders SVG then fetches a CSV at runtime and re-renders. The pattern exists and is tested | [frontend/src/routes/console/+page.svelte](frontend/src/routes/console/+page.svelte#L136) |
| C7 | Theming is an open question | The console solved it: draw with sentinel colours `#ff00NN`, swap for `var(--chart-N)` in the emitted SVG. Both themes resolve through CSS with no JavaScript | [frontend/src/lib/charts/theme.ts](frontend/src/lib/charts/theme.ts#L74) |
| C8 | Labels are gitignored | `state/labels.csv` is **not** gitignored. It is committed-eligible and has simply never been written | [backend/idhazh/evals/labels.py](backend/idhazh/evals/labels.py#L39) |
| C9 | Per-item timing is missing | It exists for summarize: `prefill_ms`, `decode_ms`, `input_tokens`, `output_tokens`, `cached_tokens`. What is missing is a **visual stage** - `ItemStage` is PLAN/FETCH/EXTRACT/SUMMARIZE/PUBLISH | [backend/idhazh/contracts/item_health.py](backend/idhazh/contracts/item_health.py#L32) |
| C10 | The site cap is a knob | `retention.site_budget_mb` 800 is the **alarm**. `PAGES_HARD_CAP_MB = 1024` is a `Final` in code, deliberately not editable | [backend/idhazh/retention.py](backend/idhazh/retention.py#L79) |
| C11 | Assemble de-duplicates the day | **It groups. It removes nothing.** The docstring says so outright: "Nothing is removed. Every item stays in the published order it was in" | [backend/idhazh/assemble.py](backend/idhazh/assemble.py#L383) |
| C12 | `carried_by` gives cross-source repetition before the model runs | Only for an **identical URL**. `merge()` groups by `url_key`, so two outlets writing the same story at two addresses are two items with `carried_by` 1 each - and both pay a full model call | [backend/idhazh/rank.py](backend/idhazh/rank.py#L441) |
| C13 | `ChartPoint {label, fact_index}` is replaced because "positional indexes break silently" | Half right, and the half it drops is the safety property. A list *position* is fragile and should become a stable `element_id` - which is what the proposal's own D14 rename asks for. What must not be dropped is that the field is a **reference, not a value**: `RouteDraft`'s docstring records what that buys - the contract carries "no free numeric field anywhere, so the worst an injection can do is pick the wrong bars" | [backend/idhazh/route.py](backend/idhazh/route.py#L187), [backend/idhazh/route.py](backend/idhazh/route.py#L193) |
| C14 | (implied by both documents) `numeric_facts()` is a sound candidate source for a chart | **It deletes exactly the series a chart exists to show.** It dedupes on `(value, unit)`, so twelve percent in one quarter and twelve percent in another collapse into one candidate. Its own docstring states the intent - "the same figure repeated in a lead and a body paragraph is one" - and the intent is right for a fact and wrong for a series. It also drops any magnitude at or below 2 with no unit, nulls a unit word on a stop-list, and stops at 16 facts | [backend/idhazh/route.py](backend/idhazh/route.py#L165), [backend/idhazh/route.py](backend/idhazh/route.py#L163), [backend/idhazh/route.py](backend/idhazh/route.py#L176) |
| C15 | Code can extract dates today | **No date extractor exists.** `numeric_facts()` finds quantities and actively drops a bare four-digit year in 1900-2100, because a year is a label and not a bar height. So the `date` kind is new work in plan-doc G, not a rename of something that ships | [backend/idhazh/route.py](backend/idhazh/route.py#L158) |

### 2.1 The root cause of the unreadable dark theme

This is the single most important finding of the review, and neither the proposal nor the owner's first diagnosis had it.

[frontend/src/lib/components/ItemVisual.svelte](frontend/src/lib/components/ItemVisual.svelte#L25) renders `<figure><img src="...svg"></figure>`. **An SVG inside an `img` element is a separate document and cannot read the host page's CSS custom properties.** Two defects compound:

- The hex is baked into the SVG by the backend, so CSS could not reach it even if the carrier allowed it.
- The carrier is an `img`, so swapping the chart engine changes nothing on its own. Sentinels would resolve to nothing and the chart would lose colour entirely.

**The fix is to inline the SVG into the item.** Every other rendering decision depends on this one.

### 2.2 The legibility failure, measured

Committed charts are 825 x 437 px inside an 890px card body ([frontend/src/lib/components/ItemVisual.svelte](frontend/src/lib/components/ItemVisual.svelte#L11), measured 2026-09-02). On a 390 CSS px phone the drawing scales to roughly 0.31x, so **10px axis labels draw at about 3.1 CSS px**. That is below `--text-xs` (12px) at every supported width. This is not a taste complaint; it is a chart whose labels nobody can read.

---

## 3. Owner decisions

Numbered for citation. Each names the proposal section it settles.

| # | Decision | Settles |
|---|---|---|
| O1 | The visual **complements** the article at high information compression. Not "a chart" | P.1.1, P.4.4.1 |
| O2 | New module `backend/idhazh/visual_planner.py`. **`route.py` is not edited.** Every producer and consumer moves. The word "route" is scrubbed from this domain - modules, classes, enums, config keys, CLI verbs, file suffixes, prompt filenames, workflow jobs | P.D-renames |
| O3 | One strong model, two calls, inside the existing sharded work job. The separate visual CI job is retired | P.D1, P.D15, P.L1 |
| O4 | Vega-Lite and `vl-convert` are dropped | P.4.4.3 |
| O5 | **d3 is the single rendering engine for digest visuals.** Not ECharts. See section 7 | P.L18, P.4.4.3 |
| O6 | Items per worker falls to 20 by setting `run.safety_ceiling_per_run` to **80**, leaving `max_parallel` at 4. See section 8.2 | P.L14 |
| O7 | `PAGES_HARD_CAP_MB` moves into `config/idhazh.json`, bounded `le=1024` so config can lower it and never raise it | P.6.2 |
| O8 | `retention.image_months` = 13 and `retention.dry_run` = false, **after** the new renderer lands | P.6.4 |
| O9 | The cleanup utility keeps the name `retention.py`. The **design concept** it implements is documented as adaptive pruning in `docs/` - see section 9 | P.6.4 |
| O10 | Feed selection tightens on measured quality. Reliability becomes a multiplier inside `authority()` | not in proposal |
| O11 | Visual-stage telemetry reaches the operator console. Every existing eval metric that is not yet on the console goes there too | P.6.2 |
| O12 | Model-assisted labelling is **approved**. `CLAUDE.md` section 0a is amended in the same commit with a narrow exception for visual labels | P.D12, P.L30, P.6.3 |
| O13 | Quote cards are **approved**, restricted to quotes identified by the semantic pass, not applied to every article | P.3.4.3, P.L32 |
| O14 | Visual asset base URL is config-driven. `raw.githubusercontent.com` is proven to work for SVG - see section 6 | P.4.4.4 |
| O15 | Features default **on** in code behind one `disabled_features` list. No config key per feature | not in proposal |
| O16 | **Nothing in the proposal is descoped.** No "v1" gate on any capability | P, all |
| O17 | The 4B router model is retired **completely** - config entry, workflow job, cache role, env vars, prompt, tests. No half job | P.D1 |
| O18 | The page uses the full width available on every medium - phone, tablet, desktop. No fixed canvas, no fixed pixel constraint | P.4.4.1 |
| O19 | Per-item colour may be derived from entity or brand identity by the model, degrading to the token palette when it cannot | P.4.4.1 |
| O20 | Caption is optional and rendered when present | P.3.1.1 |
| O21 | A visual is **earned**, never granted. Merit is justified by a machine-checkable gate, not by availability | P.3.3, P.4.1 |
| O22 | `n_ctx` rises to **16384** with `flash_attention` **on**, in one change. 32768 and above are refused - see section 11.2 | P.5.3 |
| O23 | `observability.tracing_enabled` becomes **true**. The file sink stays the only sink CI runs; a **derived per-shard aggregate** is committed and shown on the console, never the raw spans - see section 14.4 | P.6.1, P.6.2 |
| O24 | Six memory and context fields are added to `RuntimeCountersRow` from data the job **already collects and throws away** - see section 13.3 | P.5.3 |
| O25 | Duplicate collapse moves to the **plan stage**, before the safety ceiling and before sharding. No separate cross-shard dedup job - see section 14.2 | not in proposal |
| O26 | `pyproject.toml` gains pytest markers so a PR can run only what it touched. `page_weight.ceilings_bytes` is **kept** and re-baselined with headroom - see section 14.1 | not in proposal |
| O27 | Plan-stage dedup is **semantic**, using the ONNX encoder already in the dependency set, over a 48-hour window with decay. A pure title-string comparison is refused - see section 14.2 | not in proposal |
| O28 | A **prompt-iteration loop** ships: write, critique, revise, three rounds, two judges, and a deterministic gate that decides. `CLAUDE.md` section 0a is amended to permit it offline - see section 16.2 | not in proposal |
| O29 | `publish_telemetry.PUBLIC_COLUMNS` is widened by eight already-committed columns and every month republished, which **backfills the console for every past run** - see section 14.4b | P.6.2 |
| O30 | The span rollup lands in `state/span-rollup/`, **not** `state/telemetry-aggregate/`, which is taken by the item-health fold - see section 14.4a | P.6.1 |
| O31 | **Raw spans are committed** to `state/traces/<YYYY>/<MM>/<DD>-<run>-<shard>.jsonl` on a short rolling window, so the console can drill into a recent run. A lookup, so it deletes rather than folds | P.6.1 |
| O32 | `run.shard_timeout_minutes` rises 150 -> **200**. Free: Actions minutes are unmetered on a public repo, a timeout is a ceiling not an allocation, and the retired visual job returns its slot - see section 13.2 | P.5.3 |
| O33 | The prompt loop's primary targets are `unsupported_number`, `lead_missing` and `hedge_dropped` - deterministic and computable today. HHEM is the backstop, not the steering wheel. A regex cross-check of `unsupported_number` against the source over the committed test set ships with it, to verify **the checker** | not in proposal |
| O34 | **`band_reason` gets a console panel.** The five sentences a reader sees have never been plotted, so nobody can say whether summaries are improving or which defect dominates. This is the single most actionable eval gap on the project | P.5.5 |
| O35 | The visual moves **below** the summary. `ui.visual_side` is `above` today; Reader ruled that an 800px drawing above the text pushes the sentence they came for off a phone screen | P.4.4 |
| O36 | Susan's **19-row sufficiency bar** is lifted into `docs/concepts/design-system.md` as a build-failing oracle, not a review item. Rows 26 to 37 here are the subset already ruled; the full bar is the gate | P.4.4.1 |
| O37 | **Close authorship, never close discovery.** Code finds and cuts every character a reader will see; the model points at where to cut and says what the cut means. A quantity is discovered by regex by default, and the model may propose one the regex missed by naming its sentence, for code to re-parse from the article's own bytes. An entity name is a Tier 2 grouping key that is never drawn, anchored through per-sentence mentions. A quote or a claim is emitted as sentence indices, never as text. Section 1 and an earlier section 10.1 both got this wrong, in opposite directions - see section 10.1a | P.2.1.1, P.3.5 |
| O38 | **The pipeline is model-neutral; `InferenceConfig` is not, and the document must say which is which.** Every setting in sections 11.2 and 11.2a is a property of the entry `models.summarize` names plus this runner, not a constant of the design, and is quoted with that entry and that date. A model swap re-derives the whole block - see section 11.0 | P rule 1 |
| O39 | **The canonical glossary binds identifiers, not prose.** A module, class, contract field, telemetry value, config key or schema stem uses the proposal's glossary term verbatim; a plan-doc's prose keeps the plain register of section 0b - see section 15.4a | P rule 2 |
| O40 | **Deviation A is accepted as permanent, and its risk is written into `docs/` rather than left in this document.** The model assigns what a number means, and nothing verifies that: mis-pointing and mis-labelling both pass every span check (section 10.1a). A pattern cannot assign meaning, so the alternative is a chart whose axis reads "number". The limitation lives in [`../docs/concepts/digest.md`](../docs/concepts/digest.md) under the visual rule, so it survives this plan being consumed | P.1.5.2, section 12.10 |
| O41 | **A model may grade a finished visual in the review queue, and that is not a deviation.** Ruled at the level P.1.5.2 states the principle: a quality verdict reaches no reader and selects nothing to publish, so it touches no displayed value and no displayed string. **The four guardrails are the ruling, not a recommendation** - `label_source` and `model_id` stamped, a separate ledger, never pooled with human rows, never an input to a publish decision. Doc L merges with all four or it does not merge. Summary faithfulness labelling stays human-only. **This is not the same act as O40**: O40 is the model naming what a number means, which a visual draws; O41 is the model marking whether a finished visual was any good | P.1.4 non-goal 5, section 12.10, E1 |
| O42 | **The potential classifier is its own plan-doc, split out of G on 2026-09-04.** Section 12.11 G16 found it is three unbuilt things - a contrastive lexicon, a sequencing lexicon, and a date extractor correction C15 says does not exist - carrying an unstated inheritance of Deviation A. Left inside G, the element table could not merge until the hardest unsolved problem in this document was solved, and **G blocks H, I and J**. Split out, G ships a queryable fact table on its own and the chain moves. The cost is stated rather than hidden: one more plan-doc to write and track, and the measurement layer starts later than the element table | Section 15, 12.11 G16 |
| O43 | **Exactly two model calls per item. Always. No gate, no budget and no failure removes one.** Call 1 labels; call 2 writes the summary and the plan. **Call 2 runs for every item that publishes, because it is the call that writes the summary** - a gate can suppress the plan fields inside it and can never skip it. E5 ruled this on 2026-09-03 and three places in this document then contradicted it, so it is now a numbered decision rather than a sentence inside an escalation row. Splitting call 2 into two requests stays E5's conditional fallback and needs a measured timeout rate first; **until that measurement exists, a plan-doc proposing three calls is out of scope, not open.** The deterministic pass before call 1 is named **the candidate pass** and never "call 0", because a document that spells three things "call" cannot say "two calls" and be counted | O3, E5, 12.11 G17 |

---

## 4. Persona rulings - the freeze table

Seven advisors ran the bootstrap ritual and ruled on their own altitude (`CLAUDE.md` section 14). **SIGNED** means the owner of that altitude ruled and no other persona contradicts.

### 4.A Data model and extraction

| # | Title | Owner | Ruling | Proposal ref |
|---|---|---|---|---|
| 1 | Spans on the element | Fowler | Add `span_start`, `span_end`, `span_excerpt`. The regex already computes both offsets. `raw` cannot serve as the excerpt - it is whitespace-cleaned and drops the magnitude word and unit | P.2.1.1 |
| 2 | Span-drift invariant, three parts | Fowler | Write-time validator; read-time re-slice that degrades **that item** only (section 1a); CI contract test over canary fixtures. Not one build-failing gate | P.2.1.4, P.R5 |
| 3 | Per-element `source_text_hash` is dropped | Fowler | Redundant. If the text moved, `text[span] == span_excerpt` fails on the first moved element. One hash per article, reusing the existing content fingerprint | P.2.1.4 |
| 4 | **Code cuts every character a reader sees; the model points and names** | Andre, Owner O37 | Authorship is closed, discovery is not. A model has no character-level view and cannot count, so it never types a value: for a `quantity` it labels an `element_id` the candidate pass minted, or proposes a missed figure by sentence index for code to re-parse from the article's own bytes. For an `entity` or a `place` the model's `name` is a Tier 2 grouping key that is never drawn; code anchors the element through `mentions`, each verified inside its own named sentence. For a `quote` or a `claim` the model emits sentence indices and no text at all, and code slices the bytes - exact search over a long string rejects a real quote over one changed word, silently, which is worse than no check. Section 10.1a | P.2.1.1 |
| 5 | All six element kinds are in scope | Andre, Fowler | `quantity`, `entity`, `date`, `quote`, `claim`, `place`. Sequenced by risk, not by scope: `claim` lands last behind the verbatim-span validator | P.2.1, P.L31 |
| 6 | Open label vocabulary | Andre | Accept. Span-anchored, `label_source` stamped, `measure_canonical` emitted beside `measure` | P.D3, P.L4 |
| 7 | Corpus alias ledger is in scope | Andre | With `ledger_version` stamped on every computed score, and never compared across versions without re-scoring | P.2.2.3, P.R6 |
| 8 | Canonicalisation stays conservative | Andre | Over-merging is the silent direction. Log every merge, report `merge_rate`, prefer rejection when uncertain | P.2.2.2, P.R4 |

### 4.B The planner, the prompt, the model

| # | Title | Owner | Ruling | Proposal ref |
|---|---|---|---|---|
| 9 | **Extraction call runs first, summary second** | Owner, overriding Andre | See section 10. Andre proposed summary-then-plan; the owner rejected it because a lossy summary as the planner's source is the defect that produced this proposal | P.1.2 |
| 10 | The two calls are adjacent per item | Carmack | `n_parallel` is 1, so there is one cache slot. Batching all call-1s then all call-2s evicts the prefix and destroys reuse with no error | P.5.3.1 |
| 11 | Assert `cached_tokens`, not a `prefill_ms` ratio | Carmack, Andre | A ratio confounds cache reuse with delta length and reads as partial success when the prompt was built in the wrong order | P.L27 |
| 12 | Field order is decode order | Andre | Measured on this codebase: with `kind` first, `reason` became a rationalisation of a choice already made. Labels must be committed before the type is chosen | P.3.1.1 |
| 13 | Output budget rises from 400 | Andre | Derived from the schema's own bounds, re-derived whenever a bound changes. Never picked. See section 11.3 | P.3.1.1 |
| 14 | Bound every array and string in the contract | Andre | Makes the worst-case reply length arithmetic. Alarm on `finish_reason == "length"` | P.3.2 |
| 15 | Flat role map, all keys required | Andre | Optional arrays produced "a confident chart with no bars in it, twice, on the first live run". Not an 18-branch discriminated union. **Disambiguated 2026-09-03**, because P.D4 defines a different required set per type and one flat map of all-required roles would make a `bar` emit `quantity_x`, `size` and `bins`: every role name is a key, every key sits in the schema's `required` list so the decoder cannot omit one, and an inapplicable role is emitted as an **empty array**. The validator's existing "roles valid for the type" check enforces the per-type set and decides whether empty is legal there. Section 12.8 X2 | P.3.2 |
| 16 | Retire the 4B completely | Carmack, Owner O17 | Config entry, cache role, workflow job, env vars, prompt file, tests. Frees 2.33 GiB; repo cache falls from about 82 to 57 percent of the 10 GB ceiling | P.D1 |
| 17 | **A retry that perturbs nothing is refused, not budgeted** | Andre | P.R9's remedy is "perturb the rejection reason or the temperature", and on this design neither is available. Temperature jitter breaks the `seed: 0`, `temperature: 0.0` determinism contract - a re-run stops being a re-run. And there is no rejection reason to feed back, because P.L7 chose the downgrade ladder **over** a repair retry, so no validator failure ever re-calls the model. The only retry left is a **schema** retry, which fires before the validator has run and so has no reason to carry. Under greedy decoding a schema retry against identical input is bit-identical, making it a guaranteed-identical failure that costs a full decode. Ruling: a retry must perturb the **input** - drop the candidate table's tail, tighten the grammar, or raise `max_output_tokens` when `finish_reason == "length"` - and where no input perturbation applies, **do not retry at all**. `schema_retry_count` going bimodal is the symptom P.R9 named and marked addressed; a remedy that cannot fire does not address it | P.R9, P.L7, P.5.3.2 |
| 18 | `confidence` moves after `type`, or is deleted | Andre | Second in the field list means it conditions every field after it. Record, never gate | P.L23 |
| 19 | Carry the drop-the-minority lesson forward | Fowler | `same_unit_bars` records a live failure: a 4B picked three correct megawatt bars then appended a headcount. The behaviour becomes a committed fixture, not a comment | P.4.1 |
| 20 | Graceful degradation on context overflow | Andre, Owner | `context_exceeded` must degrade to a chunked read, not to nothing. See section 11.4 | P.1a |

### 4.C Rendering and the page

| # | Title | Owner | Ruling | Proposal ref |
|---|---|---|---|---|
| 21 | **Inline the SVG. Delete the `img` carrier** | Jony | Root cause of the unreadable dark theme. Swapping engines without this fixes nothing | P.4.4.2 |
| 22 | Progressive enhancement | Jony, Susan, Carmack | Build-time SVG, hydrate on point-or-focus. Hydration off by default per type; any hydrated route earns a `page_weight` entry before it merges | P.L21 |
| 23 | d3 is the single digest engine | Jony, Owner O5 | See section 7 for the type-to-module matrix | P.L18 |
| 24 | Exact-pin every d3 module | Carmack | A caret range lets a patch bump change pixels with no diff to review. Record in `renderer_version` | P.R17 |
| 25 | No fixed canvas | Susan, Owner O18 | The box is a function of what is encoded and of the space available. Retires `visuals.canvas_width`/`canvas_height` as a fixed pair | P.4.4.1 |
| 26 | Legibility floor | Susan, Jony | The smallest drawn string clears `--text-xs` (12px) **after** the scale-to-fit, at every supported width. Today it draws at 3.1 CSS px | P.4.4.1 |
| 27 | Density floor, renamed | Susan, Owner | Susan proposed a marks-per-height floor and called it information compression. The owner rejects the name: a size ratio carries no semantics and says nothing about faithfulness. It ships as **`density_floor`**, and the semantic measure keeps the name `information_delta` | P.5.2.1 |
| 28 | Token contract, with a derived-palette escape | Susan, Jony, Owner O19 | The compiler emits against the closed token set by default. The model **may** propose an entity-derived palette; it degrades to the token ramp when it cannot, and the derived colours are still contrast-checked in both themes | P.4.4.1 |
| 29 | The figure renders a caption when present | Susan, Owner O20 | `ItemVisual.svelte` renders `figure > img` and nothing else today, so `title` and `caption` have no home | P.3.1.1 |
| 30 | One mark lands first | Susan | `annotations` non-empty and drawn differently from its siblings. Eight bars of equal weight have no reading order | P.3.1.1 |
| 31 | Hydration is pixel-identical | Jony | A chart that redraws on hydrate is this project's first spinner in all but name | P.4.4.2 |
| 32 | Motion tokenised, bounded, killable | Susan | The largest committed day carries 621 items (2026-08-26). 621 entrance animations is a page that never settles | not in proposal |
| 33 | Keyboard route to every fact | Susan, Reader | No fact exists only on hover. The dominant device has no hover | P.4.3.2 |
| 34 | Empty is nothing | Susan | No placeholder, no reserved slot, no skeleton. Already true; written down so the downgrade ladder cannot reintroduce it | P.4.2 |
| 35 | A renderer bump re-renders whole days or none | Jony | Otherwise one page shows two drawing styles in one scroll, which reads as a broken site | P.R17 |
| 36 | Per-visual byte cap; over-cap degrades to `none` | Jony | There is no per-item route, so the visual lives on a list that reached 621 items | P.4.4 |
| 37 | The reading page is two contexts | Jony | Seed items are prerendered; past-seed items are drawn by the browser after a fetch. The compiled spec travels in the day payload and one code path draws both | not in proposal |

### 4.D Vocabulary

**Every type in P.3.4 ships.** The rulings below govern *how* and *in what order*, never *whether*.

| # | Type | Owner | Ruling | Proposal ref |
|---|---|---|---|---|
| 38 | `comparison` | Editor, Jony, Reader | Ships first of the infographic family. The only one whose compression argument survives contact with the page. Reader named it one of two they would actually want | P.3.4.3 |
| 39 | `quotecard` | Owner O13, Editor, Reader | Ships, restricted to quotes the semantic pass identified, capped at `summarize.max_verbatim_words`. Jony dissents on craft grounds; the owner overrules. Reader named it the other of the two they want | P.3.4.3, P.L32 |
| 40 | `callout` | **Editor** (P.L28 was assigned to Editor by name) | Ships under a three-part gate, all checkable with no model call: primary class `singular`; the figure is carried by our own title or standfirst; **and** either a span-anchored significance qualifier from a versioned list within one sentence, **or** the figure is the only quantity in the article. "Only" is admitted where "biggest" is refused - biggest is a fact about our sort order, not the world | P.L28, P.R20 |
| 41 | `whowhat` | Jony, Editor | Ships as a one-attribute `comparison` grid rather than a separate template. Each cell pairs an entity span and a claim span from the same sentence, or the cell is empty | P.3.4.3 |
| 42 | `keyfacts` | Andre, overruling four earlier vetoes | **Ships, and the objection was aimed at the wrong thing.** Two things share a name: `key_points` is the 3-5 summary bullets and nobody proposed removing them; `keyfacts` is the infographic that draws them bigger. The 7-in-8 restatement rate is a **prompt defect**, not a model-capability defect - see section 10.5. The kill criterion changes from a type-level veto that cannot fire without human labels to a **per-item gate: `keyfacts` may not render on an item whose new-fact rate is below the floor.** Machine-checkable on committed data, needs no labels, and is exactly O21 | P.3.4.3, P.L33 |
| 43 | `pie` | Jony, Owner | Ships as a declarable and buildable type under the P.3.4.1 gate: composition purpose, five parts or fewer, a **declared** whole never a summed one, one `measure_canonical`, one unit. Jony's stacked-bar routing is retained as the **downgrade target**, not as a replacement | P.L3 |
| 44 | `bubble` | Jony, Reader | Ships under the P.3.4.1 gate and the section 4.C legibility floor. Reader's objection is recorded: three numbers judged by circle area on a 360px screen | P.3.4.1 |
| 45 | `histogram` and derived values | Fowler, Owner | Ships. The Derived Value contract (P.2.3) is built with its closed allow-list `count`, `sum`, `share_of_declared_whole`, deterministic versioned binning, and a complete provenance chain | P.2.3, P.L22 |
| 46 | Diagram family | Editor, Jony | Ships. Gated behind the deterministic `processual` classifier so it never costs a non-process item a model call. Measured 2026-08-25: with diagrams enabled, 145 of 145 items reached the model and the stage spent its whole budget on 10 of 11 runs | P.3.4.2, P.L9 |
| 47 | Span-anchored edges, no exception | Editor | An unanchored arrow is an ordering or causal claim the article did not make. Reader: "wrong once, and I stop believing every summary on the page" | P.L19, P.R10 |
| 48 | Template order follows observed frequency | Jony | Not the fixed wave order in P.4.3.1. P.D2 makes the order derivable from `planned_type`, so guessing it is an unmeasured number justifying a design (Rule #10) | P.4.3.1, P.L2 |
| 49 | One day may not publish one shape | Susan | A day publishing a single rendered type is a recorded defect, read jointly with keep rate. Not a diversity target - the demand side of the P.R1 capitulation pair | P.L11, P.R18 |
| 50 | Downgrade ladder ships | Owner O16 | With **four** invariance rules - element set unchanged, purpose survives, escalating floor, and re-validation: a downgraded plan re-enters the same validator and the same compiler, and a depth that fails re-validation falls to the next depth rather than publishing (section 12.7 G8). Floors computed from depth-0 published visuals only, behind the `VISUAL_DOWNGRADE` flag | P.4.2, P.D6, P.L7 |

### 4.E Selection, retention, measurement

| # | Title | Owner | Ruling | Proposal ref |
|---|---|---|---|---|
| 51 | `safety_ceiling_per_run` is the honest knob | Editor, Carmack, Owner O6 | See section 8.2. Halving the ceiling is an editorial decision and must be presented as one, not as throughput | P.L14 |
| 52 | Cut duplicates first, never a desk's only story | Editor | Score is authority x carriers, so a single-carrier story scores lowest by construction. A straight top-N cut is a systematic cut of the exclusive story | not in proposal |
| 53 | Feed reliability multiplier | Editor, Owner O10 | Multiplicative inside `authority()`, never an added bonus - additive lets a feed buy its way across a tier. Trailing window no shorter than 30 days, clamped to a floor above zero and a ceiling of 1.0, and it may **only ever reduce**. All 191 `weight` values in `config/sources.json` are 1.0, so the manual lever has never been pulled | not in proposal |
| 54 | Add `ItemStage.VISUAL` | Fowler | Additive, one changelog entry, no migration. Today "no visual was possible" and "the visual stage broke" are the same row | not in proposal |
| 55 | `state/visuals/` ledger | Fowler | One appended row per **visual attempt**, not per published visual, sharded monthly, same shape as `state/item-health/`. `decision` separates published, downgraded, `none` and rejected. A per-publication ledger would leave every refusal, every `none` and every typed rejection reason uncommitted, and the machine loop would stop being auditable while still being the gate - section 12.7 G7. No query surface; there is no server (Rule #1) | P.R12 |
| 56 | Every rate is reported per potential class | Andre, Editor | Without a denominator of what was possible, 4 percent on narrative and 4 percent on chartable are the same number | P.2.4, P.L35 |
| 57 | `narrative` records **why** it is narrative | Editor | Otherwise an extraction outage reads as a quiet month of unvisualisable news, and P.R2 hides inside the residue class | P.2.4.2 |
| 58 | A quote-led potential class is added | Editor | The safest type in the system has no denominator in P.2.4 as written | P.2.4.2 |
| 59 | Widen `retention.py`; do not create a module | Fowler, Owner O9 | It already reasons about all four policies: the alarm, the visual prune, the telemetry fold, the seen prune | P.6.4 |
| 60 | `PAGES_HARD_CAP_MB` to config with `le=1024` | Carmack, Fowler, Owner O7 | Config can lower it and cannot raise it, so Rule #2's "the budget is the platform, not a preference" stays enforceable | P.6.2 |
| 61 | `dry_run = false` lands **after** the new renderer | Fowler, Owner O8 | Flipping the delete fuse while the old Vega-Lite SVGs are the only assets on disk deletes a year of visuals with `max_deletes_per_run: 200` the only bound | P.6.4 |
| 62 | Cleanup records `candidates_found` and `skipped_by_fuse` | Carmack | `deleted` is capped at 200, so `deleted` alone can never show whether the backlog is shrinking | P.6.4 |
| 63 | Delete `VisualKind.IMAGE` and `SpecFormat.IMAGE_PROMPT` | Fowler | No renderer, never exercised, skipped unconditionally. Check the committed corpus first - it is a published enum | not in proposal |
| 64 | Wire in the existing faithfulness scorer | Fowler, Andre | The eval ledger, `ConfidenceBand` and `BandReason` already exist and `LabelRow` already imports `ConfidenceBand`. Do not build a second scorer (Rule #8) | P.L25, P.Q8 |
| 65 | Never show `why` to a reviewer | Andre | `LabelRow` already hides the machine score from the labeller for the same reason | P.R14 |
| 66 | Call it offline paired evaluation | Andre | "A/B testing" names a mechanism Rule #1 forbids, and the numbers would eventually be quoted as if readers produced them | P.L26, P.6.3.4 |
| 67 | Weight fitting, pairwise mode and the timed arm all ship | Owner O16 | Andre and Carmack proposed deferring them because 0 of 60 drawn rows carry a human label as of 2026-08-28. The owner overrules on scope; the labelling-capacity risk is recorded as M6 in section 13 | P.5.2.3, P.5.4.3, P.L34 |
| 68 | Rejected plans are recorded and rendered | Andre, Owner O16 | Recorded as JSON immediately (near-free); rendered into `review/` for labelling. Renders are build artifacts under the 500 MB artifact ceiling, never committed, never under `frontend/public/` | P.D12, P.L30, P.R3 |
| 69 | `run.route_budget_minutes` must be re-derived | Fowler, Carmack | It exists because the old job ran 51-60 minutes against a 60-minute bound. Folding into `work` invalidates the number | P.5.3 |
| 70 | Every existing eval metric reaches the console | Owner O11 | `ConfidenceBand`, `BandReason`, `verbatim_run`, faithfulness, lead coverage and the new visual metrics all get a panel. Stored sharded under `state/` | P.6.2 |

---

### 4.F Where the personas disagreed, and how it was settled

Most of section 4 is unanimous. These seven are not, and a ruling that hides a real disagreement is worth less than one that names it.

| Subject | The disagreement | Settled how |
|---|---|---|
| `keyfacts` | Editor, Jony, Susan and Reader all voted to kill it. Reader: *"a 3-to-5 bullet box next to a summary that already has 2 to 5 key points is the same thing printed twice."* Andre disagreed with all four | **Andre wins on diagnosis.** The four aimed at the wrong target: `key_points` is the summary field and `keyfacts` is the infographic. The 7-in-8 restatement rate is a prompt defect (section 10.5), not evidence against the type. Ships with a per-item gate instead of a type-level veto |
| `quotecard` | Jony rejects it as "one sentence in a bigger font with a border". Reader named it one of only two types they actually want. Editor accepts it. Andre flagged it against the republishing non-goal | **Owner ruled (O13).** Ships, restricted to quotes the semantic pass identifies, capped at `summarize.max_verbatim_words` |
| Visual placement | Jony assumed the visual keeps its slot. Reader said it is *"in the way"* and pushes the sentence off a phone screen | **Reader wins.** O35 moves it below the summary |
| `pie` | Jony would build no pie template at all, routing composition to a stacked bar. The owner wants the type | **Both.** Pie ships under its gate; the stacked bar becomes its downgrade target rather than its replacement |
| Prompt-loop target | Andre built the loop around HHEM and an incumbent comparison. The owner said that over-complicates it | **Owner wins.** The three deterministic checks steer; HHEM is the backstop (O33) |
| Call ordering | Andre ruled summary first, then plan. The owner rejected it outright | **Owner wins.** Extraction first. A lossy summary as the planner's source is the defect that produced this work (section 10) |
| Scope deferrals | Andre and Carmack both proposed deferring the fitter, the pairwise page and the timed arm on the grounds that zero labels exist | **Owner overrules (O16).** All ship; the labelling-capacity risk is recorded as M6 rather than used as a scope cut |

**One warning that no persona contradicted, recorded because it is the failure mode this project has already had once.** Susan: the design measures 33 things about a visual and not one of them is whether a person would choose to look at it. Every binding gate is integrity or cost, and a plain grey bar chart passes all of them. Making the sufficiency bar advisory is how this ships as another minimum-that-passes-every-veto.

## 5. Reversals - everything wrongly scoped, now restored
An earlier draft of this record deferred the following. **All are in scope.** Recorded so the omission cannot recur.

| # | Was deferred as | Restored scope | Proposal ref |
|---|---|---|---|
| RV1 | Element kinds `quantity` + `date` only | All six kinds: `quantity`, `entity`, `date`, `quote`, `claim`, `place` | P.2.1 |
| RV2 | Corpus alias ledger dropped | Built, with `ledger_version` stamping and conservative merge logging | P.2.2.3 |
| RV3 | Derived values, `histogram`, `pie` "contract written, not built" | Built, with the closed function allow-list and provenance chains | P.2.3 |
| RV4 | `d3-force` out | In. It is the layout for the node-edge graph family | P.3.4.2 |
| RV5 | Weight fitting, pairwise page, timed comprehension arm deferred | All built | P.5.2.3, P.5.4.3 |
| RV6 | Rejected-plan renders deferred | Built | P.D12 |
| RV7 | `keyfacts` killed | Built, with the kill criterion attached | P.3.4.3 |
| RV8 | Downgrade ladder unmentioned | Built behind `VISUAL_DOWNGRADE` | P.4.2 |
| RV9 | Diagram family deferred behind infographic | Both ship; the ordering is a dependency, not a scope cut | P.3.4.2 |
| RV10 | `bubble` pushed to "wave 3 at the earliest" | Built under its gate | P.3.4.1 |
| RV11 | Article Visual Potential classifier implied optional | Built. Every rate depends on it | P.2.4 |
| RV12 | Draco named only as "a candidate worth evaluating" | Evaluated explicitly as a validator component, with a written verdict | P.4.4.5 |

---

## 6. Serving visual bytes off the Pages bundle

**Measured 2026-09-02**, `Invoke-WebRequest -Method Head` against
`https://raw.githubusercontent.com/miztiik/yen-idhazh/refs/heads/main/frontend/src/lib/icons/svg/archive.svg`:

```
STATUS = 200
Content-Type: image/svg+xml
Cache-Control: max-age=300
Access-Control-Allow-Origin: *
Cross-Origin-Resource-Policy: cross-origin
Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; sandbox
X-Content-Type-Options: nosniff
```

**SVG works.** The concern that this host serves SVG as `text/plain` is withdrawn - it serves `image/svg+xml`, so an `img` tag renders it.

Three consequences, and one of them is a genuine conflict.

| Finding | Consequence |
|---|---|
| `Content-Type: image/svg+xml` | The remote carrier is viable. Bytes leave the Pages 1 GB cap |
| `Cache-Control: max-age=300` | Five minutes. A repeat reader refetches. The Pages CDN caches far longer, so this is a real cost on a slow connection |
| **An SVG in an `img` still cannot read the page's custom properties** | The remote carrier and CSS theming are mutually exclusive **for the `img` path** |

### 6.1 The resolution

| Path | Carrier | Themed | Counts against Pages | Use |
|---|---|---|---|---|
| Seed items (prerendered) | **Inline SVG** in the HTML | Yes | Yes, gzipped | Default. Row 21 |
| Past-seed items (already fetched by the browser) | Fetch the SVG and inline it into the DOM | Yes | **No** | The long tail, where the byte pressure actually is |
| Raster fallback, archives | `img` with the config base URL | No | No | Anything not themed |

This gives themed visuals everywhere and moves the growing tail off the Pages cap. It works because the reading page is already two contexts (row 37) - past-seed items already require a fetch.

**Config shape**: `visuals.asset_base_url`, defaulting to same-origin. Pointing it at `raw.githubusercontent.com` in this repo, then at another branch, repo or Pages site later, is one config edit. Branch-based raw URLs survive the `prune.yml` force-push because the prune squashes history and leaves the working tree intact; only commit-SHA-pinned URLs break.

### 6.2 What still needs measuring

- Repository pack growth per published day, from two dates differenced. The prune bounds the past; it does nothing about a growing present.
- Checkout cost with and without a blob filter. At 4 workers plus plan and assemble that is six checkouts a day of a tree carrying every visual ever published.
- Throttle behaviour on `raw.githubusercontent.com` under a burst at the page's real image count. The limit is undocumented, so the degraded state must be explicit.

---

## 7. The d3 matrix - one engine for the digest

**Decision O5: d3 alone. ECharts is not used for digest visuals.**

### 7.1 Why

The owner's complaint is that the current visuals are "extremely ugly", static, and that ECharts is doing a bad job. The diagnosis in section 2.1 shows the carrier is the primary cause - but the engine choice still matters for what O1, O18 and O19 ask for:

| Requirement | ECharts | d3 |
|---|---|---|
| Brand or entity-derived colour per mark (O19) | Fights you; series colour is a chart-level concept | Native; every mark is authored |
| Non-standard marks (a car glyph sized by units) | Effectively not available | Native |
| Full-width responsive with no fixed canvas (O18) | Container-driven, resize handler needed | Pure function of width; recompute and re-emit |
| Node-edge graph | `graph` series, tuned for exploratory network layout | `d3-force`, `d3-hierarchy`, `d3-dag` - the reference implementations |
| Bytes shipped to a reader | Full engine if hydrated | Only the modules used, and zero if not hydrated |
| Code we own | Less | More |

The cost of d3 is stated plainly: **more code to write, and axis, legend and tooltip behaviour we author rather than inherit.** That is the trade the owner is buying, and it is the right one when the goal is a visual that looks made rather than generated.

### 7.2 Type to module matrix

This matrix is the record of the decision and moves into `docs/architecture/publishing/` when the plan executes.

| Visual type | Purpose | d3 modules | Notes |
|---|---|---|---|
| `bar` | ranking, category comparison | `d3-scale` (band, linear), `d3-shape`, `d3-axis` | Baseline. Horizontal by default at narrow widths |
| `dot` | ranking | `d3-scale`, `d3-shape` (symbol) | Cleveland-McGill preferred form for ranking |
| `line` | trend | `d3-scale` (time, linear), `d3-shape` (line, curve) | |
| `area` | cumulative magnitude | `d3-shape` (area) | Gated to stock or cumulative measures, never a rate |
| `scatter` | relationship | `d3-scale`, `d3-shape` (symbol) | |
| `bubble` | relationship, 3 channels | `d3-scale` (sqrt for size), `d3-shape` | `scaleSqrt` is mandatory - a linear radius misstates area |
| `slope` | before/after | `d3-scale`, `d3-shape` (line) | No axis; two labelled columns |
| `stacked_bar` | composition | `d3-shape` (stack), `d3-scale` | Also the `pie` downgrade target |
| `pie` | composition, declared whole | `d3-shape` (pie, arc) | Under the P.3.4.1 gate |
| `histogram` | distribution | `d3-array` (bin), `d3-scale` | Binning rule is versioned config, not model-chosen |
| `timeline` | sequence of dated events | `d3-scale` (time), `d3-axis` | |
| `table` | precise multi-dimensional | none - typeset HTML | Not an SVG artefact |
| `flow` (diagram) | process | **`d3-force`** or `d3-hierarchy`, plus `d3-shape` (link) | Force for genuinely branching graphs; `d3-hierarchy` (tree) for a chain or tree |
| `comparison` | qualitative grid | none - typeset HTML | |
| `callout` | one striking figure | none - typography in the item's own scale | |
| `quotecard` | attributed statement | none - typography | |
| `whowhat` | actors and roles | none - one-attribute `comparison` | |
| `keyfacts` | 3-5 takeaways | none - typography | |

Shared across all SVG types: `d3-scale`, `d3-array`, `d3-format` (number formatting), `d3-time-format` (date labels), `d3-selection` **only in the hydrated path** - the build step emits markup as strings, so no DOM is needed at build time.

### 7.3 `d3-force` determinism

`d3-force` is used for the node-edge graph and nothing else. The non-determinism people hit is the **wall-clock timer**, not the algorithm: d3 places nodes on a deterministic phyllotaxis spiral when `x`/`y` are unset, and its jiggle uses a constant-seeded generator. The recipe:

1. Construct with the simulation stopped. Never let the internal timer run.
2. Sort nodes and links by `element_id` before construction - iteration order changes the result.
3. Never carry `x`/`y` in from a previous run or a cached plan.
4. Run exactly N ticks in a synchronous loop, N from `config/` (Rule #6). N = 300 matches the default schedule, where alpha reaches `alphaMin` 0.001.
5. Round output coordinates to a fixed precision so float drift is not a diff.
6. Exact-pin `d3-force` and record it in `renderer_version`.
7. Test: same input rendered twice in one process and once in a fresh process, byte-identical after rounding.

Cost is an estimate, not a measurement: roughly 5-20 ms per graph on 4 vCPU at a 30-node cap. At the current visual rate that is about a second of build time a day.

### 7.4 The console is not migrated by this plan

The console keeps ECharts. It has 23 test files, a working sentinel bridge, and no complaint against it. Migrating it to d3 is a separate decision and a separate plan-doc if it is ever wanted.

---

## 8. Scale, sharding and the runner

### 8.1 Model download - the answer to the bandwidth concern

The weights are **not** downloaded once per shard. `actions/cache@v6` holds `backend/models` and `backend/bin` under the key `llm-<file>-<revision>-<build>-v4`, and the Hugging Face fetch runs only `if: steps.weights.outputs.cache-hit != 'true'` ([.github/workflows/digest.yml](.github/workflows/digest.yml#L411)). Every shard shares one key, so **raising the shard count adds cache restores, never downloads.**

What the shard log shows as "downloading" is the cache *restore* printing byte progress. That is a real cost - a 5.29 GiB restore per worker - but it is internal to GitHub, not Hugging Face, and it does not consume an external bandwidth budget.

The 10 GB per-repo cache ceiling is the real pressure: 5.29 (summarizer) + 2.33 (router) + the llama.cpp build is roughly 8.18 GB, about 82 percent. **Retiring the router (O17) drops that to about 57 percent.**

### 8.2 `shard_size` vs `max_parallel` vs `safety_ceiling_per_run`

The three are not interchangeable and the naming misleads.

```
shards = max(1, min(ceil(items / shard_size), max_parallel))
```
[backend/idhazh/cli.py](backend/idhazh/cli.py#L709)

| Knob | What it actually is | Value |
|---|---|---|
| `run.max_parallel` | **The number of worker jobs.** Each appears as `shard-{N}` and commits under that name | 4 |
| `run.shard_size` | URLs per worker VM, sized by model-load amortisation. **Above 20 items a day it never binds** - the `ceil` term always exceeds `max_parallel` | 5 |
| `run.safety_ceiling_per_run` | **What sizes a run.** Items per worker is this divided by the worker count | 160 |

Where 160 came from, quoted from its own field description: it began as a crash guard against a mis-parsed feed, supply overtook it, and `items_planned` has been exactly 160 on every run since 2026-08-25. Owner decision 2026-08-29 kept it at 160.

**The owner's instruction resolves to one edit.** To get 20 items per worker with 4 workers:

| Knob | Today | Becomes | Effect |
|---|---|---|---|
| `run.safety_ceiling_per_run` | 160 | **80** | 80 / 4 = 20 items per worker |
| `run.max_parallel` | 4 | **unchanged** | Still 4 cache restores per run, not 8 |
| `run.shard_size` | 5 | **unchanged** | It does not bind; changing it is noise |

This is cheaper than raising `max_parallel` to 8, which would keep 160 items but double the 5.29 GiB restores. It is an **editorial** decision - the day publishes half as many items - and Editor's ruling (row 52) governs which half is lost: duplicates first, never a desk's only story.

All three knobs are in `config/idhazh.json` under `run`.

### 8.3 Measured shard cost and memory

Read from the whole of [state/runtime-counters.csv](state/runtime-counters.csv) on 2026-09-02, not from a sample. 104 rows; 80 carry `job_seconds`; 72 carry `peak_rss_bytes`.

| Metric | n | Distribution | What it means |
|---|---|---|---|
| `job_seconds` at 40 items | 80 | min 1,584 s, p50 4,711 s, p90 6,101 s, p95 6,380 s, **max 8,124 s** | 26.4 min, **78.5 min median**, 101.7 min, 106.3 min, **135.4 min worst**. The worst shard used **90.3 percent of the 150-minute timeout**. The median used 52 percent |
| `peak_rss_bytes` | 72 | min 10.06 GiB, p50 12.60 GiB, **max 13.29 GiB** | Against 16 GB (14.90 GiB usable) the worst shard left **1.61 GiB free** |
| `model_load_ms` | 72 | 2,336 to 4,166 ms | Opening 5.29 GiB of weights costs 2.3 to 4.2 s |
| `n_tokens_max` | 29 | 2,549 to 5,516 | The largest prompt ever seen is 5,516 tokens, **67 percent of the 8192 window** |
| `prompt_tokens_cached_total` / `prompt_tokens_total` | 29 | 0.72 to 0.90 | Prefix caching already works |

**Two corrections to earlier drafts of this document, both mine.** An earlier version read only the first 30 lines of the ledger, which are its oldest, and reported that `peak_rss_bytes` and `model_load_ms` were empty in every row and that a shard runs 46 to 70 minutes. Neither is true. Memory has been measured since 2026-08-30 and the worst shard is nearly twice as slow as I said. The lesson is recorded because it changed two rulings: **a ledger is sorted oldest-first, so a head read measures the past.**

At 20 items the base work roughly halves - median about 39 minutes, worst about 68 - which leaves the margin the second call spends. The margin is real but it is not luxurious: sizing from the worst case rather than the median is the whole of Rule #2 here, and the worst case is 135.4 minutes, not 70.

### 8.4 Per-feed context routing - worth building

The owner's idea: route consistently long-form feeds to a worker started with a larger context, and short-form feeds to a worker with a smaller one.

This is implementable and cheap, because the pieces exist. The `plan` job already computes the shard matrix and emits it as an output. `server_argv` already reads `n_ctx` from config. `item-health` already records `source_words_before_cap`, so **which feeds are consistently truncated is already measurable from committed data.**

Shape: a `long_form` flag per feed derived from a trailing window of `source_words_before_cap`, the plan job partitions items into a long-context shard set and a short-context set, and each worker starts its server with the `n_ctx` its partition needs. Gains headroom for the two-call design without raising memory everywhere.

Blocked on the memory measurement in section 13 (M1).

---

## 9. Adaptive pruning - the design concept

Decision O9 keeps the module name `retention.py`. What follows is the **design concept** the module implements, to be written into `docs/concepts/adaptive-pruning.md` so a coding agent has a target to comply with. The names "intelligent pruner" and "intelligent compaction" were rejected: "intelligent" and "adaptive" claim a property the code does not have when it merely reads a date, and "compaction" is borrowed from log-structured storage where it means something else (section 0b).

### 9.1 The five properties

| Property | What it means | Why it is not optional |
|---|---|---|
| **Config-driven** | Every window, fuse and cutoff is a knob in `config/idhazh.json` behind a Pydantic model. No literal dates, no literal counts | Rule #6 |
| **Atomic** | One deletion or fold is one file, written temp-then-rename where it rewrites. A failed unit never damages a sibling | Section 1a |
| **Shard-aligned** | Cleanup operates on the same monthly shards the writers produce, so a fold reads one file and writes one file | A cleanup that must read a year to delete a day cannot finish in a job |
| **Fused** | No run may delete more than `max_deletes_per_run`, and the run reports the backlog it did not clear | An off-by-one in a date parse must not eat the archive |
| **Heuristic-ready** | The policy that selects candidates is a named, testable predicate, so an age rule, a size rule or a value rule are interchangeable | Age is the only honest rule today; that will not always be true |

### 9.2 The four policies, and what each does

| Policy | Acts on | Rule | Knob |
|---|---|---|---|
| **Alarm** | The **built** bundle, never the payload tree | Measures and reports; deletes nothing | `retention.site_budget_mb`, `PAGES_HARD_CAP_MB` |
| **Asset prune** | Rendered visuals under the digest tree | **Age only, never size.** A size-triggered prune deletes most on the day the reader has most to read | `retention.image_months`, `max_deletes_per_run`, `dry_run` |
| **Ledger fold** | `state/item-health/`, `state/scores/`, and every new ledger | Past the window a month folds to one row per group and the full-grain shard is deleted. The aggregate is kept forever | `observability.keep_months`, `hard_delete_after_months` |
| **Lookup prune** | `state/seen/` | Deletes without folding. A lookup outside its read window answers no question, so folding it would invent a total nobody reads | `collect.seen_window_days` |

**The rule that decides which policy applies: a ledger folds, an asset deletes, a lookup deletes.**

**Correction, 2026-09-03: `observability.keep_months` and `observability.hard_delete_after_months` no longer exist, so every `keep_months` cell in this section and in 9.3 names a knob nothing reads.** The source-health lifecycle work replaced one shared age with one named age per store - `item_health_full_grain_months`, `item_health_aggregate_keep_months`, `feed_health_keep_months`, `scores_full_grain_months`, `score_archive_keep_months` and `public_telemetry_keep_months`, all listed in [`../docs/concepts/config.md`](../docs/concepts/config.md). A config that still spells either old name now fails validation and is told its replacement, so this is not a rename that quietly resolves. Which named window each of the six ledgers below should take - `state/visuals/` most of all, since nothing owns it yet - is this plan author's call, and it has to be made before the row that writes that store lands.

**Correction, 2026-09-04: the glossary's `Ledger` is false as written, and 15.4a binds identifiers to that glossary.** The proposal defines a ledger as "an append-only file, never edited in place - so history is always recoverable", and the fold above deletes the full-grain shard. Both are wanted: the proposal's own Q9 asks what stops an append-only ledger growing without bound, and 12.4 answers it with this fold. **The definition narrows to: append-only within its window; folds to a durable aggregate; never edited in place at full grain.** That is what every row of 9.3 already does, and the one store the fold must never touch is registered as such - `state/labels.csv` is the only ground truth and is never deleted.

**And the fold's group key is a per-store declaration, not a global rule.** "One row per group" above names no key, and the key is what decides whether the fold preserves a breakdown or erases it. `state/telemetry-aggregate/` already sets the pattern by declaring its key in the schema description. `state/visuals/` is the store where the choice is load-bearing - section 12.9 G12.

### 9.3 The compliance register

Every artefact this project writes declares which policy governs it. This table is the register and lives in the doc.

| Artefact | Grain | Policy | Window |
|---|---|---|---|
| `frontend/public/digest/<Y>/<M>/<D>/*.svg` | file | asset prune | `image_months` |
| `frontend/public/digest/<Y>/<M>/<D>/*.json` | file | **never deleted** - the record that a day happened | - |
| `state/item-health/<YYYY-MM>.csv` | monthly shard | ledger fold | `keep_months` |
| `state/scores/<YYYY-MM>.csv` | monthly shard | ledger fold | `keep_months` |
| `state/feed-health/<YYYY-MM>.csv` | monthly shard | ledger fold | `keep_months` |
| `state/telemetry-aggregate/<YYYY-MM>.csv` | monthly shard | kept forever | - |
| `state/runtime-counters.csv` | append-only | ledger fold | `keep_months` |
| `state/seen/<YYYY-MM>.csv` | monthly shard | lookup prune | `seen_window_days` |
| `state/published.csv` | append-only | **never deleted** | - |
| `state/labels.csv` | append-only | **never deleted** - the only ground truth | - |
| `state/visuals/<YYYY-MM>.csv` (new) | monthly shard | ledger fold | window **and group key** both open - section 12.9 G12 |
| `corpus/corpus.jsonl` | rolling window | rewritten by `prune.yml` | `prune_keep_days` |
| `frontend/public/telemetry/<YYYY-MM>.csv` | monthly shard | published projection; follows its source | `keep_months` |
| `review/` renders | build artifact | deleted after labelling; never committed | artifact retention |
| `state/rejected-plans/<YYYY>/<MM>/<DD>.jsonl` (new) | daily file | lookup prune - a rejected plan body answers no question outside its review window, so folding it would invent a total nobody reads | short rolling window, section 12.7 G10 |

### 9.4 Sharding enables the cleanup, and the cleanup enables the sharding

The relationship the owner named, stated plainly so the doc records it: monthly sharding is what makes a fold an atomic single-file operation, and an atomic fold is what makes cleanup safe enough to enable at all. A ledger written as one growing file could only be cleaned by rewriting the whole thing, which is neither atomic nor bounded. **This is why `dry_run` can move to false: not because the policy got smarter, but because the storage shape makes each unit small and reversible.**

### 9.5 What the run must record

One row per cleanup run, so the operator sees the backlog rather than guessing:

`candidates_found`, `deleted`, `skipped_by_fuse`, `fuse_tripped`, `cutoff_date`, `oldest_kept`, `bytes_reclaimed`, `site_bytes_before`, `site_bytes_after`, `dry_run`, `policy`.

`deleted` is capped at `max_deletes_per_run`, so **`skipped_by_fuse` is the only field that shows whether the backlog is shrinking.** The console panel is that series over time.

---

## 10. The prompt flow - the owner's ordering

Andre proposed: call 1 = summary, call 2 = plan against that summary. **The owner rejected it**, and the rejection is correct on the project's own evidence: using a lossy summary as the planner's source is the defect that produced this proposal. Summarisation is extractive, padded and unsatisfactory today; planning on top of it inherits every one of those failures.

### 10.1 The ordering that ships

```
CANDIDATE PASS - CODE READS THE ARTICLE  no model, no network, microseconds
  in:  sanitized article text
  out: candidates: [ {element_id, kind, surface, span_start, span_end,
                      value, unit, sentence_index, extractor}, ... ]
       -> every quantity the number pattern can find, with the offsets that
          prove where it came from and the magnitude already multiplied
          out. `numeric_facts()` does this today. `extractor` is "regex".
       -> two holes, both recorded as corrections C14 and C15. The dedup is
          on (value, unit), so a figure repeated across two periods
          collapses to one - call 1's `proposed` is what recovers it. And
          there is no date extractor at all, so `date` is new work in
          plan-doc G rather than a rename of something that ships.

CALL 1 - LABEL, NAME AND POINT
  in:  [system: extraction + semantic rules]
       [user:   title
                + <UNTRUSTED>full article text</UNTRUSTED>
                + candidate table, indexed by element_id]
  out: { labels:    [ {element_id, measure, entity, dimension, time,
                       salience, attribution, hedge}, ... ],
         proposed:  [ {sentence_index, surface}, ... ],
         entities:  [ {name, entity_type, salience,
                       mentions: [{sentence_index, surface}, ...]}, ... ],
         places:    [ {name, geo_hint,
                       mentions: [{sentence_index, surface}, ...]}, ... ],
         quotes:    [ {sentence_start, sentence_end, speaker_mention}, ... ],
         claims:    [ {sentence_start, sentence_end, attribution, hedge}, ... ],
         events:    [ {action, actor, object, when}, ... ],
         relations: [ {from, to, relation, sentence_index}, ... ] }

  what code does with each - and it is a DIFFERENT check per kind:

    labels   -> may cite only an element_id the candidate pass minted. An
                unknown id is dropped. No field here accepts a number, so
                authorship is impossible by grammar rather than caught by a
                check.
    proposed -> the escape hatch for a figure the regex missed. Code searches
                ONLY the named sentence, demands exactly one hit, and
                re-parses value and unit with the same number pattern over
                the article's own bytes. Stamped extractor="model_proposed",
                capped per article. A spelled-out number and a relative
                change ("doubled") stay refused - there is nothing to parse.
    entities -> `name` is Tier 2. It is a grouping key for the alias ledger
      places    and it is NEVER drawn. Each mention's `surface` must occur
                exactly once inside its own named sentence, and that mention
                is the span. Zero surviving mentions drops the element. The
                drawn label is the longest surviving mention, never `name`.
    quotes   -> indices only, no text. Code slices the bytes. Exact search
      claims    over a long string rejects a real quote over one changed
                word, silently, which is worse than no check at all. This is
                the same instrument section 10.6 already bought for the lede
                and quote indices.

CALL 2 - UNDERSTAND AND DECIDE          <- appends to call 1's message array
  in:  [ ...everything above, unchanged... ]
       [assistant: call-1 JSON]
       [user: summarise + plan the visual, given the elements you just found]
  out: { summary: {title, standfirst, key_points},
         visual:  {decision, purpose, type, encodings, element_ids,
                   labels, annotations, caption, why} }
```

### 10.1a Who finds what

**One sentence governs all six kinds:**

> Code finds and cuts every character a reader will see. The model points at where to cut, and says what the cut means.

#### Rejected alternatives

Each is the natural over-correction of the other, so both are recorded. Authority: Andre, 2026-09-03.

| Rejected | Why |
|---|---|
| **The model emits a verbatim surface for every element, numbers included, adjudicated afterwards by exact search** | A number the model types is a number the model authored. Exact search cannot tell a real number from a real number pointed at the wrong sentence, and the span it mints is valid either way |
| **Only the regex may discover a quantity, and an entity name must exact-match the article** | Closing authorship is right; closing discovery is not. The regex deletes the series a trend chart exists to show, and an entity name is a label, not a location. Both are shown below |

**Why the regex cannot be the only discoverer.** `numeric_facts()` is lossy by design, and its losses land on exactly the articles a chart would serve. It dedupes on `(value, unit)` ([backend/idhazh/route.py](backend/idhazh/route.py#L165)), so twelve percent in one quarter and twelve percent in another become one candidate - it deletes the series a trend chart exists to show. It drops any magnitude at or below 2 with no unit ([backend/idhazh/route.py](backend/idhazh/route.py#L163)), drops a bare four-digit year ([backend/idhazh/route.py](backend/idhazh/route.py#L158)), nulls a unit word on a stop-list ([backend/idhazh/route.py](backend/idhazh/route.py#L144)) and stops at 16 ([backend/idhazh/route.py](backend/idhazh/route.py#L176)). Every one of those is a correct call for its original job - picking a few bars - and a wrong call for a candidate set. `proposed` is the recovery, and it stays safe because code, not the model, does the parsing: the model names a sentence, code re-parses the bytes.

**Why an entity name is not searched.** Exact search confuses a location with a label. An article writes "Vestas Wind Systems A/S" once and "Vestas" four times, and the canonical name may appear nowhere verbatim. Entity resolution is precisely what a semantic model is good at and string matching is bad at. The proposal's own Tier 1 / Tier 2 split answers it: the **mention** is Tier 1 and gets anchored per sentence, the **name** is Tier 2, is a grouping key for the alias ledger (row 7), and is never drawn. The same reasoning retires exact search for `quote` and `claim` - a long string rejected over one changed word fails silently, and a sentence index cannot.

**What the model never does.** It never types a value. `RouteDraft`'s docstring already records why that matters: the contract carries "no free numeric field anywhere, so the worst an injection can do is pick the wrong bars" ([backend/idhazh/route.py](backend/idhazh/route.py#L193)). `numeric_facts()` computes `match.start()` and `match.end()` ([backend/idhazh/route.py](backend/idhazh/route.py#L126)), `fact_menu()` prints them indexed ([backend/idhazh/route.py](backend/idhazh/route.py#L232)), and `ChartPoint.fact_index` is an index, never a value ([backend/idhazh/route.py](backend/idhazh/route.py#L187)). That reference survives as a stable `element_id` (correction C13).

**Two failures the design still has to watch, because no anchoring check sees either.**

| Failure | Caught by? | Control |
|---|---|---|
| **Mis-pointing** - the model means one `"5"`, the anchor lands on another | No. The span is real, so `text[span] == span_excerpt` passes, the write-time validator passes and the read-time re-slice passes | The per-sentence rule. A surface is searched inside one named sentence and must hit exactly once, so ambiguity is a rejection rather than a coin toss |
| **Mis-labelling** - right number, wrong `measure`, `unit` or `entity` | No. These are Tier 2 and no string search reaches them | An id-cited label is checkable against that id's own unit and magnitude. A label attached to a free string is checkable against nothing. This is the whole reason `labels` cites ids |

**What it costs, stated rather than implied.** The candidate table is extra prefill on call 1, and prefill runs at 9.84 tok/s on this runner (measured 2026-08-23, AMD EPYC 9V74, 4 vCPU). It is partly repaid, because labelling by id decodes fewer output tokens than re-typing every surface, and output is the expensive direction at 6.01 tok/s. The net is arithmetic over the bounded table size and is derived with the output budget in section 11.3, in the same commit. It is not guessed here.

### 10.1b Step 1 drawn - what code does, and what the model does

Section 1a draws the whole pipeline. This is its stage 1 zoomed in: the proposal draws ARTICLE -> TRUSTED ELEMENTS as a single edge labelled "deterministic extraction + model labelling", and this is that edge opened up. It is the drawing plan-doc G carries into `docs/architecture/extraction/` when the plan is decomposed.

Plain ASCII, for the reason given in section 1a.

```
                     +---------------------------------+
                     |             ARTICLE             |
                     |  sanitized text + title         |
                     |  text_hash over the normalised  |
                     |  bytes that every span indexes  |
                     +----------------+----------------+
                                      |
                                      v
   +======================================================================+
   |  CANDIDATE PASS - CODE READS FIRST  no model, no network, no tokens  |
   +======================================================================+
   |  FINDS   every quantity the number pattern matches, and emits        |
   |          element_id  kind=quantity  surface  span_start  span_end    |
   |          value  unit  sentence_index  extractor="regex"              |
   |                                                                      |
   |  MISSES  by design. Each was a correct call for picking a few bars   |
   |          and is the wrong call for a candidate set:                  |
   |            - a figure repeated across two periods    (dedup, C14)    |
   |            - a bare four-digit year                                  |
   |            - any magnitude <= 2 carrying no unit                     |
   |            - a number whose following word is on the stop-list       |
   |            - everything past the 16th figure                         |
   |            - ANY date. No date extractor exists yet   (C15)          |
   +===================================+==================================+
                                       |
                      candidates[], indexed by element_id
                                       |
                                       v
   +======================================================================+
   |  CALL 1 - MODEL READS THE SAME ARTICLE                               |
   |  in: system + title + <UNTRUSTED>article</UNTRUSTED> + candidates    |
   +======================================================================+
   |  CANNOT EMIT a span, a character offset, a value, a unit or a count. |
   |  No field of the schema accepts one, so the grammar refuses it at    |
   |  decode time and nothing downstream has to check for it. (Rule #11)  |
   +===================================+==================================+
                                       |
                                       v
   +======================================================================+
   |  ANCHORING - CODE ADJUDICATES           a DIFFERENT rule per shape   |
   +==================+===================================================+
   | labels[]         | Cites element_id and nothing else. An unknown id  |
   |   element_id     | is dropped. No numeric field exists here at all.  |
   |   measure entity |                                                   |
   |   dimension time | -> TIER 2 on an element the candidate pass minted |
   |   salience       |                                                   |
   |   attribution    |                                                   |
   |   hedge          |                                                   |
   +------------------+---------------------------------------------------+
   | proposed[]       | The escape hatch for a figure code missed.        |
   |   sentence_index | Search ONLY the named sentence. Exactly one hit,  |
   |   surface        | or dropped. Re-parse value and unit from the      |
   |                  | ARTICLE'S OWN BYTES with the same number pattern, |
   |                  | never from the reply. Capped per article.         |
   |                  | A spelled-out number and a relative change        |
   |                  | ("doubled") stay refused - nothing to parse.      |
   |                  |                                                   |
   |                  | -> TIER 1 quantity, extractor="model_proposed"    |
   +------------------+---------------------------------------------------+
   | entities[]       | `name` is TIER 2 - a grouping key for the alias   |
   | places[]         | ledger, and it is NEVER drawn on a page.          |
   |   name           | Each mention.surface must occur exactly once      |
   |   entity_type    | inside its OWN named sentence, and that           |
   |   geo_hint       | occurrence is the span. Zero surviving mentions   |
   |   salience       | drops the element. The drawn label is the         |
   |   mentions[]     | longest surviving mention, never `name`.          |
   |     sentence_idx |                                                   |
   |     surface      | -> TIER 1 mentions + TIER 2 name                  |
   +------------------+---------------------------------------------------+
   | quotes[]         | INDICES ONLY. No text crosses from the reply.     |
   | claims[]         | Code slices the article's bytes between them.     |
   |   sentence_start | Exact search over a long string is refused: it    |
   |   sentence_end   | rejects a real quote over one changed word, and   |
   |   speaker_mention| it does so silently.                              |
   |   attribution    |                                                   |
   |   hedge          | -> TIER 1 span + TIER 2 attribution and hedge     |
   +------------------+---------------------------------------------------+
   | events[]         | Every actor and object must resolve to a          |
   | relations[]      | surviving entity element, or the row is dropped.  |
   |                  | An edge carries sentence_index with no exception  |
   |                  | (row 47): an unanchored arrow is a causal claim   |
   |                  | the article did not make.                         |
   +==================+===================================================+
                                       |
                        every survivor carries a span
                                       |
                                       v
                     +---------------------------------+
                     |        TRUSTED ELEMENTS         |
                     |        (source of truth)        |
                     +---------------------------------+
                     | TIER 1 - byte-exact, and never  |
                     |   model-authored                |
                     |   element_id  kind  surface     |
                     |   span_start  span_end          |
                     |   span_excerpt  value  unit     |
                     |   sentence_index  extractor     |
                     +---------------------------------+
                     | TIER 2 - model-assigned,        |
                     |   span-anchored, validated      |
                     |   entity  time  measure         |
                     |   measure_canonical  dimension  |
                     |   salience  attribution  hedge  |
                     |   label_source  ledger_version  |
                     +----------------+----------------+
                                      |
                    +-----------------+-----------------+
                    |                                   |
                    v                                   v
          to the SEMANTIC MODEL,              to ARTICLE POTENTIAL
          call 2 - section 10.1               deterministic - section 12.6 G5
```

**Three invariants the drawing encodes. A plan-doc may not relax any of them.**

1. **A Tier 1 field is never model-authored.** Each one comes from the candidate pass, or from code slicing bytes the model only pointed at. `extractor` records which, on every element, so a later run can measure the two paths apart.
2. **A Tier 2 field is never drawn without its Tier 1 anchor.** `name` groups; the mention draws. This is the rule that makes an alias ledger safe (row 7) and it is the one an implementer is most likely to lose, because rendering `name` is easier and looks tidier.
3. **A rejection is per element, never per article.** A mention that will not anchor drops one element and leaves the article's other elements standing - section 1a, degrade rather than fail. An article that ends with zero elements is `narrative`, and row 57 makes it record why.

### 10.2 What "call 2 appends to call 1's message array" means

The tokens the server sees on call 2 are, in order:

```
[chat template header]                    <- identical
[system: extraction + semantic rules]     <- identical    | REUSED FROM CACHE
[user: title + article + candidate table] <- identical    | (the expensive part)
[assistant: call-1 JSON]                  <- NEW, but short
[user: summarise + plan]                  <- NEW, short
```

llama-server reuses the **longest common prefix** of the tokenised prompt. Because the system turn and the article are byte-identical and come first, the article is prefilled **once**. Only the call-1 output and the second instruction block are new. That is the entire mechanism.

If instead call 2 carried a *different* system prompt, the common prefix would be the template header alone and the whole article would re-prefill - the "case (b)" that costs roughly double.

Two conditions make the reuse real:
- `n_parallel` is 1, so there is one cache slot. The two calls must be **adjacent for one item**. Running all call-1s then all call-2s evicts the prefix every time.
- The assertion is `cached_tokens` on call 2, not a timing ratio.

### 10.3 Why this ordering is also better on quality

- The planner sees the **article**, not a compression of it. No fact reaches the planner only if the summariser happened to keep it.
- The summariser sees the **element table** it just produced, so key points can be grounded in extracted facts rather than re-derived from prose.
- Entity and event extraction is stored for reuse regardless of whether a visual is drawn.
- Field order is decode order: the model commits to what it found before it decides what to say about it.

The cost, stated: the summariser's input changes, so `summary_faithfulness` is not comparable across the cutover. The owner accepts that explicitly - the current summaries are unsatisfactory and comparability with them is not worth protecting. The discontinuity is marked in the metric series (P.6.4.2 step 5).

### 10.3a What the planner's source actually is

Two things are true at once and they are easy to run together. This section exists so nobody has to guess which.

**The planner's source is the article and the element table. It is not the summary.** Call 2 carries the full article in the same user turn call 1 read, plus the anchored element table, and `element_ids` may cite only an anchored element. Nothing the summary says can reach a visual unless it is already an element. **The summary can neither introduce material to the plan nor hide material from it.**

**And the summary is nevertheless in the planner's context**, because decoding is autoregressive and `summary` decodes before `visual` inside call 2's object. E5 requires that order - it is what makes the summary recoverable when the output budget cuts the reply.

So the summary **conditions** the plan without **sourcing** it, and that is a different thing from what section 10 refused:

| | Refused (P.D1's original ordering) | Ships |
|---|---|---|
| What the planner reads | the summary, and nothing else | the article, the element table, **and** the summary |
| Can the planner see a fact the summary dropped? | No | Yes. The article is right there |
| Can a sentence in the summary put a number on a chart? | Yes, and that is the defect that produced this work | No. Only an anchored `element_id` can |

**The cost, named rather than implied.** With prose decoded first, a plan can drift toward illustrating the sentences rather than the elements. That is a row-12-shaped risk and it is real. Two things bound it: `element_ids` makes the drift unable to invent anything, and `information_delta` measures it directly - it counts plan elements the summary does not already state (section 12.4 Q3), so a plan that only illustrates the prose scores zero there by construction. **If `information_delta` collapses after the cutover, this ordering is the first suspect.**

### 10.4 Summary quality is a named work item

The owner's assessment: summaries are extractive at times, do not focus on key ideas, and pad. `finetune.student` is `route` and `finetune.teacher` is `summarize` today, which is a distillation setup for the model being retired. **That configuration is dead once O17 lands and must be re-pointed**, and fine-tuning the summariser becomes a real candidate. Recorded here so it is not lost; it is a separate plan-doc.

### 10.5 Why key points restate the summary, and the fix

The owner asked whether the 7-in-8 restatement rate is a prompt defect or a model-capability defect. **It is a prompt defect, and the prior is strongly against a model swap.**

Three mechanical reasons the current prompt cannot work:

1. **Decode order.** `SummaryDraft` decodes `title`, then `summary`, then `key_points` ([backend/idhazh/summarize.py](backend/idhazh/summarize.py#L100)). The model is asked to write something *unlike* the text it has just written, which is the least likely continuation.
2. **The rule is a complaint, not a constraint.** "A key point that restates the summary is a wasted line" gives the model no definition of "restates" that it can compute.
3. **Nothing measures it.** `METRICS_VERSION` 3 names no key-point redundancy metric, so the defect has run unseen for as long as the field has existed.

And one structural cause that is nobody's fault: **`key_points_max` is 5 for every band**, and it sits on `SummarizeConfig` rather than `SummaryBand`. Asking for five key points on top of a 40-word summary of a 60-word post is asking for facts that are not in the article. **Redundancy is structurally guaranteed at the shortest band.**

The fix, in cost order:

| # | Change | Cost |
|---|---|---|
| 1 | Decode key points **before** the summary, so facts are found first and prose connects them. Under the two-call design they become "state the highest-salience elements, one sentence each, with attribution" | Field reorder |
| 2 | Make the anti-restatement rule a deterministic check in `to_summary` that **drops the offending key point, not the item** - the `verbatim_run` pattern this codebase already uses, with a ceiling in `config/` | One function |
| 3 | Move `key_points_max` onto `SummaryBand`, so the shortest band gets 0-1 and the longest gets 5 | One contract field |
| 4 | One worked good-or-bad pair in the system prompt - about 30 tokens, prefix-cached across the shard, so free after the first item | 30 tokens |

**The instrument**: new-fact rate, the share of key points stating a fact the summary does not contain. Baseline is **11 of 89, 12.4 percent**, reported per band. The two-call design unlocks a strictly better version - **element-id disjointness**: a key point whose span-anchored element ids are all already cited by the summary is a restatement by construction, with no lexical false positives.

**The standing trap, and it would quietly destroy the measurement: never use new-fact rate to select.** Best-of-N against it produces key points optimised for lexical difference from the summary, which is the Goodhart form of this exact metric, and the alarm then stops being able to detect the thing it was built for.

On swapping the model: re-run the same twenty items on the same weights through the fixed prompt first. If the rate does not move, it becomes a model question. **Fine-tuning before the prompt fix trains a model to reproduce a prompt defect.**

### 10.6 What else call 1 extracts

The currency, measured 2026-08-23 on AMD EPYC 9V74, 4 vCPU: **100 extra output tokens in call 1 costs 26.8 s per item** - 16.6 s to write at 6.01 tok/s decode plus 10.2 s to read back on call 2 at 9.84 tok/s prefill. At 20 items that is **8.9 minutes of shard wall clock per 100 tokens.** The binding constraint is output tokens, not context.

| Signal | What it buys | Tokens | Shard cost | Verdict |
|---|---|---|---|---|
| **Salience rank per element** | Decides which mark lands first (row 30), which facts become key points, and search ranking | ~40 | 3.6 min | **TAKE.** Decoded *after* the element list, so it is an observation and not a prior |
| **Attribution type per claim** (self-reported / named / anonymous / unattributed) | Makes the prompt's attribution rule mechanical instead of aspirational | ~15 | 1.3 min | **TAKE.** Cheapest quality win available |
| **Hedge marker per claim** | Closes the loop with the hedge lexicon already in `backend/idhazh/evals/metrics.py` | ~15 | 1.3 min | **TAKE.** Same lexicon, or the two decouple |
| **Topical keyphrases**, 5-8, verbatim | The only search surface that needs no embedding model. Also an archive facet | ~50 | 4.5 min | **TAKE.** Verbatim and span-anchored, or not at all |
| **Lede and quote sentence indices** | Feeds `quotecard` (row 39) and the existing `lead_coverage` metric | ~20 | 1.8 min | **TAKE** indices only |
| Numeric-unit normalisation | A converted figure the source never stated | 0 | - | **NO.** Code does arithmetic; `measure_canonical` sits beside the surface unit |
| Coreference chains | Within-article entity merging | ~40 | 3.6 min | **NO.** Exact and prefix matching over spans code already holds does most of it, and the model's version cannot be span-validated (Rule #8) |
| Question-answer pairs | Genuinely the strongest retrieval surface | ~105 | 9.3 min | **NO, not in call 1.** The only candidate that asks the model to **author** rather than to find. If it ships it is a third call on a subset |
| Sentiment or tone | Nothing this project consumes | ~10 | 0.9 min | **NO.** A tone label invites a tinted card, which is an editorial judgement the digest does not make |
| Embedding vectors | Vectors for search | n/a | - | **NO.** Floats through a JSON decoder are hallucinated floats. A small sentence encoder over the committed summaries at build time is the honest route, and it costs the model nothing |

Accepted total is about **140 tokens, 12.5 minutes of shard wall clock** at 20 items.

Three things dilute the primary jobs, named so they can be watched for: **mixing an author-task into a find-task** teaches the model that inventing is in scope for call 1, and the span validator then starts rejecting real elements for reasons nobody can trace; **any field decoded before the thing it describes** becomes a rationalisation, which this codebase has already measured once (row 12); and **any field with no named consumer** costs 26.8 s per 100 tokens per item, forever.

---

## 11. Context, tokens and degradation

### 11.0 Model neutrality - what is pinned to a model, and what is not

The proposal's first rule is that model neutrality is mandatory. This document has to be read against that rule in two directions, because it obeys the rule in one and would break it in the other if the distinction were left unwritten.

**The pipeline is neutral and stays neutral.** The weights are named in exactly one place - `models.<role>` in `config/idhazh.json` - and every stage downstream reads `model.id` off the config it was handed. No module name, class name, contract field, telemetry value, prompt filename, config key or schema stem carries a parameter count, a vendor or a revision. `visual_planner.py` is named for what it does, which is the whole of O2. Retiring the 4B (O17) is a config edit and the removal of a role, not a rewrite. Nothing in section 15's thirteen plan-docs may put a model's identity back into a name (section 15.4a).

**The runtime settings are not neutral, and pretending otherwise is the hazard.** Every number in section 11.2 - 16384, flash attention on, ubatch 512, parallel 1, the KV table, the 1.61 GiB margin - was derived from one model's architecture on one runner. The architecture is the load-bearing half: the model card records 32 layers of which only 8 carry a growing KV cache, 4 KV heads and a head dimension of 256. A dense model of similar size at the same window costs roughly four times the KV per token, so 16384 would not fit the measured margin. **The window is a measurement about a named config entry, not a property of the design**, and the same is true of every other flag in 11.2a. They are tuned against the entry in play from its model card, from published guidance and from what this runner measured - not read off a default.

**And the structure hides that today.** `ModelsConfig` carries `summarize`, `route` and **one shared** `inference: InferenceConfig` ([backend/idhazh/contracts/app_config.py](backend/idhazh/contracts/app_config.py#L536)). Change `models.summarize` and the new weights silently inherit the previous model's window, cache types, batch shape and attention flags. Nothing raises. The run comes back slower, or out of memory, or with different words, and the config diff shows one repository string.

Three consequences bind every plan-doc in section 15:

1. **Any llama-server setting quoted anywhere carries the model entry it was derived against, the runner and the date.** That is Rule #10 applied to a setting rather than to a throughput figure. A bare `n_ctx: 16384` in a plan-doc is an unmeasured number justifying a design.
2. **A model swap re-derives the whole `InferenceConfig` block, not only `n_ctx`.** `-fa`, `-ctk`, `-ctv`, `--ubatch-size`, `--threads-batch` and `--jinja` are each ruled on in 11.2a for the entry in play today and for no other entry.
3. **The silent inheritance gets closed.** Whether the block moves onto `ModelRef` so a swap cannot inherit, or stays shared behind a qualification gate that refuses a pairing nothing has measured, is plan-doc H's call. What is not open is leaving it silent.

### 11.1 `--no-context-shift`

The server is started with `--no-context-shift` ([backend/idhazh/llm/server.py](backend/idhazh/llm/server.py#L123)). The reason is written next to it:

> Without this the server silently drops the middle of an oversized prompt and answers about a document it no longer holds, which scores as a hallucination and names the wrong cause. Refusing is the signal.

So an oversized prompt returns an error instead of a plausible answer about a document that was never read. Keep it.

### 11.2 Raising `n_ctx` - settled

**Ruling: `n_ctx` goes to 16384 with `flash_attention` on, in one change. 32768 and above are refused.**

Every number in this subsection and in 11.2a is derived against the entry `models.summarize` names today, on a stock `ubuntu-latest`. Section 11.0 governs what happens to all of them when that entry changes.

#### The architecture, from the model card fetched 2026-09-02

These are model-card claims, not our measurements, and they are labelled as such wherever they are used.

| Property | Value |
|---|---|
| Native context | **262,144 tokens**, extensible to 1,010,000 with YaRN |
| Layers | 32, hidden dimension 4096 |
| Layout | `8 x ( 3 x (Gated DeltaNet -> FFN) -> 1 x (Gated Attention -> FFN) )` |
| **Consequence** | **Only 8 of 32 layers carry a growing KV cache.** The other 24 are linear-attention layers with a fixed-size recurrent state per sequence |
| Gated Attention | 16 Q heads, **4 KV heads**, head dimension 256 |
| Sampling the card recommends, non-thinking | temperature 0.7, top_p 0.8, top_k 20. **We use 0.0 / 1.0 / seed 0** - determinism wins, deliberately |
| Thinking | On by default. `enable_thinking: false` is a chat-template variable |

The expert's `--ctx-size 131072` is defensible on the card and wrong on this runner. It is also internally inconsistent: the same proposal narrows `--ubatch-size` to 128, which is only needed to pay for a huge window that this pipeline cannot fill.

#### KV cache arithmetic

Per full-attention layer per token: `4 KV heads x 256 head dim x 2 (K and V) = 2,048 elements`. Across 8 layers:

| Cache type | Bytes per token | 8,192 | 16,384 | 32,768 | 131,072 |
|---|---|---|---|---|---|
| f16 | 32.0 KiB | 0.25 GiB | 0.50 GiB | 1.00 GiB | 4.00 GiB |
| q8_0 | 17.0 KiB | 0.13 GiB | 0.27 GiB | 0.53 GiB | 2.13 GiB |

The hybrid layout is why this is affordable: a dense 32-layer model of this size would cost roughly four times as much per token.

#### Against the measured baseline

Measured peak resident memory is **13.29 GiB worst over 72 shards**, on a 14.90 GiB usable runner - **1.61 GiB free.** Arithmetic accounts for only about 5.6 GiB of that 13.29, so **no pure-arithmetic extrapolation is trustworthy on its own**; only the delta is, because just two terms move with `n_ctx` - the KV cache, and the attention score buffer that flash attention removes.

| n_ctx | KV | flash-attn | Projected worst peak | Free | Verdict |
|---|---|---|---|---|---|
| 8,192 | f16 | off | 13.29 GiB (measured) | 1.61 GiB | today |
| **16,384** | **f16** | **on** | **about 13.29 GiB** | **about 1.61 GiB** | **ship** |
| 16,384 | f16 | off | about 13.54 GiB | 1.36 GiB | works, and pays a bill it need not |
| 32,768 | f16 | on | about 13.79 GiB | 0.86 GiB | **refused** |
| 131,072 | f16 | on | about 16.8 GiB | negative | dead |

**Flash attention on pays for the entire doubling of the window.** It removes a term that scales as `ubatch x n_ctx`, which is exactly what the larger KV costs.

#### Why 32768 is refused even though it fits

It buys nothing. The largest prompt ever seen is 5,516 tokens and `extract.truncation_cap_tokens` is 5,000, so a 32K window is more than five times what this pipeline can put into it - and it would spend 1 GiB of a 1.61 GiB margin doing so. Rule #2: the budget is the platform, not a preference.

And 131,072 fails on wall clock before it fails on memory. Filling it once at the measured prefill rate of 9.84 tok/s takes **13,320 seconds, or 222 minutes for a single article**, against a 150-minute shard timeout. It can never be filled.

#### Why 16384 is the right number

The two-call worst case is about 8,580 tokens: 880 system + 5,000 article cap + about 1,200 call-1 output + about 300 call-2 instructions + about 1,200 call-2 output. That is **105 percent of 8192** - the design does not fit in today's window. 16384 gives 1.9x headroom over that worst case and costs nothing once flash attention is on.

The candidate pass's table is not in that 8,580 and must be added to it before the number is final. It is bounded by construction - `numeric_facts()` takes a `limit`, 16 today - so the addition is arithmetic over that bound, not an estimate. It is derived with the output budget in 11.3, in the same commit. The headroom is 1.9x, so a bounded table does not put 16384 at risk; it does move the worst case, and a worst case that moves without being recomputed is how a window stops fitting.

### 11.2a The full settings comparison

| Setting | Today | Expert proposes | Andre's verdict | Why |
|---|---|---|---|---|
| `--ctx-size` | 8192 | 131072 | **16384** | Two-call worst case is 105 percent of today's window. 131072 takes 222 minutes to fill once |
| `--flash-attn` | unset | `on` | **Take it, own commit** | Lowest-cost item on the list and the precondition for quantised V-cache. Assert `flash_attn = 1` from the startup line rather than trusting the flag took |
| `--jinja` | absent | present | **Highest-value item. Needs a new digested config field** | Without it the server may apply its own template instead of the model's, and `enable_thinking: false` is a variable only the model's template consumes - so the thinking-off control may never have reached it. The fingerprint cannot see this today |
| `--cache-type-k` | f16 | `q8_0` | **Measure first. Not in the same commit as `n_ctx`** | Halves KV bytes but changes how partial sums accumulate, so it changes the words. It is folded into the fingerprint for that reason. The fallback, not a default |
| `--cache-type-v` | f16 | `q8_0` | **Measure first, coupled to `-fa`** | llama.cpp gates V-cache quantisation on flash attention. Setting it without `-fa` errors or is silently ignored depending on build |
| `--ubatch-size` | 512 | 128 | **Reject. Keep 512** | Exists only to pay for the 131072 proposal. Prefill is 63 percent of model time and a 512-column matrix already saturates 4 threads |
| `--threads-batch` | unset | 4 | **Reject as a config edit** | llama.cpp falls back to `--threads` when absent, so on 4 vCPU this spells existing behaviour - but writing `4` where `null` sits **invalidates every prior work identity for zero change in output** |
| `--batch-size` | 512 | 512 | No-op | Already 512 |
| `--threads` | 4 | 4 | No-op | Already 4, and there are 4 vCPU |
| `--parallel` | 1 | 1 | **No-op, and load-bearing** | One slot is what makes call 2 reuse call 1's prefix. Two slots evict it silently. Measured 2026-08-25: two sequences bought 1.055x aggregate decode - 5.5 percent faster where the gate wanted 40 percent |

**Determinism is not at risk**: nothing above touches `temperature` 0.0, `top_p` 1.0 or `seed` 0. What five of them break is **comparability across the change**, because flash attention, both cache types, ubatch and threads-batch alter float accumulation order. `n_ctx` alone invalidates every prior work identity, so absorb it in the same commit as the two-call cutover, which section 10.3 already accepts as a discontinuity.

### 11.3 The output budget

`visuals.max_output_tokens` is **400** today. A reply that hits it becomes `none` with "the routing reply was cut off by the output budget" ([backend/idhazh/route.py](backend/idhazh/route.py#L520)) - and the owner has already observed the router cutting off in practice.

Under strict JSON-schema decoding a reply that hits `max_tokens` fails **strict validation of the whole object**, because the outer object never closes. That is not the same as the reply being lost, and an earlier version of this section said it was. The bytes come back on a normal HTTP 200, `parse_completion` puts the partial decode in `Completion.content` ([backend/idhazh/llm/server.py](backend/idhazh/llm/server.py#L195)), and `to_summary` then fails the item on `hit_the_budget` **without ever reading them** ([backend/idhazh/summarize.py](backend/idhazh/summarize.py#L385)). A grammar-constrained decode closes each sub-object in schema property order, so a `summary` that finished before the cut is closed, balanced, and independently parseable with `json.JSONDecoder().raw_decode`. E5 turns that into the degradation rule. The derivation below still binds: recovery is the seatbelt, the budget is the brake. The two-call design puts elements, entities, events, relations, the summary and the plan through that one ceiling.

**The budget is not picked. It is derived** from the contract's own bounds: every array gets `maxItems`, every string gets `maxLength`, and the worst-case reply length is then arithmetic. It is re-derived whenever a bound changes, and the derivation is committed beside the number. Roughly 1,200 tokens is the order of magnitude for call 2 given 16-24 labelled elements plus the plan, but the arithmetic is what sets it, not that figure.

### 11.4 Degrading on `context_exceeded`

Today `FailureCode.CONTEXT_EXCEEDED` exists and is recorded, and the item gets no summary at all. Under the two-call design the longest articles - which are also the most chartable - are exactly the ones that would fail.

**Ruling: chunked degradation, and the constants already exist.** `evaluation.chunk_words` (900) and `chunk_overlap_words` (150) are used by the scorer. The same shape applies: when the article does not fit, read it in overlapping chunks, extract elements per chunk, merge on span, and plan over the merged table. Element extraction is naturally chunkable because an element is local to its span. The summary over a chunked read is marked as such, and the item carries the existing source-limit sentence.

This is Andre's ruling in the one case the owner asked about, and it is strictly better than the current behaviour, which is to publish nothing.

---

## 12. Proposal coverage matrix

Every numbered item in the proposal, with its disposition here. **This is the section to audit.**

### 12.1 Owner decisions P.D1 - P.D15

| P.D | Subject | Disposition |
|---|---|---|
| D1 | Two calls, one model | Accepted, **ordering reversed** - section 10. Still exactly two model calls: the candidate pass before them is deterministic code and costs no inference (O37, O43) |
| D2 | Full vocabulary declared, templates in waves | Accepted; wave order follows observed frequency (row 48). **Full means full** - section 12.8 X1 |
| D3 | Open element labels | Accepted (row 6) |
| D4 | Per-type encoding roles | Accepted (row 15, flat map with all keys required) |
| D5 | No invented metric weights | Accepted; weights learned (row 67) |
| D6 | Downgrade ladder | Accepted (row 50) |
| D7 | Numerals in prose enforced | Accepted; allow-list minimal and versioned, `allowlist_hits` reported |
| D8 | Feedback captured out-of-band | Accepted, amended by O12 |
| D9 | Paired comparisons across config versions | Accepted; visual-vs-no-visual is the standing arm, config A/B rides on top (Editor, P.L16) |
| D10 | `none` arm is a config ratio | Accepted with a floor above zero and a frozen window (Editor, P.L12) |
| D11 | Diagram path ships | Accepted (row 46) |
| D12 | Rejected plans labelled | Accepted (row 68) |
| D13 | Extraction is measured | Accepted (Carmack, P.L29 - zero runner cost) |
| D14 | Trusted Element, not Trusted Fact | Accepted, all six kinds (row 5) |
| D15 | Principle amended to "all semantic analysis" | Accepted |

### 12.2 Litigation rows P.L1 - P.L35

| P.L | Verdict | Owner | Where |
|---|---|---|---|
| L1 | AMEND - two calls, ordering reversed | Andre / Owner | 10.1 |
| L2 | **AMEND, disambiguated 2026-09-03.** The vocabulary **lives in `config/`** rather than in a Python literal (Rule #6). It is still the **full** vocabulary - config locates the list, it does not shorten it. `wasted_decode_rate` reported | Carmack, Fowler | row 48, section 12.8 X1 |
| L3 | AMEND - `pie` ships gated; stacked bar is its downgrade | Jony / Owner | row 43 |
| L4 | ACCEPT - open vocabulary with canonicalisation | Andre | row 6 |
| L5 | ACCEPT - equal weights, then learned | Andre | row 67 |
| L6 | ACCEPT - two tiers, structurally nested | Fowler | 4.A |
| L7 | ACCEPT - downgrade ladder behind the flag | Owner | row 50 |
| L8 | AMEND - D7 on visual-owned strings; `key_points` included since call 2 now sees elements | Andre / Owner | 10.3 |
| L9 | AMEND - diagram ships behind the `processual` classifier | Editor | row 46 |
| L10 | **MIS-MAPPED, corrected in 12.9 G13.** P.L10 is "integrity invariant vs KPI" - a build-failing invariant on **value provenance**, with `trusted_data_ratio` reported separately. Row 2 rules on **span drift**, which is P.R5, and 12.3 closes R5 with row 2 correctly. The provenance invariant's enforcement level is unruled | Fowler | 12.9 G13 |
| L11 | AMEND - observe only; single-shape day is a defect | Jony, Susan | row 49 |
| L12 | AMEND - ratio with a floor, frozen in a window | Editor | 12.1 D10 |
| L13 | ACCEPT - both modes behind `REVIEW_MODE`, `mode` field mandatory | Andre | P.6.3.6 |
| L14 | AMEND - budget is per shard, not per article | Carmack | 8.2, 8.3 |
| L15 | AMEND - versions are **date-stamps**, never integers (section 11) | Fowler | 13 M7 |
| L16 | AMEND - visual-vs-no-visual is the standing arm | Editor | 12.1 D9 |
| L17 | ACCEPT - thresholds from observed percentiles | Carmack | 13 M5 |
| L18 | **CLOSED - d3** | Jony / Owner O5 | section 7 |
| L19 | ACCEPT - span-anchored edges, no exception | Editor | row 47 |
| L20 | AMEND - bound by legibility, not a node count | Susan, Carmack | row 26 |
| L21 | **CLOSED - progressive enhancement** | Jony, Susan, Carmack | row 22 |
| L22 | ACCEPT - derived values built with the closed allow-list | Owner O16 | row 45 |
| L23 | AMEND - `confidence` moves after `type` or is deleted | Andre | row 18 |
| L24 | ACCEPT - principle amended | Andre | 12.1 D15 |
| L25 | ACCEPT - wire in the existing scorer | Fowler, Andre | row 64 |
| L26 | ACCEPT - offline paired evaluation | Andre | row 66 |
| L27 | AMEND - assert `cached_tokens`, not a ratio | Carmack, Andre | row 11 |
| L28 | **RESOLVED by Editor** - the three-part gate | Editor | row 40 |
| L29 | ACCEPT - extraction is measured | Carmack | 12.1 D13 |
| L30 | ACCEPT - rejected plans labelled; `review/` outside `frontend/public/` | Fowler, Andre | row 68 |
| L31 | ACCEPT - all six kinds | Fowler / Owner | row 5 |
| L32 | AMEND - verbatim only, capped at `max_verbatim_words` | Andre / Owner O13 | row 39 |
| L33 | **OVERRULED** - `keyfacts` ships with its kill criterion | Owner O16 | row 42 |
| L34 | ACCEPT - timed comprehension arm ships | Owner O16 | row 67 |
| L35 | ACCEPT - every rate per potential class | Andre, Editor | row 56 |

### 12.3 Risks P.R1 - P.R20

| P.R | Disposition |
|---|---|
| R1 | Rejection rate and `planned_type_entropy` alarmed as a **pair**, read per `plan_version` not per day - decoding is `temperature 0.0, seed 0`, so entropy cannot drift daily (Andre) |
| R2 | Closed by D13; extraction metrics ship |
| R3 | Closed by row 68 |
| R4 | Closed by row 8 |
| R5 | Closed by row 2 |
| R6 | Managed by `ledger_version` stamping (row 7) |
| R7 | **Reframed.** Andre's structural defence assumed summary-first. Under section 10's ordering the summariser sees the element table, so stripping numbers from prose does not raise `information_delta` - it is measured against elements, not against the summary's own scarcity. `summary_informativeness` still ships as the counterweight |
| R8 | Closed - floors from depth-0 published visuals only |
| R9 | Closed by row 17 |
| R10 | Disclosed - edges are Tier 2 with a span; the decision procedure is published and edges are sampled for audit |
| R11 | Closed - alt text generated deterministically by the compiler, inside D7. **12.8 X6 makes that binding**: section 1a's plan box and section 10.1's call-2 shape had the model emitting it, and they lose the field |
| R12 | Closed by row 55 |
| R13 | Closed - `queue_position` on every label |
| R14 | Closed by row 65 |
| R15 | `evaluation_cost` reported separately **and** a sample-rate cap in config enforced inside the shard budget (Carmack) |
| R16 | Closed - `none_arm_ratio` set from a reviewer-hours budget, recorded on the queue |
| R17 | Closed by rows 24 and 35 |
| R18 | Closed by row 49 plus Editor's rule: a running story's visual repeats only when its numbers moved |
| R19 | Closed by row 56 |
| R20 | Closed by row 40 |

### 12.4 Open questions P.Q1 - P.Q10

| P.Q | Answer |
|---|---|
| Q1 | Classifier thresholds live in `config/idhazh.json` behind a Pydantic model, stamped by that file's existing top-level `version`. No bespoke version field, no named owner (Fowler). **This refuses a second source of truth, not a telemetry column** - see 12.8 X5, which reconciles it with the P.6.1 event |
| Q2 | Extend `visuals.min_chart_points` into a map keyed by the type enum. `table` does **not** bypass it - a one-row table is a sentence (Fowler) |
| Q3 | `information_delta` is deterministic: plan `element_ids` whose `raw` string does not appear in the summary, over all plan `element_ids`. Relationship extraction from prose would need a model, which would make the metric share the failure modes of the thing it measures (Andre) |
| Q4 | Normalised types with the surface form preserved. `time` carries `normalised` plus `granularity`; the Tier 1 guarantee is the verbatim surface form |
| Q5 | Sampling rate, reviewer count and agreement target are set from a reviewer-hours budget; `inter_reviewer_agreement` is published beside every keep rate or the keep rate is not quotable |
| Q6 | The edge decision procedure is published, edges are sampled for human audit, and edge anchoring is never described as deterministic |
| Q7 | The canary mechanism extends to element-table fixtures. Zero runner cost; the only condition is that the fixture set stays small enough that six checkouts do not pay for it (Carmack, Fowler) |
| Q8 | **Yes.** The eval ledger, `ConfidenceBand`, `BandReason`, `verbatim_run` and the faithfulness extra all exist. Wire in, build nothing (row 64) |
| Q9 | One rule: **a ledger folds, an asset deletes, a lookup deletes.** Section 9.2 |
| Q10 | Alias-ledger additions are reviewed in the PR that adds them; the model never writes to it unreviewed (row 7) |

### 12.5 Proposal sections

| P section | Disposition |
|---|---|
| *How to read this*, rule 1 - model neutrality | Accepted and extended. The pipeline stays neutral; **section 11.0** records that `InferenceConfig` is not, names the structural hole that hides it - one shared `inference` block, so a swap inherits silently - and binds every quoted setting to the model entry it was derived against (O38) |
| *How to read this*, rule 2 - canonical vocabulary verbatim | Accepted for **identifiers**, declined for prose, and the split is written down in **section 15.4a** (O39). Raised by review: 15.4 ruled on hot files and never on hot names |
| 1.1 Governing principle + ownership boundary | Accepted, with D15's amendment |
| 1.2 End-to-end flow | Accepted, **with the call ordering reversed** - section 10 |
| 1.3 What changes | Accepted; the "today" column corrected by section 2 |
| 1.4 Non-goals | **Six accepted, one amended - not seven accepted.** "No more than ~10 chart types" is replaced by rules-per-type, as the proposal's own parenthetical says. **Non-goal 5, "using another LLM as the judge of visual quality", is amended by O12 and E1**, and a non-goal crossed without being named is a boundary that stops meaning anything. The amendment is narrow: a machine label is permitted for **visual** labels only, behind four guardrails - `label_source` and `model_id` stamped, a separate ledger, never pooled with human rows, and it never selects what publishes. Summary faithfulness labelling stays human-only. Section 16.2's prompt loop does **not** cross this non-goal: it judges a prompt at development time, never published output, and 16.2 argues that on its own terms |
| 1.5 Compliance audit | **Re-run 2026-09-04 - section 12.10.** This row said "deviations A and B carried openly", which was true when it was written and stopped being true further down this same table. Deviation A stands unchanged. Deviation B's cause is closed by rows 22 and 31, and the clause is now **conditionally** compliant on a control nothing has tested. One candidate new deviation, from O12, is scored and disclosed there rather than assumed away |
| 2.1 Trusted Element | All six kinds (row 5), spans by code (row 4) |
| 2.2 Open label vocabulary | Accepted with canonicalisation and the alias ledger (rows 6, 7, 8) |
| 2.3 Derived values | Built (row 45) |
| 2.4 Article Visual Potential | Built, plus a quote-led class (row 58) and a `narrative` reason (row 57). **Its seven signals were never dispositioned, and they are not deterministic** - section 12.11 G16 |
| 3.1 Plan contract | Accepted; `confidence` repositioned (row 18) |
| 3.2 Encoding roles | Accepted as a flat map with all keys required (row 15) |
| 3.3 What planning decides | Accepted |
| 3.4.1 Chart vocabulary | All 12 types ship (rows 43, 44, 45). **Two of its gates were not carried**: `stacked_bar`'s exhaustiveness check and the `pie`/`bubble` telemetry flag - 12.12 G26 and G27 |
| 3.4.2 Diagram vocabulary | Ships (rows 46, 47); `flow` first, then `hierarchy`, `state`, `mindmap` each with their own validator rules. **The cycle predicate was not carried** - 12.12 G24 |
| 3.4.3 Infographic vocabulary | All five ship (rows 38-42) |
| 3.5 Worked example | **This row promised an update and assigned nobody.** It said "adopted as the implementer reference, updated for the new call ordering", and no updated example exists. The original is now wrong in five ways, two of them failures this document rules against by name - 12.12 G25 |
| 3.6 Schema lineage | Accepted, **except three rows that carry live instructions rather than history** - `semantic_role`, `fact_indexes` and the `fact_id` alias deadline. 12.12 G28 |
| 4.1 Validator | Accepted; nine current predicates carried forward, `same_unit_bars` behaviour preserved as a fixture (row 19). **Two universal rules were not carried**: "convertible or identical" lost its second word, and `plan_version is current` has no check - 12.13 G29 and G32 |
| 4.2 Downgrade ladder | Ships (row 50). **Its kill criterion did not** - 12.13 G30 |
| 4.3 Compiler | Ships; `planned_type` and `rendered_type` both recorded. **`alt_text` had two owners and now has one** (12.8 X6), and two of its three accessibility duties were unassigned - 12.13 G31 |
| 4.4 Rendering | **Closed**: d3, progressive enhancement, inline SVG (rows 21-23) |
| 4.4.5 Draco | Evaluated with a written verdict (RV12) |
| 5.1 Upstream metrics | Ships, three validation tiers - **the methods, and none of the seven instruments**, including the one P.5.1.1 rates highest. 12.13 G35 |
| 5.2 Machine quality | Ships; `structural_efficiency` renamed `density_floor` where it measures size (row 27). **P.5.2.6's first-ranked tuning lever, the `purpose` to `type` prior, was not carried** - 12.12 G22. Neither were the fitter's four guardrails and its release rule (12.13 G34) nor the four comparability rules (12.13 G37) |
| 5.3 Cost | Ships; `compile_ms` and `render_ms` split from the start. **The timing reconciliation rule was dropped, and section 14.4 then rebuilt its argument from scratch** - 12.13 G36 |
| 5.4 Human instrument | Ships, Q1-Q5 plus Q4b, plus the timed arm (row 67) - **the components, and none of the protocol**. 12.13 G38 |
| 5.5 KPI set | Ships, per potential class and per vertical (Editor). **`human_visual_gain` has no home and the no-benchmark guard is missing** - 12.13 G39 |
| 5.6 The two loops | Accepted |
| 6.1 Telemetry event | Ships as the canonical schema; `state/visuals/` is its store (row 55) |
| 6.2 Console | Ships, plus every existing eval metric not yet on the console (row 70). **The never-blend rule that constrains one of its panels was carried as a field and not as a rule** - 12.12 G23 |
| 6.3 Feedback without a server | Ships, amended by O12 |
| 6.4 Versioning and migration | Ships; **versions are date-stamps, not integers** (P.L15) |
| 7.1 Risk register | Section 12.3 |
| 7.2 Litigation | Section 12.2 |
| 7.3 Open questions | Section 12.4 |
| 7.4 References | Retained |

### 12.6 The section 1.2 diagram, box by box

Audited 2026-09-03 against the proposal's end-to-end flow, because a coverage matrix organised by section number can miss a box that has no section of its own.

**Covered: every box, every Visual Plan field, all eight Visual Validator checks, and all seven SEMANTIC MODEL responsibilities.** The three the owner named are contracted fields rather than prose - *assess visual need* is `decision`, *choose the form* is `purpose` plus `type`, *select elements* is `element_ids`, all in section 10.1's call-2 shape. The pass/fail fork is `validation_result`; the failure carries `rejection_reason` and `rejection_stage`. The diagram's own edge label, "deterministic extraction + model labelling", is O37 and calls 0 and 1.

Six things were not covered. Each gets an owner here so none falls between plan-docs.

| # | Gap | Why it is load-bearing | Owner |
|---|---|---|---|
| G1 | **The `none` decision records no cause.** Section 14.5 names five gates a visual must clear and row 36 adds a sixth, the per-visual byte cap. Only a validator failure carries a reason, so five of the six routes to `none` are one undifferentiated bar | `none` is the majority outcome by design - section 14.5 says "`none` remaining common is not a defect". A majority outcome with no cause breakdown means the largest number on the console explains nothing. Add `none_reason`, a typed enum, one member per gate | **K** |
| G2 | **Downgrade depths 2 and 3 are unspecified.** Row 50 ships the ladder with an "escalating floor" and names no percentile; the proposal's depth 2 is p75 plus an annotation and depth 3 is refuse | A ladder with one named rung is not a ladder. The floors are computed from depth-0 published visuals only (row 50), but the percentile at each depth is a knob and needs a home under `visuals` | **H** |
| G3 | **No visual console panel is named anywhere.** Every reference is generic - "the console panels that read them". O34's `band_reason` panel is the only one this document names | Doc K's whole worth is "the ability to tell whether the visual work worked", and section 15.2 fails its own test if the panels are left to be invented. **Five must exist**, widened from three on 2026-09-04 by 12.9 G14: rejection reason over time, keep rate by `downgrade_depth`, `planned_type` against `rendered_type`, the **downgrade funnel** and the **pipeline funnel per potential class**. Five is a floor, not the list - 12.5 accepts P.6.2 whole, so all thirteen required panels are in scope | **K** |
| G4 | **`downgrade_edge` is a field with no legal-edge table.** Only `pie` -> `stacked_bar` is named, in row 43 | Without a static allow-list the ladder can walk a comparison into a timeline and record it as a legal edge. The cross-family ban is what row 50's "purpose survives" invariant implies and never states | **H** |
| G5 | **`comparative` is missing from the potential classes, and `chartable` appears only in prose.** The proposal names five: `chartable`, `singular`, `processual`, `comparative`, `narrative` | Row 56 makes every rate report per potential class. A missing class is a missing denominator, which is the exact defect row 56 exists to prevent | **G** |
| G6 | **"NO geometry" is never stated as a rule.** The plan contract's other two prohibitions are ruled in row 4 and gate 3; the geometry ban is only implied | It is the rule that keeps the compiler swappable. A plan carrying a pixel is a plan bound to one renderer, and section 7 just made d3 that renderer | **H** |

**And one structural defect in this document's own rules.** `compile_ms` and `render_ms` were heading for two stores at once: section 12.5 puts them in the P.6.1 event at `state/visuals/` (row 55), while section 14.4 T3 adds `compile_visual` and `render_visual` spans whose durations 14.4a commits to `state/span-rollup/`. Section 14.4a's disjointness test compared the rollup against item-health alone, so **the fourth-record rule it exists to enforce would never have looked at the store the collision was in.** Both are corrected in 14.4a: the visual timings live in `state/visuals/` only, and the test now runs against every committed ledger.

### 12.7 The tail of the flow, audited for intent

Section 12.6 asked whether each box exists. This asks whether each box still does what it was **for**. Audited 2026-09-03 from the validator's pass/fail fork to the end of the diagram.

**Holds cleanly.** The machine loop still gates publication. The human loop still gates nothing - no gate in section 14.5 reads a label, and E1 bars a machine label from the publish decision. All four queue populations survive: published, rejected, config-B variants and the `none` arm.

**Stronger than the proposal's intent, and worth keeping.** Three places where this document tightened rather than carried:

| Tightening | Where |
|---|---|
| `review/` is a build artifact - never committed, never under `frontend/public/`. The proposal shipped it with the site | Row 68, section 9.3 |
| The `none` arm carries a floor above zero, so it cannot be quietly switched off | D10 |
| Every visual carries an annotated mark, not only a downgraded one | Row 30 |

**Five defects. G7 is the serious one.**

| # | Defect | Intent it breaks | Fix | Owner |
|---|---|---|---|---|
| G7 | **`state/visuals/` was specified two ways.** Row 55 said one row per *published* visual; section 12.5 and section 16 Q4 route the whole per-attempt event to that same store | "A rejected plan is never silently dropped." Under a per-publication ledger the diagnostic half of the machine loop - every refusal, every `none`, every typed rejection reason - is never committed. **The loop stops being auditable while still being the gate**, and a later run cannot tell a refused visual from one never attempted | Row 55 now reads **one row per attempt**, with `decision` separating published, downgraded, `none` and rejected. This is also the store G1's `none_reason` needed and did not have | **K** |
| G8 | **A downgraded plan's re-validation is never stated.** In the diagram the ladder is an arrow *into* the compiler, not around it | A downgrade that skips the validator can publish the thing the original plan was refused for | A fourth invariant beside row 50's three: a downgraded plan re-enters the **same** validator and the **same** compiler, and a depth that fails re-validation falls to the next depth rather than publishing | **H** |
| G9 | **The composite-score ban had no sentence.** The proposal states it twice - until the correlation between machine metrics and human keep rate is measured, no composite score may gate anything - and this document carried it only as the word "Accepted" in a coverage row while shipping the fitter (row 67) | Thirteen parallel agents read section 14.5's gate list. A rule that appears nowhere in the list reads as an oversight to fix, not a rule to keep | Stated outright in section 14.5: the quality index is a diagnostic and never a gate | **K** |
| G10 | **The rejected plan's body has no home and no size.** Row 68 says rejected plans are "recorded as JSON immediately" and names no path, no policy and no window. Section 9.3 registers the `review/` *renders* but not the plans themselves | Section 9.3 claims to name every artefact this project writes. An artefact missing from it has no retention policy, which is how a build artifact becomes a committed one by accident | The G7 ledger row carries the reason; the plan body does not fit a CSV cell. It takes the pattern T4 already set for raw spans - a short rolling window, a lookup, so it deletes rather than folds - plus a register row in 9.3 and a sampling ratio in `config/` beside `none_arm_ratio` | **K** |
| G11 | **Two paths to `none` bypass the reason field even after G1.** Gate 1 in section 14.5 refuses before the model is ever called, and row 36 degrades on the per-visual byte cap. Neither passes through the validator that owns `rejection_reason` | The pre-model refusal is the cheapest gate and therefore the most common, so the most frequent outcome would be the least explained | `none_reason` covers all six gates in section 14.5, not only the ones the validator sees | **K** |

**One field with no writer**, recorded so it is not mistaken for a contract: `gate_floor_applied` has a writer at depth 1 and none at depths 2 and 3, because G2 leaves those percentiles unspecified. It becomes real when H closes G2.

### 12.8 Contradictions inside this document, resolved

Six rows of this document disagreed with another row of this document. X1 to X4 were found by review on 2026-09-03, X5 and X6 on 2026-09-04. All are resolved here rather than left for a plan-doc to discover at merge time.
| # | The two rows | Why they could not both stand | Resolution |
|---|---|---|---|
| X1 | **12.1 D2** accepts "full vocabulary declared". **12.2 L2** amended that to "declared set is config" | Read as *limited to the types that have templates*, L2 makes P.D2's neighbour-downgrade unreachable, makes `wasted_decode_rate` identically zero so it measures nothing, and **breaks row 48**. Row 48 derives the build order from what the planner chooses; a planner that cannot name an unbuilt type can never say which template to build next. L2 cites row 48 as its own resolution, so as written it refuted itself | **Full vocabulary, located in config.** Rule #6 puts the list in `config/`; it does not shorten it. An unbuilt type stays declarable, is deterministically downgraded to its nearest built neighbour, and the downgrade is logged. `wasted_decode_rate` measures how often that happens and is the cheapest signal for sequencing the waves. **And this does not cross non-goal 3**, which says a type arriving without both a validator rule set and a compiler template is not in the vocabulary: **NG-3 governs what may render; D2 governs what may be named.** An unbuilt type never reaches a reader, so the enum stays full and the render set stays gated. Written down because an agent reading NG-3 alone would restrict the enum and undo this three weeks after it landed |
| X2 | **Row 15** rules "flat role map, all keys required". **P.D4** and P.3.2.1 define a *different* required set per type, with nine optional cells across three role names - `series`, `label`, `entity` | One flat map with every role required would make a `bar` emit `quantity_x`, `size`, `bins` and `event_label`. A flat map with roles left optional brings back the exact failure row 15 exists to prevent: "a confident chart with no bars in it, twice, on the first live run" | **Structurally present, semantically optional, per-type enforced.** One flat map. Every role name is a key and every key is in the schema's `required` list, so the decoder cannot omit one. An inapplicable role is emitted as an **empty array**. The validator's existing "roles valid for the type" check enforces the per-type set and rules whether empty is legal there. The cost is real and must be measured rather than assumed: roughly eight empty arrays per plan, at 6.01 tok/s decode |
| X3 | **12.1 D15** accepts the amended principle in one line. **Section 1** carried a different, weaker sentence | The proposal narrows its own slogan in P.1.5.2 because the slogan is not defensible. Accepting the amendment while printing the un-amended version is how the weaker one survives into `docs/` | Section 1 now carries P.1.5.2's formulation verbatim beside the slogan. It is the same claim section 10.1a arrives at from the other direction |
| X4 | **O2** scrubs "route" from every identifier, including a schema stem (15.4a). **C1** found that `Route` in `contracts/route.py` is a **persisted** contract with a committed `schemas/route.schema.json` | `CLAUDE.md` section 11: renaming a persisted shape is breaking and needs a changelog entry, a version stamp **and the read-side migration in the same commit**. Committed digest payloads were written under that stem. Nothing downstream of C1 picked this up, so O2 as written is a release blocker with no migration attached | **The rename is in scope and the migration is part of it.** Plan-doc H owns it: the new stem, the version stamp, the changelog entry, and a read-side migration that reads a payload written under the old stem. Row 63 already knows this file carries published enums - same file, same hazard, and the two land together |
| X5 | **12.4 Q1** rules "no bespoke version field" for the potential classifier. **12.5's 6.1 row** accepts the P.6.1 event "as the canonical schema" and section 16 Q4 says it is "adopted whole" - and that event carries `potential_classifier_version` | Fowler's reasoning is right and one config version beats a proliferation of bespoke ones. But the hazard P.2.4.4 names is real, and P.6.4.1 lists this stamp under "every rate in the system re-baselines". A version that exists only in `config/` and never lands on the row cannot tell a later reader which thresholds produced that row's class - **and the class is the denominator for every rate** (row 56). A stamp nothing carries is not a stamp | **Both stand, because the column is not a bespoke version.** No new number is minted: the row carries the value of the config file's existing top-level `version`, which is what Q1 already nominates. Q1 was refusing a **second source of truth**, not a **column**. K owns the column and its name - either P.6.1's name carrying the config value, or a name that says what it is - and `config/` stays the only place the number is set |
| X6 | **`alt_text` has two owners.** Section 1a's VISUAL PLAN box lists it beside `title` and `caption`, and section 10.1's call-2 output emits it - so **the model writes it**. 12.3 R11 says the opposite: "Closed - alt text generated deterministically by the compiler, inside D7" - so **code writes it**. Both were carried from the proposal, which holds the same split across P.3.1.1 and P.4.3.2 | This is not a wording choice, it decides four other things. **If the model emits it**, D7's numeral check is a live validator rule with a real rejection path, `alt_text` costs output tokens in section 11.3's derived budget, and **R11 is not closed**. **If the compiler generates it**, D7 is satisfied by construction because the compiler only holds element values, `alt_text` does not belong in the plan contract at all, and X2's every-key-required rule would otherwise make it a mandatory empty field. P.4.3.2 names the stake: alt text is "the last unguarded prose channel in the system" if the model writes it | **The compiler generates it, and the plan contract loses the field.** R11 is the later and stronger ruling, and it is the one this document already recorded as closed. Section 1a's box and section 10.1's call-2 shape are corrected to drop `alt_text`; the compiler assembles it from the plan and the elements, as P.4.3.2's Owns column says. Two consequences to carry: section 11.3's output budget is re-derived without it, and the sufficiency bar's alt-text check becomes a compiler oracle rather than a validator rule. **Found by cross-referencing two sections rather than by walking one**, which is why five section-walks missed it - the same shape as X3 | **H** |

**Two stale references in the proposal**, recorded so a plan-doc does not chase them. P.D15's body calls it "the section 2 principle", but the principle is in P.1.1 and its narrowed public form is in P.1.5.2; D15's own cross-reference column says section 1, which is correct, so only the body text is stale. And P.1.1 closes with "section 5 audits the full principle clause by clause" - it is **P.1.5** that does that, and section 12.10 re-runs it. P.5 is the measurement chapter and audits no clause.

### 12.9 Four more, from the second review

Section 12.6 checked whether each box exists, 12.7 whether it still does what it was for, 12.8 whether this document agrees with itself. This is the fourth pass, run 2026-09-04 against the proposal's **build order**, its **glossary** and its **structural defences** - the three places a coverage matrix organised by section number does not reach. The G numbering continues 12.6 and 12.7's single sequence.

| # | Defect | Intent it breaks | Fix | Owner |
|---|---|---|---|---|
| G12 | **`state/visuals/` folds to "one row per group" and nothing says what the group is.** Section 9.2 sets the policy and names no key; 9.3 gave the store `ledger fold` and a window knob that no longer exists | G7 made this store one row per **attempt** and G1 added `none_reason` so the majority outcome has a cause breakdown. A fold keyed on date alone deletes both at the window edge: the full-grain shard is gone and the aggregate never carried the cause. **This is the half that decides whether G1 was worth building** | Declare the key in the schema, the way `state/telemetry-aggregate/` already declares "one `(date, stage)` pair" in its own description. `(date, decision, none_reason, rejection_reason)` is the only key that survives the fold with G1 intact. Ruled together with the named window 9.2's correction already owes this store, and before the row that writes it lands | **K**, with **E** |
| G13 | **Two build-failing invariants are unruled, and a coverage row hides it.** P.2.3.2 declares build-failing that "every displayed value resolves either to a Tier 1 element, or to a derived value with a complete provenance chain", and P.6.2.1 puts `derived_provenance_complete` and `span_integrity_pass` on the console under "any failure is a build break, not an alarm". Row 2 softens the **span** invariant deliberately and well. Nothing rules on the other two - and **12.2's L10 row cited row 2, which answers a different litigation item**: P.L10 is integrity-invariant-versus-KPI, about value provenance; span drift is P.R5, which 12.3 closes with row 2 correctly | Row 2's amendment then reads as a precedent covering all three, and section 14.5's five gates all resolve to `none` at item level, so the softer regime looks settled. It was never asked. A corpus-wide build break over one drifted span is the wrong trade; publishing a number with no provenance chain is a different question and may well be the right one to break on | One sentence each for `derived_provenance_complete` and `span_integrity_pass` saying whether they break the build or degrade the item, and one saying why the span invariant is the exception rather than the new rule. 12.2's L10 row now points here | **H** |
| G14 | **The build order's named console deliverable appears nowhere in this document.** The proposal's step 7 is "Telemetry + Console - one canonical event schema, **the downgrade funnel**", and P.6.2.1's first two required panels are the pipeline funnel per potential class and the downgrade funnel. G3 named three panels and neither was among them | G3 exists so panels are not invented at implementation time. The downgrade funnel is the one panel that renders G1's `none_reason` end to end - planned, validated, depth 1, depth 2, rendered, `none` - and the pipeline funnel is the only panel row 56's per-potential-class denominator ever reaches. Naming three of thirteen and calling them the ones that must exist drops the two the proposal ranked first | G3 now reads five, with both funnels named, and says outright that five is a floor rather than the list - 12.5 already accepts P.6.2 whole | **K** |
| G15 | **The pairing rule is carried as instances, never as a rule.** P.7.1.1 states two structural defences: never alarm on a single metric that can be improved by giving up, always pair it with a diversity or coverage counter; and keep the human loop pointed at the output, not at the metrics. Of the three named pairs only rejection rate x `planned_type_entropy` survives explicitly, in 12.3 R1 | A rule generates the next pair; three panels do not. Every gate in section 14.5 can be improved by refusing more, and row 49 is the demand side of exactly one of them. Without the rule stated, the next metric added gets no counterweight and nobody notices | State the rule once in K beside the panel list. The components exist already - row 56 gives `missed_visual_rate` its denominator, row 8 reports `merge_rate` - what is missing is the instruction to alarm them in pairs. Rule 2 is already honoured, by row 65's "never show `why` to a reviewer" | **K** |

**Two of these were inherited rather than introduced, and saying so is not a defence.** Two of G15's three pairs were never panelled in the proposal either - P.6.2.1 lists keep-rate by downgrade depth rather than against missed-visual rate, and puts `merge_rate` in extraction health with no `semantic_coherence` beside it. And the glossary's `Ledger` was false in the proposal before this document bound identifiers to it (9.2, correction of 2026-09-04). K owns both regardless: a plan-doc that copies a gap forward has still shipped the gap.

### 12.10 The compliance audit, re-run

P.1.5 scores the governing principle clause by clause, and P.1.5.3 claims **zero undisclosed deviations**. That claim was made about the proposal. This document has since absorbed 39 owner decisions, 70 persona rows, 15 gaps and 4 contradictions, and nobody re-asked it. It is a table, not a project, so it is re-run here rather than assumed to have survived.

| Clause | P.1.5 said | Now | Why it moved |
|---|---|---|---|
| **One larger model** | Compliant | **Compliant**, and stronger | O17 retires the 4B completely - config entry, cache role, workflow job, env vars, prompt, tests. The proposal deleted a model; this document deleted its last mention |
| **performs all semantic analysis** | Compliant, as amended by D15 | **Compliant**, and the amendment carries more weight | Still one semantic authority, invoked twice. Section 10 reverses the ordering and adds the candidate pass, which is deterministic code and not an invocation at all (O37) |
| **deterministic code controls data integrity** | Partial - **Deviation A** | **Partial - Deviation A stands, and is now accepted as permanent** | Tier 2 labels and diagram edges are model-assigned by design. Section 10.1a tightens the anchoring rule per kind and names the two failures no check catches - mis-pointing and mis-labelling - which discloses more of the deviation rather than shrinking it. **O40 accepts it and moves the risk into [`../docs/concepts/digest.md`](../docs/concepts/digest.md)**, so it outlives this document |
| **and rendering afterward** | Open in practice - **Deviation B**, on L21 | **Decided, and conditionally compliant** | Row 22 closes L21: build-time SVG, hydrated on point-or-focus. The answer is "both, deliberately", so the clause holds only while row 31 holds - hydration must be pixel-identical. **Nothing has tested row 31**; doc I does not exist yet |

**Deviation B is closed as a decision and open as a control**, and recording it as simply closed would be the comfortable sentence rather than the true one. "Code owns the spec-to-pixels path" survives progressive enhancement only while the browser reproduces bytes code already chose. Row 31's stated reason was reader-facing - a chart that redraws on hydrate is this project's first spinner in all but name - and it turns out to carry a compliance load as well. **Doc I owns the test**: one plan, the build-time emit and the post-hydrate DOM compared byte for byte.

#### One candidate new deviation, disclosed rather than assumed

O12 and E1 put a model inside the labelling loop. The principle says deterministic code controls data integrity, and a machine label is not deterministic code, so it is scored here rather than left for someone to notice.

| Question | Answer |
|---|---|
| Does a machine label reach a reader? | No. Separate ledger, rendered on no page |
| Does it select what publishes? | No. E1 bars it, and 12.7 confirms no gate in section 14.5 reads a label |
| Is it pooled with human ground truth? | No, and `label_source` plus `model_id` keep the two separable after the fact |
| Does it touch a displayed value or a displayed string? | No |

Against P.1.5.2's narrowed formulation - "deterministic code controls every displayed value and every displayed string" - it sits **outside the clause**, so it is not a fifth deviation. Two things stop that being a comfortable answer. The narrowed formulation is the defensible one but the **slogan** is what gets quoted, and against the slogan this reads as a crossing. And the four guardrails are the whole of the argument, so **a plan-doc implementing three of the four silently creates the deviation this row says does not exist.**

**Ruled 2026-09-04 by O41: outside the clause, not a deviation, and the four guardrails bind doc L as a merge condition rather than as advice.** Doc L implements all four, or this row is wrong.

#### Scorecard, re-stated

| | P.1.5.3 | Now |
|---|---|---|
| Clauses fully compliant | 2 of 4 | 2 of 4 |
| Clauses partially compliant | 2 of 4 | 1 of 4 - Deviation A, accepted as permanent by O40 |
| Clauses conditionally compliant | - | 1 of 4 - Deviation B, on row 31, untested |
| Undisclosed deviations | 0 | 0. The one candidate was scored, ruled by O41, and is not a deviation |
| Non-goals amended | not asked | 1 of 7 - non-goal 5, by O12, E1 and O41. See 12.5 |

### 12.11 Six more, from the third review

Sections 12.6 to 12.10 audited boxes, intent, internal consistency and the compliance scorecard. This pass, run 2026-09-04, walks the **element record field by field** and the **potential classifier signal by signal** - the two places the coverage matrix disposed of an output and never looked at its input. Six gaps below; a seventh was a contradiction and is X5 in 12.8.

| # | Gap | Why it is load-bearing | Owner |
|---|---|---|---|
| G16 | **The potential classifier is an unbuilt algorithm, and it is not deterministic.** P.2.4.1 names seven signals - `numeric_density`, `measure_diversity`, `temporal_structure`, `entity_count`, `comparison_signal`, `process_signal`, `quote_density` - and **not one of them appears anywhere in this document.** G5 fixed the class list, row 56 made every rate report per class, section 1a draws the box; nobody wrote down how a class is computed. And P.2.4.1's header says "computed deterministically from elements, no model call", which read against section 10.1b is not what it sounds like: `numeric_density` and `measure_diversity` rest on `measure_canonical`, which is **Tier 2 and model-assigned**; `entity_count` and `quote_density` read call-1 output; `comparison_signal` and `process_signal` need a contrastive and a sequencing lexicon that has no author; `temporal_structure` needs the `date` kind, which correction **C15 says does not exist at all** | The largest unspecified algorithm left, and its blast radius is the whole measurement layer - P.5 reports every rate per class and P.2.4.3 calls it "the highest-leverage measurement change". **And the consequence nobody wrote down: the potential class inherits Deviation A.** The denominator under every rate in the system would rest on judgement O40 has just accepted as unverifiable. It also collides with row 46, which gates the entire diagram family behind "the deterministic `processual` classifier" - a classifier whose `process_signal` has no definition, no producer and no word list | **M**, split out of G by O42, and it blocks **J** |
| G17 | **Three places contradicted a ruling this document had already made.** E5 settled it on 2026-09-03 - "the call structure does not change; O3's two calls stand" - and then section 1a drew the reachability gate's "no" branch around the semantic model box, section 14.5 wrote "the model is never asked", and E5's own tail floated splitting call 2 into two requests as a conditional fallback. Call 2's output is `{summary, visual}`: it is the call that writes every item's summary | **This was never an open question, and presenting it as one cost a round trip.** Read together the three made the call count look undecided, so a reader counting `call 0`, `call 1`, `call 2` found three things named "call" against O3's "two calls" - and D1's row had to explain the discrepancy in line, every time it was cited. A rule needing an explanation beside every citation is a naming defect, and it is the mechanism by which a settled decision kept re-opening | **CLOSED 2026-09-04.** O43 states the invariant as a numbered decision: exactly two model calls, always; a gate suppresses plan fields and never skips a call; three calls is out of scope until a timeout rate is measured. The gate box is redrawn, section 14.5 gate 1 restated, and `call 0` renamed to **the candidate pass** in all twelve places, so counting the calls in this document now yields two | **H**, closed |
| G18 | **The compiler's deterministic truncation is missing, and it is the pressure valve.** P.3.5 and P.4.3.2 both make it a compiler responsibility: where a claim must be shortened to fit a card the compiler truncates deterministically with an ellipsis, and the model never rewrites. Nothing here carries it. The nearest rule is row 39's cap of `summarize.max_verbatim_words` on `quotecard` | **A cap rejects; truncation renders.** Section 14.3 establishes that constant is 20 words and exists as a summary anti-copying cap, so nothing says what happens to a 40-word claim the planner picked for a `callout` or a `whowhat` cell. The valve got **more** necessary, not less: section 10.1b made quotes and claims sentence-index-only, a better guarantee than exact search, and sentence indices yield **whole sentences** - precisely the input truncation exists to handle. P.L32 names what it closes: real sentences are rarely card-shaped, and "let it tidy the wording slightly" will sound reasonable every single time | **H**, with **J** |
| G19 | **Three field names are in play for one concept, and a gate cites the one that vanished.** Section 10.1b's Tier 1 list reads `element_id kind surface span_start span_end span_excerpt value unit sentence_index extractor` - no `raw`. Row 1 discusses `raw` as though it survives and explains why it cannot serve as `span_excerpt`. 12.4 Q3 defines the whole of `information_delta` on it: "plan `element_ids` whose `raw` string does not appear in the summary" | `information_delta` is gate 4 in section 14.5. Computed on the wrong one of the three it silently changes what the metric means: `raw` is whitespace-cleaned and drops the magnitude word and unit, `span_excerpt` is the verbatim slice, and nothing says whether `surface` is `raw` renamed or a third thing. **This is the failure 15.4a exists to prevent, five sections earlier in the same document** - `surface` propagated out of the model's reply shape into the element record | **G**, with **K** for Q3 |
| G20 | **`context` was deleted without a line.** Correction C2 records that today's `NumericFact` is `value, raw, unit, context`; section 10.1b's Tier 1 list does not carry it | It is probably superseded by `sentence_index` plus the span, and that would be an improvement - `context` is a derived string, a sentence index is a pointer. Say so. **Section 2 exists to correct this document's claims about what ships**, so a field that ships today disappearing in silence is the one deletion that section cannot afford to leave unstated | **G** |
| G21 | **`derived_value_rate` is never named.** It reaches scope only through 12.5's blanket acceptance of the P.6.1 event | P.2.3.2 puts it and `trusted_data_ratio` beneath the provenance invariant as its two reporting metrics, and G13 is already re-opening that invariant - so it costs nothing to name it in the same pass. P.L22 says why it is load-bearing: the closed allow-list and the separate `derived_value_rate` "are the only things keeping it narrow - skip either and the guarantee is gone unnoticed" | **H**, with **K** |

**These do not cost the same, and sequencing them by cost is wrong.** G19 and G20 are one naming pass in G and must land before Q3 is implemented. G21 rides with G13 in one commit. G18 is a single compiler rule in H. **G16 is not a gap, it is an unbuilt algorithm** carrying two missing lexicons, one missing extractor and an unstated inheritance of Deviation A - which is why O42 gave it a plan-doc of its own rather than leaving it as one phrase in G's row. G17 stays with H, because the gate is H's to draw; it sits here because the drawing it breaks is the one every other doc reads first.

### 12.12 Seven more, from the fourth review

Sections 12.6 to 12.11 audited boxes, intent, internal consistency, the compliance scorecard and the element record. This pass, run 2026-09-04, walks **section 3 of the proposal** - the plan contract, the three vocabularies and the schema lineage. Section 12.5 disposed of it in eleven rows, and it carries more instruction per line than any other chapter.

| # | Gap | Why it is load-bearing | Owner |
|---|---|---|---|
| G22 | **The `purpose` to `type` learned prior is missing entirely.** P.5.2.6 ranks it **first** among all tuning levers - "the largest single lever on keep-rate" - and P.6.3.3 gives it an artefact, `fit_priors.py` producing `priors.json`, in the same diagram as `fit_weights.py`. Zero hits here for any of it. **Correction, 2026-09-04: this row originally said `fit_weights.py` is "the one this document does ship". It is not shipped, it is intended** - row 67 ships a decision and no artefact, which is 12.13 G34 | Row 67 took one of the four artefacts in that diagram as a name and none as a specification, because weights and priors read as one job. **They are opposites.** Weights score a finished visual for triage and need about 200 labelled visuals, so they are blocked on M6. The prior steers which type the planner picks in the first place, has a published empirical seed (Saket, Endert and Demiralp, measured at 5 to 34 data points, the band our visuals sit in) and **needs no labels at all**. This document defers the expensive one and drops the free one. **And the prior carries a constraint nobody has stated: it must be static within a shard.** Rendered into the system prompt once at startup it is free, because the system turn is prefix-cached (section 10.2). Injected per item it changes the prompt per item and destroys the KV reuse the whole two-call design rests on - row 11's `cached_tokens` assertion would fail and nothing else would look wrong | **H**, with **L** |
| G23 | **The never-blend rule is carried as a field, not as a rule.** P.3.4 states it - "`chart_type_distribution` splits three ways and the families are never blended. A blended distribution is uninterpretable" - and P.3.4.2 repeats it for the diagram case: "`decision: diagram` is not a chart type and is never aggregated into the chart distribution". The **data** to split by family exists here, through P.6.1's `family` field and P.5.5.1's `type_distribution x family`. The instruction does not | **Exactly the shape of G15, one section later.** The failure is concrete and cheap to hit: a console panel titled "type distribution" that pools `bar`, `flow` and `quotecard` into one histogram is a reasonable thing to write, is uninterpretable, and nothing here would stop it. G14 has just made `planned_type` against `rendered_type` a required panel, and **this rule constrains that exact panel** - so it belongs beside it rather than three sections away | **K** |
| G24 | **"No cycle unless the article asserts one" is nowhere.** P.3.4.2 lists it among five diagram-family predicates. 12.5's blanket accept of P.4.1 carries "nine current predicates" forward, and this is not one of them - there is no current implementation to carry | Section 7.3 pins `d3-force` for the node-edge graph and gives it a seven-step determinism recipe. **A cyclic graph in a force layout is not a rendering error.** It lays out cleanly and reads as an assertion: an invented feedback loop is an invented claim. This is the family where row 47 already refuses to compromise on a single edge, and a cycle is a claim built out of edges that each anchor perfectly well on their own | **H** |
| G25 | **The worked example is promised, not delivered, and the original is wrong in five ways.** 12.5 reads "adopted as the implementer reference, **updated for the new call ordering**". No updated example exists, and section 10.1's call-2 block is a schema sketch rather than a populated instance | P.3.5 styles itself as "the reference an implementer should code against - fully populated, no placeholders", so an implementer following 12.5 opens it and copies it. It is wrong five independent ways, and **two of them are failures this document ruled against by name**: (1) one root object as if from a single pass, against section 10.1 and row 9; (2) `encodings` carries only `time` and `quantity`, which X2 makes schema-invalid; (3) `"plan_version": 3`, an integer, against P.L15's date-stamps; (4) `"element_ids": [3, 5, 7]` - small integers that read as positional indexes, **the exact field C13 and D14 removed**; (5) `confidence` decoded second, straight after `decision`, which is **precisely the position row 18 rules against**. One JSON block fixes it, and it is what H and J will both copy | **H** |
| G26 | **`stacked_bar` has no gate of its own.** P.3.4.1 gives it one - "parts exhaustive against a declared whole, or downgraded to grouped `bar`". Row 43 names `stacked_bar` only as pie's downgrade target, and section 7.2 repeats that | **G8-shaped, and it should be ruled with G8.** A `pie` refused because its whole was summed rather than declared lands in a `stacked_bar` that never re-asks the question, so the refusal buys nothing. G8 already requires a downgraded plan to re-enter the same validator - which helps only if the target type has a predicate to re-enter it with | **H** |
| G27 | **The `pie` and `bubble` telemetry flag is gone.** P.3.4.1 flags both so their keep rate can be compared directly against the position and length types: "if `pie` under-performs over a meaningful sample, that is an empirical result, not an argument" | Row 43 settles P.L3 by shipping pie under a gate. **The flag is what makes L3 decidable later.** Without it the pie question can only ever be re-argued, which is how a settled decision becomes a recurring one | **K** |
| G28 | **Three schema-lineage rows carry live instructions and none is dispositioned.** `semantic_role` was "adopted as the encoding key itself"; `fact_indexes` was rejected in favour of `element_ids`; and `fact_id` carries a deadline - keep it as a deprecated alias for exactly one release, then remove it. Zero hits for any of the three | P.3.6 is mostly historical, and these three are not. X2 implements `semantic_role` without citing it, so the reasoning behind the strongest part of the encoding design is recorded nowhere. And an alias with a deadline attached is the kind of instruction only ever noticed after the release it was supposed to end at | **G**, with **H** |

**Two are free, four are one sentence, and one is not.** G25 is a single JSON block. G27 is one flag on an event 12.5 already accepts whole. G28 is three lines. G23 and G24 are one rule each, in K and H. **G22 is the one with a real cost, and it is the cheap half of a job this document already took** - `fit_priors.py` needs no labels, so unlike row 67's weights it is not blocked on M6. Its static-within-a-shard constraint is a prompt-architecture rule rather than a fitting detail, so it belongs in H before the prompt is written, not after.

### 12.13 Eleven more, from the fifth review

Sections 12.6 to 12.12 walked the diagram, the tail, the element record and the plan contract. This pass, run 2026-09-04, walks **sections 4 and 5 of the proposal** - the validator, the compiler, the renderer, and the whole measurement chapter. It is the pass that found this document's fifth inherited contradiction (X6) and an error in 12.12's own G22.

| # | Gap | Why it is load-bearing | Owner |
|---|---|---|---|
| G29 | **"Convertible or identical" lost a word, and the word was the check.** P.4.1.2 is deliberately precise: units must be "convertible or identical - **not merely equal strings**". Every restatement here drops it - section 1a's validator box says "units compatible", section 14.5 gate 3 says "units are compatible" | Convertibility is not a validator refinement, it is **a new class of displayed value**. Drawing `4,200 tonnes` beside `4.2 kilotonnes` on one axis renders a number the article never wrote, which lands inside P.2.3's Derived Value contract - **whose function list is a closed allow-list of `count`, `sum` and `share_of_declared_whole`, adopted verbatim by row 45. `convert` is not on it.** Section 10.6 refuses the *model* doing unit normalisation and says "code does arithmetic", which reads as settled and answers **who**, never **whether**. Two consistent positions exist and this document holds neither: units must be identical, and `tonnes` beside `kilotonnes` is a rejection (cheapest, and consistent with row 8's prefer-rejection rule); or `convert` becomes a fourth derived function with a versioned unit table, a provenance chain, and `derived_value_rate` counting it | **H**, ruled with G21 |
| G30 | **The ladder shipped without its kill criterion.** P.4.2.5 pre-commits to the evidence that retires it: `visual_keep_rate` at depth 1 or more against depth 0, and if downgraded visuals are kept materially less often "the flag goes to `off` - **the ladder is deleted, not tuned**". The instrument is here twice - P.6.2.1's panel, and G14 just made it required. The decision rule is nowhere | **Row 42 did this correctly for `keyfacts` and row 50 did not do it for the ladder.** The proposal's own reasoning applies unchanged: pre-committing to the kill criterion now is cheaper than defending it later. A ladder carrying four invariance rules, G2's percentiles and G4's edge table is a substantial mechanism to be maintaining on faith | **K** |
| G31 | **Two of the compiler's three accessibility duties are unassigned, and the architecture creates the question the proposal warns about.** P.4.3.2 gives the compiler contrast, **focus order** and **screen-reader structure**. Row 28 covers contrast properly. The other two are zero hits. P.4.4.4's fifth question is the pointed one: does accessibility live baked into the static output or re-derived client-side - "splitting it across both is how it silently regresses" | Progressive enhancement (row 22) **is** that split. Rows 31 and 33 push toward baked without ruling on it: row 31 is about pixels, row 33 is a design constraint. **This answers itself off a test doc I already owns**: 12.10 assigns I the byte-for-byte hydration comparison, and if the DOM matches byte for byte then focus order and the accessible tree match by construction. One sentence riding on a test that already exists | **I** |
| G32 | **`plan_version is current` has no validator check.** It is P.4.1.1's eighth universal rule and guards contract drift. Section 1a's validator box and section 14.5 gate 3 both omit it | P.L15 makes versions date-stamps, so "current" is a comparison and not an equality - worth stating, because X1 just moved the type vocabulary into `config/` where it can now drift independently of the contract that reads it | **H** |
| G33 | **`comparison` grid rectangularity is stated on the derived type and missing from the base type.** Row 41 gives the rule to `whowhat` - each cell pairs an entity span and a claim span from the same sentence, "or the cell is empty" - and row 41 also ships `whowhat` **as** a one-attribute `comparison` grid | Row 38 ships `comparison` first of the whole infographic family, so the base type reaches a reader before the type that carries its only shape rule | **J** |
| G34 | **Row 67 ships a decision and the machinery has no artefacts.** "Weight fitting, pairwise mode and the timed arm all ship", and doc L lists weight fitting as a deliverable. Zero hits for `weights.json`, `fit_weights.py`, `weight_version`, `holdout`, or any fitting method | **P.5.2.3's four guardrails are the entire defence against a fitted model quietly getting worse**: hold out 20 percent of pairs, refuse to promote unless holdout ranking accuracy improves, clamp per-refit coefficient movement, keep the previous version for instant rollback. A fitter without them is a number that moves every month with no way to separate improvement from noise. And P.5.2.3 states a release rule twice, in P.5.2.3 and P.6.4.1: **never change `components_version` and `weight_version` in the same release, or the entire score time series is lost.** Both are absent | **L** |
| G35 | **The seven upstream metrics are absent, including the one the proposal rates highest.** 12.5 disposes of P.5.1 as "Ships, three validation tiers", which covers the methods and none of the instruments. `extractable_but_unused_rate` - elements extracted but never selected by any plan - is called "the most useful free diagnostic in the system", and `span_integrity_rate` is missing beside it | D13 exists to separate a planner regression from an extractor that started missing numbers, "and the planner gets blamed for both". **`extractable_but_unused_rate` is the single metric that discriminates them**: when it rises the planner is under-reading the table rather than the extractor under-producing. It is free and needs no labels. `span_integrity_rate` is the reporting half of row 2's three-part span invariant, and **G13 is already re-opening whether `span_integrity_pass` breaks the build - the metric and the invariant should be ruled together** | **M** (O42), with **K** |
| G36 | **The timing reconciliation rule is missing, and section 14.4 rediscovered it without citing it.** P.5.3 states it: all stage timings sum to `wall_clock_total`, any residual reported as `unattributed_ms`, and "a timing set that does not reconcile is how invisible costs survive". P.6.1 carries the field and P.6.1.1 makes it a rule | Section 14.4's headline argument for turning tracing on is unaccounted shard wall clock - `job_seconds` minus the summed stage times - and it says "nobody currently knows that". **So this document built the mechanism and dropped the invariant that makes it self-checking.** `unattributed_ms` plus a reconciliation assertion costs nothing on top of T5's rollup and turns "nobody knows" into a number that alarms | **C**, with **K** |
| G37 | **The four comparability rules are absent, and G12 needs them in the room.** P.5.2.4: report percentile rank within the corpus rather than raw score; stratify by potential class, family and element-count band, then z-score within stratum; publish a rolling 28-day median as the headline; track the distribution rather than the mean, because "a bimodal distribution is the interesting finding and a mean hides it" | 12.9 G12 is about to settle a fold key for `state/visuals/` - `(date, decision, none_reason, rejection_reason)` - so the cause breakdown survives the window edge. **P.5.2.4 says the quality scores need stratum and shape preserved too.** Settle the key without this in the room and the aggregate keeps counts and loses shape, after which no percentile and no bimodality check is recoverable | **K**, ruled with G12 |
| G38 | **The human loop ships without its operating manual.** Three omissions, one theme. P.5.6.1's four phases - Bootstrap at about 200 stratified labelled visuals, Calibrate on pairwise only exiting when holdout accuracy is stable across two refits, Automate on a shrinking random sample exiting on machine-to-human rank correlation, then Steady state - are zero hits. P.5.4.1's answer locking is absent: "a reviewer who commits to keep first will rationalise Q1 to Q4 to match". P.5.4.3's six validity conditions are absent, including the one the timed arm rests on: **the question is authored from the elements, never from the visual** | The phases are **what makes M6 actionable**. M6 says start labelling in parallel and the rate reveals itself - the phases are what the revealed rate is measured against, and without them there is no exit criterion for any of it. Row 65 protects a reviewer from anchoring on `why` and nothing protects them from anchoring on their own first answer. And a timed arm whose questions are written from the visual measures nothing while still producing a number | **L** |
| G39 | **Two small ones, both cheap.** `human_visual_gain` is zero hits - one of only eight human KPIs, and the one asking whether comprehension materially improved; it rides in on 12.5's blanket with no home. And P.5.2.5's no-benchmark guard is absent: **there is no published industry average for chart keep rate or any composite visual-quality score, so any figure quoted from the internet as a benchmark for them is quoting nothing** | The second is Rule #10-shaped, and this document enforces Rule #10 vigorously everywhere else. One sentence, and it stops a future agent setting a target from a blog post | **K** |

**One of these is a correction to this document's own audit.** 12.12's G22 said `fit_weights.py` was "the one this document does ship". It is not shipped, it is intended - row 67 names it and specifies nothing, which is G34. The same pass should have caught both artefacts in P.6.3.3's diagram and caught one. G22 now says so.

**And one is the fifth inherited contradiction, X6.** It surfaces only by cross-referencing P.3.1.1 against P.4.3.2, which no section-walk does - five passes went past it. The lesson is worth more than the row: **a coverage matrix organised by section cannot find a contradiction that lives between two sections.** X3 was the same shape.

---

## 13. Measurements that must be taken

Rule #10: an unmeasured number may not justify a design. Each row blocks something named.

| # | Measurement | Cost | Verdict | Blocks |
|---|---|---|---|---|
| M1 | Memory headroom on the runner | **already taken** | **CLOSED.** 72 rows, peak 13.29 GiB worst on a 14.90 GiB box. Write it into `docs/reference/measurements.md` | Was blocking `n_ctx`; no longer |
| M2 | **Marginal MB per published day** | **one command** | **TAKE TODAY.** The two available readings differ by 18x - 3.90 MB/day from the per-item figure, 70.2 MB/day from the built-to-payload ratio, which is 172 days to the alarm or 9.6. Difference `retention.measure()` on two committed dates | `image_months`, off-Pages hosting, the coverage target, E3 |
| M10 | Repository pack growth per day | **one command** | **TAKE WITH M2.** Pack size at two commits, differenced. Rides along free | Whether the remote carrier trades a hard cap for a worse soft one |
| M7 | How often an article states a whole | **one command** over the committed corpus | Take it - nearly free - but it gates the vocabulary doc only, not the critical path | `pie` and `stacked_bar` template value |
| M11 | **Duplicate rate at plan time** | **one command** | **TAKE WITH M2.** The committed day payloads already carry `also_covered_by`; that count is the upper bound on what a plan-time cut would save | The dedup threshold - section 14.2 |
| M3 | Summarizer cross-host spread | 10 full runs | **SKIP - you already have it.** The ledger spans five CPU models and `job_seconds` 1,584 to 8,124 s, a **5.1x spread on real production work**, which is better evidence than ten synthetic shards | `shard_timeout_minutes`; conservative default below |
| M5 | Console alarm thresholds | one corpus month | **SKIP.** Ship every alarm in record-only mode with no threshold. An alarm set on a guess is worse than no alarm | Every console alarm |
| M9 | `raw.githubusercontent.com` under burst | scripted, hits a third party | **SKIP for now.** Keep `visuals.asset_base_url` same-origin. The number is not needed until M2 says bytes must move off Pages | The degraded state for the remote carrier |
| M4 | Call-2 `cached_tokens` | cannot precede the code | **Not a measurement campaign - a test, and it is two assertions rather than one**, because the two halves fail for different reasons. **The floor that must hold:** `cached_tokens >= call-1 prompt tokens`. The system turn and the user turn carrying the article and the candidate table are byte-identical on both calls and come first, so they prefill once or the prompt was built in the wrong order. **The target that must be measured, not assumed:** whether call-1's *generated* tokens also cache. They sit in the slot after call 1, but call 2 re-renders them as an assistant turn through the chat template, which adds wrapper tokens the model never generated. If that re-render does not tokenise identically, the common prefix ends at the article and roughly 1,500 tokens re-prefill - a cost, not a cliff, because the article is already safe. Record both numbers | Whether the two-call design is affordable |
| M8 | Build-time render cost per visual | cannot precede the code | Same. Time the d3 emitters when they exist, 20 repetitions, median and interquartile range | The corpus re-render path |
| M6 | Human labelling cadence | needs a person | Gates the review plan-doc only. **Do not let it block anything earlier.** Start labelling in parallel; the rate reveals itself | Weight fitting, pairwise, the timed arm |

### 13.1 The shortest path - three commands, then one dispatch

1. **M2** - difference `retention.measure()` on two committed dates. Unblocks `image_months`, off-Pages hosting and E3.
2. **M10** - pack size at two commits. Unblocks whether the remote carrier is a trade or a loss.
3. **M11** - count `also_covered_by` over the committed day payloads. Unblocks the dedup threshold.

Then land `n_ctx` 16384 **and** `flash_attention` on together, on one manual dispatch, and read the KV-buffer and compute-buffer lines out of `llama-server.log`. That single run closes the 7.7 GiB gap between arithmetic and measured memory, and is the only thing standing between the project and 32768 if it is ever wanted.

**Nothing else blocks the first plan-doc.**

### 13.2 The shard budget, and why the timeout rises

Measured over 80 shard rows at 40 items: median **78.5 min**, p90 **101.7 min**, worst **135.4 min** - 90.3 percent of the 150-minute timeout.

At 20 items the base work roughly halves. Call 2 at the full output budget costs about 260 s an item, so 20 items is about 87 minutes.

| | Base at 20 items | Buffer for call 2 | Call 2 needs | Verdict at 150 | Verdict at 200 |
|---|---|---|---|---|---|
| Median | ~39 min | 111 min | 87 min | fits, 24 min spare | fits, 74 min spare |
| p90 | ~51 min | 99 min | 87 min | fits, 12 min spare | fits, 62 min spare |
| **Worst** | **~68 min** | **82 min** | **87 min** | **overruns by 5 min** | **fits, 45 min spare** |

**Raise `run.shard_timeout_minutes` from 150 to 200.** Three reasons it is free:

1. **Actions minutes are free and unmetered on a public repository** (Rule #2 states it outright), so a longer ceiling costs no money.
2. **A timeout is a ceiling, not an allocation.** A job that finishes in 60 minutes consumes 60 minutes whether the cap is 150 or 200.
3. **The retired visual job returns its 40-to-50-minute serial slot**, so the run does not get longer end to end even though the shard may.

200 minutes is 56 percent of the 6-hour platform ceiling, which is the one number that is not ours to move.

**Do not lower the timeout to "reclaim" the halved item count.** Size from the worst case. The margin between 78.5 and 135.4 minutes is exactly what the second call spends.

### 13.3 Six memory fields to add, all from data already collected

`peak_rss_bytes` is llama-server's high-water mark alone, so every headroom figure above is an **upper bound on headroom** - the unsafe direction. All six below are optional additive fields on `RuntimeCountersRow`: one changelog entry, `version` stamped, no read-side migration.

| Field | Source | Already collected? | What it unblocks |
|---|---|---|---|
| `kv_cache_bytes` | `llama-server.log` KV-buffer line at load | yes, already passed as `--server-log` | Closes the gap between 5.6 GiB of arithmetic and 13.29 GiB measured |
| `compute_buffer_bytes` | same log | yes | The only other term that moves with `n_ctx`. Proves or kills the flash-attention saving |
| `n_ctx_configured` | same log | yes | The row says which window produced its memory number |
| `model_buffer_bytes` | same log | yes | Proves the weights on disk are the weights in memory |
| `python_peak_rss_bytes` | `rss-samples.tsv` column `python_vmrss_kb` | **yes, and thrown away** | llama-server is not the whole job |
| `cgroup_peak_bytes` | `memory-peak.txt` | **yes, and only echoed to a 2-day artifact** | The number the runner counts against the limit. The only authoritative one |

One collection defect to fix with them: the sampler reads `VmHWM` for llama-server but `VmRSS` for python. `VmRSS` is instantaneous, so a 15-second sampler can miss a spike and the recorded python peak is a **lower** bound. Read `VmHWM` for both.

---

## 14. Answers to standing questions

### 14.1 `page_weight.ceilings_bytes` - why it exists and why PRs keep failing

It is a **gzip size ceiling per prerendered route**, enforced by `frontend/scripts/bundle-gate.mjs` reading `config/idhazh.json`.

Why it matters: a prerendered HTML page that quietly grows is a page that quietly gets slower on a phone on a slow connection, and nothing else in the project would notice. `/console/` is at 276,828 bytes gzipped - a quarter of a megabyte of HTML before a single script.

Why it keeps failing PRs, in the config's own words: the three `/console/` ceilings "grow with the ledger their panels read, so each ceiling carries a measured few days and **expires by design**". **These ceilings are meant to be re-baselined.** A failure is usually the gate doing its job on a page that legitimately grew, not a defect.

Two things fix the friction without losing the gate:

1. **Re-baselining is routine, not an incident.** Record the new number and the date in the same commit. A page that renders a day is already never capped - only `/` and `/<date>/` are exempt, because the only way under such a ceiling is to publish fewer items.
2. **Give the visual work headroom before it starts.** Re-baseline every `/console/` ceiling once, at the top of the work, with a stated buffer sized from measured growth rather than raised reactively when a PR goes red. A ceiling raised in the PR that broke it is a ceiling nobody is enforcing.

#### Test filtering - there is none today

`pyproject.toml` has `[tool.pytest.ini_options]` with `testpaths = ["backend/tests"]` and `addopts = "-q -n auto"` and **no `markers` list at all.** Every local run is the whole suite.

Add markers for the whole project, not only the visual work:

| Marker | Covers | Why it earns a name |
|---|---|---|
| `contract` | Schema generation, drift, round-trip | The gate that must run on every contract change and almost nothing else |
| `visual` | The planner, the validator, the compiler, the renderer | The new surface. Lets a renderer change run in seconds |
| `slow` | Anything over a second - canary sweeps, corpus scans, the span leak guard | The set a developer skips locally and CI never does |
| `workflow` | The YAML contract tests and the shell-script tests | Only relevant when `.github/` changes |

CI keeps running everything. The markers exist so a developer can run the ten tests their change can break, and so the six-minute local suite stops being the reason a gate gets skipped. On the route tests specifically: they move with the module, but `same_unit_bars`' behaviour becomes a committed fixture (row 19) rather than being deleted - it records a real live model failure.

### 14.2 How duplicates are found today - and the correction

**Assemble does not de-duplicate. It groups, and removes nothing.** `collapse_same_story()` clusters by embedding similarity at 0.94 with a weakest-link rule, and its own docstring states the outcome: "Nothing is removed. Every item stays in the published order it was in" ([backend/idhazh/assemble.py](backend/idhazh/assemble.py#L383)). It is a display decision.

**And `carried_by` only sees an identical URL.** `merge()` groups by `url_key`, so two outlets writing the same story at two addresses are two items with `carried_by` 1 each ([backend/idhazh/rank.py](backend/idhazh/rank.py#L441)).

So the owner's instinct is right and the gap is real: **a same-story-different-URL duplicate is fetched, summarised, scored and published today, and the assemble grouping saves not one model call.**

#### The proposed cross-shard dedup worker is refused

| Cost | Figure |
|---|---|
| A runner slot | One more job, plus a 5.29 GiB cache restore if it needs the model |
| Serial position | It cannot start until the slowest shard finishes, so it **adds its whole duration after 135 measured minutes**. It overlaps nothing |
| **What it saves** | **Zero.** By the time every shard has finished, every model call has already been spent |

#### Where dedup belongs: the plan stage, and it must be semantic

**A pure string comparison of titles is refused.** Only syndicated wire copy shares a title. When a significant event happens almost every outlet writes its own headline, so a string match finds the one case that `url_key` already catches and misses the case that matters.

The encoder to do it properly is already a hard dependency. `onnxruntime` is pinned exactly in `pyproject.toml` and measured at **16 ms to embed three summaries** (Windows 11, 8 vCPU, 2026-08-22). Embedding 80 titles-plus-leads is therefore well under a second, needs no model call, and reaches no network.

```
PLAN STAGE, before the safety ceiling and before sharding

  1. candidates <- everything collected today, each with title + feed lead
  2. collapse exact url_key            (this already happens)
  3. vectors <- encode(title + " " + lead[:200]) for each candidate
  4. recent  <- vectors for everything published in the last
                collect.dedup_window_hours (48), read from state/published.csv
  5. for each candidate, in descending rank score:
       a. if max cosine(candidate, kept) >= dedup_similarity_min
            and the match is from a DIFFERENT source
          -> mark as duplicate of the kept item, do not plan it
       b. else if max cosine(candidate, recent) >= dedup_similarity_min
          -> it is a re-run of a story already published; apply
             a recency decay to its score rather than cutting it,
             because a story that developed is not a duplicate
       c. else keep
  6. Editor's rule binds: never cut a desk's only story of the day
  7. write what was cut, and what it was cut against, to the run record
```

| Property | Value |
|---|---|
| Compute at 80 items | 80 x 79 / 2 = 3,160 comparisons plus the 48-hour window. Sub-second |
| Saved per duplicate cut | Roughly 3 to 4 minutes of shard wall clock under the two-call design - **5 percent of a worker's job** |
| Runner slots added | **zero** |
| New config | `collect.dedup_window_hours`, `collect.dedup_similarity_min`, `collect.dedup_decay_half_life_hours` |
| Window maintenance | The 48-hour window reads `state/published.csv`, which the seen prune already bounds at `collect.seen_window_days`. No new retention surface |

**Record-only on the first run**: compute the collapse, log what it would have cut and what it matched against, cut nothing. A cut at plan time is irreversible where the assemble grouping is reversible and visible.

The rate is measurable now with no run: the committed day payloads already carry `also_covered_by`, and that count is the upper bound on what a plan-time cut could save. That is measurement M11.

### 14.3 How quotes are identified today

**They are not.** There is no quote extraction anywhere. `evals/metrics.verbatim_run()` measures the share of the summary's 4-grams that appear verbatim in the source - an **anti-copying** metric - and `summarize.max_verbatim_words` (20) caps how much of the source a summary may echo.

So quote identification is entirely new work, and it is the `quote` element kind: the model names the sentence, code finds it by exact search, and the span proves it. That is why O13's restriction matters - a quote card fires only when the semantic pass identified a genuine attributed statement, never on every article.

### 14.4 Tracing and Langfuse - what ships

**Today, verified against the code on 2026-09-03:**

| Question | Answer |
|---|---|
| Instrumented? | **Yes.** Ten span call sites exist: `ROBOTS`, `ITEM`, `FETCH`, `EXTRACT`, `TAG`, `SUMMARIZE`, `RENDER_PROMPT`, `PARSE_REPLY`, `SCORE`, `ROUTE`, plus a `MODEL_CALL` generation |
| Collecting? | **No, not in CI.** `tracing_enabled` is false, so the sink is `NullSink` and every span is discarded. On a developer box with it on: yes, to `backend/var/traces/` |
| Only the env vars stopping it? | **No - two independent reasons.** Tracing is off at all, and no host is configured |
| Exported to `state/`? | **No** |
| Was that in the previous observability plan? | **No, and it was excluded on purpose.** `TODO/20260830-observability-plan.md` made "a published telemetry column being added" an **ESCALATE trigger**: *"nothing here needs one and a proposal to add one is a separate decision"* |
| Can it work? | **Yes** |

**Why it was excluded then, and why the reason is gone.** That plan narrowed deliberately because four sibling agents held the console files open and a second plan was mid-flight; it also wrote `shard` to `state/item-health/` while explicitly keeping it out of `PUBLIC_COLUMNS` for the same reason. Those plans have all closed - #298, #312, #357, #368, #379, #385. **The separate decision it deferred is this one.**

The cost was already priced in that plan and is trivial: a per-item published trace row is about **140 bytes raw, 0.0214 MiB a day, 0.6 percent of the site's runway**. Carmack also rejected sampling the collection, measuring it at **1 part in 128,000 of a shard - 0.0008 percent**. There is nothing to save by not collecting.

#### Langfuse collects nothing we do not already hold

`_LangfuseSink.emit()` sends `metadata=record` where `record = span.as_record()` - **our own span, unchanged.** It derives exactly two more fields, both from attributes we own: `model` from `AttrKey.MODEL_ID`, and `usage_details` from `INPUT_TOKENS` and `OUTPUT_TOKENS`. `input` and `output` are passed **explicitly as `None`**, because they are the SDK's free-text fields and this repository is public.

**So Langfuse is a rendering of data we already have, not a collector.** Writing our own spans to `state/` yields one hundred percent of what a Langfuse dashboard would show. Langfuse stays as a developer drill-down and is a source of nothing.

#### What spans buy that no ledger column can

| Observation | Why it matters |
|---|---|
| **Unaccounted shard wall clock** - `job_seconds` minus the summed stage times | Named by Andre in the closed plan as *the one thing a span tree would surface that the ledger does not*. If the model is idle for most of a shard, more shards is the wrong lever, and **nobody currently knows that** |
| `robots.txt` read time inside fetch | Whether the first item from a host pays for a slow robots read the next twenty do not |
| Taxonomy tag time inside extract | Whether a taxonomy that grew a hundred patterns is what slowed extraction |
| Prompt-build and verbatim-check time | The two pure-Python costs inside summarize, invisible in `summarize_ms` |

#### What changes

| # | Change | Note |
|---|---|---|
| T1 | `observability.tracing_enabled` -> **true**, **after** T4 exists | Flipping it first writes a file nobody reads |
| T2 | The **file sink stays the only sink CI runs** | No host, no key, no third party. Rule #1 untouched. Langfuse stays available to a developer who names a host |
| T3 | Spans for the new stages: `extract_elements`, `plan_visual`, `compile_visual`, `render_visual`, plus a `model_call` generation per call | Each `SpanName` and `AttrKey` member is added in the commit that emits it |
| T4 | **Raw spans committed to `state/traces/<YYYY>/<MM>/<DD>-<run>-<shard>.jsonl`, on a short rolling window** | A lookup, not a measurement, so by section 9.2's own rule it **deletes rather than folds**. Bounded by construction. Lets the console drill into a recent run |
| T5 | **A per-shard rollup appended to `state/span-rollup/<YYYY-MM>.csv`**, kept and folded at `keep_months` | The trend line. **Not** `state/telemetry-aggregate/`, which is taken by the item-health fold |
| T6 | Every existing eval metric that is not yet on the console gets a panel | O11 |
| T7 | **Widen `publish_telemetry.PUBLIC_COLUMNS` by eight columns** and republish every month | See 14.4b |

Raw traces are **evidence with a short life**; the rollup is **the record**. That split is what satisfies the fourth-record objection while giving an operator something to click into.

#### The one collision, and how it resolves

[docs/concepts/telemetry.md](docs/concepts/telemetry.md) records a rejected alternative: **"Making a span a committed record - a fourth record of the same run, free to disagree with the other three." Authority: Fowler, 2026-08-30.** Committing raw spans would reverse that ruling.

It does not need reversing. **Commit an aggregate, not the spans.** At the end of a shard, fold the span tree into a handful of numbers - time in each stage, count per stage, the model-call token totals - and append that as one row per shard, in the shape `state/runtime-counters.csv` already uses. The raw spans stay in the gitignored file and the two-day artifact.

That keeps the rule the doc is protecting: the ledgers stay the record, a span stays evidence, and there is no fourth record free to disagree - because the committed row is *derived from* the spans rather than being a second account of the same events.

**Rule #11 rides with it unchanged**: the attribute vocabulary is closed, every value is a digest, a count, a flag or a closed name, `telemetry.attribute` refuses a string over 64 characters, and `backend/tests/test_spans.py` plants a sentinel and fails the build if a single character of it reaches an attribute. Turning tracing on does not relax any of that - it makes the guard run on every CI job instead of on a developer's box.

### 14.4a The clearing condition, sharpened

"Derived from spans" is **not** sufficient on its own. `ItemHealthRow` already carries `fetch_ms`, `extract_ms`, `summarize_ms`, `prefill_ms`, `decode_ms`, `input_tokens`, `output_tokens` and `cached_tokens` **per item, per run**. A rollup restating any of those is exactly the fourth record the ruling refused: two code paths computing one number, free to diverge.

> **The committed rollup may carry only what no ledger column holds.**

| | Ruling |
|---|---|
| Committed | Count and duration for **five spans only**: `robots`, `tag`, `render_prompt`, `parse_reply`, `item` |
| **Not** committed | `fetch`, `extract`, `summarize`, `score` durations; any token count; any digest; any id; any per-item cell - item-health holds every one. **And not the visual stages**: `compile_ms` and `render_ms` belong to `state/visuals/` and to no second store (section 12.6) |
| Grain | One row per `(date, run_id, shard, span_name)` - the same shard-by-run grain `state/runtime-counters.csv` uses |
| File | `state/span-rollup/<YYYY-MM>.csv`, contract `SpanRollupRow`, schema stem `span-rollup-row` |
| The test that makes it binding | **Contract tier**: assert the rollup's column set is disjoint, outside the key, from the column set of **every** committed ledger - `state/item-health/`, `state/scores/`, `state/runtime-counters.csv` and `state/visuals/`. Item-health alone is not enough: section 12.6 found a collision in `state/visuals/`, which an item-health-only test cannot see |

**Flipping `tracing_enabled` before the fold exists buys nothing.** The file sink writes into `backend/var/`, which dies with the checkout. Spans in CI with no fold are runner seconds spent writing a file nobody opens. The toggle flips **after** T4 and T5 land, not before.

**"Republish" touches no article data.** `frontend/public/telemetry/<YYYY-MM>.csv` is a projection of the **operational ledger** - one row per planned item per run carrying stage, outcome, failure code and timings. It is rewritten whole on every publish already. Widening it adds columns to that metrics file. No article text, no summary, no payload is regenerated.

### 14.4d The five eval labels, and where they are not shown

These are reader-facing today, one sentence per reason, from [frontend/src/lib/bands.ts](frontend/src/lib/bands.ts#L24):

| `BandReason` | Reader sees | Trigger |
|---|---|---|
| `unsupported_number` | "Our summary gives a figure the article does not." | A number in the summary absent from the source. **Forces `low`** |
| `faithfulness` | "Parts of our summary do not line up with the article." | HHEM below the band threshold |
| `lead_missing` | "Our summary leaves out names or figures from the opening." | `lead_coverage` below `evaluation.lead_coverage_min` (0.3) |
| `hedge_dropped` | "The article is more careful about this than our summary is." | The source hedged; our summary states it flat |
| `not_scored` | "We could not check this summary against the article." | The scorer did not run |

Plus three band labels: `high` "Matches the source" (drawn on no item), `medium` "Mostly matches the source", `low` "May not match the source". **The icon difference is the band, not the reason** - the cross is `low`, the exclamation is `medium`.

**`band_reason` appears nowhere in any console route.** The console shows the band distribution and a doubt count; it has never shown which of the five is driving them, or how that mix moves over time. That is the most actionable eval gap on the project and it is what a prompt loop needs to steer by.

**Consequence for section 16.2: the loop's primary targets are not HHEM.** They are `unsupported_number`, `lead_missing` and `hedge_dropped` - three deterministic, model-free checks that need no scorer, no labels and no judge, and that are computable on committed data today. HHEM is the slow backstop, not the steering wheel.

One instrument to add with them: **a regex cross-check of `unsupported_number` against the source over the committed test set.** That tests the checker rather than the summary, and nothing has ever verified the checker.

**This gap is O34 and it is worth stating on its own.** The five sentences a reader sees on an item have never been plotted anywhere. Today nobody can say whether summaries are getting better, or which of the five defects dominates, or whether a prompt change helped. Every other measurement in this document is downstream of being able to see that.

### 14.4b Telemetry for yesterday's code - the answer is better than expected

**Eight numeric columns are already committed per item per run, and the console has never been shown any of them.** `publish_telemetry.PUBLIC_COLUMNS` is eleven columns wide and stops at `source_words_before_cap`. Everything below is in `state/item-health/` today and invisible to the console:

`fetch_ms`, `extract_ms`, `summarize_ms`, `prefill_ms`, `decode_ms`, `input_tokens`, `output_tokens`, `cached_tokens`

Widening the projection and republishing every existing month from `state/` **backfills the console for every past run, in one commit, with no spans, no package and no new stage.** Every added cell is an integer, so `FORBIDDEN_COLUMNS` and Rule #11 do not move.

| Operator question | Past runs answer it? | From |
|---|---|---|
| How many items failed, at which stage, with which code | Yes, already published | `state/item-health/` |
| Per-item fetch, extract and summarize time | **Yes - console cannot see it** | `state/item-health/`, absent from `PUBLIC_COLUMNS` |
| Per-item tokens read, written and reused from cache | **Yes - console cannot see it** | same |
| What llama-server counted, per shard | Yes | `state/runtime-counters.csv` |
| Processor busy, peak memory, model load time | Yes, since 2026-08-30 | `state/runtime-counters.csv` |
| Faithfulness, band and band reason | Yes, build-time read | `state/scores/` |
| **Time inside the `robots.txt` read, the tag pass, prompt building, the verbatim check** | **No** | **gone forever for every run before the flip** |

Two consequences. **There is no backfill for those five and no invented one is acceptable** - an instrument that did not run writes an empty cell, never a zero. And **the flip date is a discontinuity every new panel must name**, or a sub-step series starting that day, drawn beside a fetch-time series reaching back a year, reads as "robots suddenly got slow".

### 14.5 How a visual is earned

O21 says a visual is earned, never granted. The gate is five machine-checkable conditions, all of which must hold:

1. **Reachability.** A pre-plan predicate proves some choice over this article's elements could survive validation. Below that, **call 2 still runs and still writes the summary; only the plan fields are suppressed** (O43). What is saved is the plan's decode, not the call. The "21 measured seconds" this document used to quote was a saving for skipping the whole call, which cannot happen, so **the figure is withdrawn rather than re-used** - the plan-decode saving is a different number and doc H measures it.
2. **Potential class.** The article's class admits the family. `narrative` admits none.
3. **Validation.** Every element exists, roles match the type, units are compatible, no duplicate element in a role, no literal value, no authored text, every numeral matched.
4. **Novelty.** `information_delta` above its floor - at least one element the summary prose does not already state.
5. **The sufficiency bar.** Legibility floor, density floor, both themes resolve, a caption when present, one annotated mark, no sideways scroll, keyboard route to every fact.

Fail any one and the answer is `none`, and the gate that failed is recorded as `none_reason`, one enum member per gate (section 12.6 G1). `none` remaining common is not a defect.

**And one thing that is deliberately not a gate.** The quality index is a diagnostic and it never gates anything. It stays a diagnostic until the correlation between the machine components and human keep rate is measured - until `information_delta` is shown to predict `visual_keep_rate`, a composite of unvalidated components is a number that looks like a judgement. Row 67 ships the fitter, and the fitter produces weights for a diagnostic. Section 12.7 G9 records that this ban had no sentence in this document before 2026-09-03.

Susan's warning, recorded verbatim in substance: **the proposal measures 33 things about a visual and not one of them is whether a person would choose to look at it.** Every binding gate is integrity or cost, and a plain grey bar chart passes all of them. The sufficiency bar must be a compiler oracle, not a review item - a check a person can skip is the check skipped on the day it would have bitten.

### 14.6 Escalations, resolved

| # | Issue | Resolution |
|---|---|---|
| E1 | Model-assisted labelling vs `CLAUDE.md` section 0a | **Approved (O12), ruled not a deviation (O41).** Section 0a is amended in the same commit with a narrow exception for **quality verdicts on a finished visual** - a model standing in for a human reviewer. **This is not the Tier 2 label a visual draws**, which is Deviation A and was never inside this ban; the two share the word "label" and nothing else. Machine verdicts carry `label_source` and `model_id`, land in a separate ledger, are never pooled with human rows, and never select what publishes. Summary faithfulness labelling stays human-only |
| E2 | `quotecard` vs the republishing non-goal | **Approved (O13).** Restricted to quotes the semantic pass identifies, capped at `summarize.max_verbatim_words`. Not applied to every article |
| E3 | The 18x uncertainty in bytes per day | **Measure before deleting (M2).** No early deletion. `image_months` 13 deletes nothing until 2027-09-17, so it buys time and is not a cap defence. If the pessimistic reading holds, the site hits the cap and **the deploy fails** - the digest stops publishing entirely. Recommendation: take M2 immediately, and land the config-driven asset base URL early so the release valve exists before it is needed |
| E4 | Retention does not protect the Pages cap | **Agreed.** The defences that act on the right timescale are: the coverage rate itself, the per-visual byte cap (row 36), and the off-bundle base URL (section 6). Age-based retention is an archive policy, not a cap defence |
| E5 | **What does an item get when call 2 fails?** No row said. Section 11.4 ruled on `context_exceeded` and on nothing else | **RESOLVED - graceful degradation, and the call structure does not change.** O3's two calls stand. Ruling (Andre, 2026-09-03): `summary` decodes before `visual`; on a reply that hit the output budget, code recovers the closed `summary` object from the returned bytes with `json.JSONDecoder().raw_decode`, publishes the item with that summary and `decision = none`, and records the visual's loss as a `none_reason` - never a `FailureCode`. **The bytes are already in hand.** The cut returns a normal 200, `parse_completion` puts the partial decode in `Completion.content` ([backend/idhazh/llm/server.py](backend/idhazh/llm/server.py#L195)), and `to_summary` discards it unread at [backend/idhazh/summarize.py](backend/idhazh/summarize.py#L385). We lose the summary by choice today, not by constraint. Cost: **zero extra seconds**, no second request, no re-prefill, no field reorder, and no conflict with rows 12, 14 or 17 or with sections 11.1 and 11.3. **What it does not cover, stated plainly:** any failure where the server delivered no body at all - a timeout mid-decode, an HTTP reset, a server crash - because `"stream": False` ([backend/idhazh/llm/server.py](backend/idhazh/llm/server.py#L183)) leaves the completion in the server's memory until the decode ends. Those cost the summary today too, so the merge makes them no worse, and the budget cut is the one failure the merge actually manufactures. Splitting call 2 into two requests would cover them and is the fallback **if** timeouts prove real; nothing measures a timeout rate today, so measure before taking it. Two obligations ship with this: a contract test asserting `summary` precedes `visual` in the generated schema, because the recovery boundary is the property order and llama.cpp's order-preserving grammar is not something we pin; and row 14's alarm stays on the raw `finish_reason` and never on "did the item publish", because an alarm you can satisfy by degrading gracefully has stopped being an alarm |

---

## 15. The plan-doc split

Thirteen plan-docs. The organising principle is **functional isolation over dependency order**: each doc delivers something that works and is worth having on its own, and each owns a disjoint set of files so parallel agents do not collide. Many PRs is fine; overlapping PRs is not.

### 15.1 The thirteen

| # | Plan-doc | Delivers, on its own | Primary files it owns |
|---|---|---|---|
| **A** | **Console owes you telemetry** | Every number already committed becomes visible, for every past run. Eight per-item timing and token columns, the five band reasons plotted over time, faithfulness and lead coverage panels | `backend/idhazh/publish_telemetry.py`, `frontend/src/routes/console/**`, `frontend/src/lib/console/**` |
| **B** | **Developer speed** | A PR runs only the tests it can break; page-weight ceilings get headroom instead of failing reactively | `pyproject.toml`, `backend/tests/conftest.py`, `config/idhazh.json` -> `page_weight` |
| **C** | **The span tree earns its keep** | Tracing on, raw traces on a rolling window, a per-shard rollup, and the first answer to "is the model idle for most of a shard" | `backend/idhazh/telemetry.py`, `contracts/span_rollup.py`, `ledger.py`, `.github/workflows/digest.yml` |
| **D** | **Fewer, better articles** | Feed reliability enters the score, semantic dedup cuts a duplicate before it costs a model call, the run drops to 80 items | `backend/idhazh/rank.py`, `discover.py`, `config/idhazh.json` -> `collect` and `run` |
| **E** | **Retention that actually runs** | `docs/concepts/adaptive-pruning.md`, the compliance register, the cap in config, deletion switched on with a visible backlog | `backend/idhazh/retention.py`, `docs/concepts/adaptive-pruning.md`, `config/idhazh.json` -> `retention` |
| **F** | **Better summaries** | The prompt loop, key points decoded first, per-band key-point caps, the new-fact rate, the regex check on the checker | `backend/idhazh/summarize.py`, `backend/idhazh/prompts/summarize.txt`, `backend/utilities/prompt_loop.py`, `backend/idhazh/evals/metrics.py` |
| **G** | **The element table** | The code-first candidate pass, span-anchored elements of all six kinds, the re-slice invariant, extraction metrics | `backend/idhazh/extract.py`, `contracts/element.py`, `backend/idhazh/elements.py` |
| **H** | **The visual planner** | `visual_planner.py`, the plan contract, the validator, the two-call flow, `n_ctx` 16384 with flash attention, the 4B retired completely, every trace of "route" gone | `backend/idhazh/visual_planner.py`, `contracts/visual.py`, `backend/idhazh/cli.py`, `backend/idhazh/llm/server.py` |
| **I** | **Visuals a reader can read** | Inline SVG, d3, both themes resolving, full-width reflow, the visual moved below the summary, the sufficiency bar as a build gate | `frontend/src/lib/charts/**`, `frontend/src/lib/components/ItemVisual.svelte`, `frontend/src/lib/server/visual-render.ts` |
| **J** | **The vocabulary** | Each visual type, one at a time, each independently shippable | `frontend/src/lib/charts/types/<type>.ts`, one file per type |
| **K** | **The visual is measured** | The section 6.1 telemetry event, `state/visuals/`, `ItemStage.VISUAL`, the console panels that read them | `contracts/visual_telemetry.py`, `frontend/src/routes/console/visual/**` |
| **L** | **Human judgement** | The `review/` harness, paired evaluation, weight fitting, the timed arm | `review/**`, `backend/idhazh/evals/labels.py`, `backend/utilities/review_queue.py` |
| **M** | **The potential classifier** | A denominator for every rate in the system: which visual family an article could have supported, and where it could not, why. Split out of G by O42. Carries the two lexicons, the `date` dependency and the Deviation A question | `backend/idhazh/potential.py`, `contracts/potential.py`, plus the classifier-threshold block it introduces in `config/idhazh.json` |

### 15.2 What each one is worth alone

This is the test that matters. A plan-doc that only pays off when a later one lands is a phase, not a plan.

| # | If nothing else ever ships, you still got |
|---|---|
| A | An operator who can see per-item cost and which summary defect dominates. **Backfilled over every past run** |
| B | A faster PR loop for every future change on the project |
| C | The answer to whether more shards is the right lever |
| D | A better digest from the same runner budget |
| E | A site that does not fill up, and a documented cleanup contract |
| F | Better summaries. **This alone may be the largest reader-visible win in the whole programme** |
| G | A queryable fact table over every article, reusable by search later |
| H | One model instead of two, a 2.33 GiB cache saving, and honest naming |
| I | Charts that are readable in dark mode - today's most visible defect |
| J | One more way to say something. Each type is its own PR |
| K | The ability to tell whether the visual work worked |
| L | Ground truth |
| M | The one number that makes every other rate readable - what was possible. Without it, 4 percent on narrative articles and 4 percent on chartable articles are the same figure |

### 15.3 Dependency edges - only the real ones

```
B ----------------------------------------> (independent, do first, helps all)
A ---------------------------------> K      (K reuses A's console patterns)
C ---------------------------------> K      (K reuses C's ledger seam)
D ---------------------------------> (independent)
E ---------------------------------> (independent)
F ---------------------------------> (independent)
G ------> H ------> I ------> J
                    I ------> K
                              K ------> L
G ------> M ------> J                       (M gates the diagram family, row 46)
          M ------> K                       (M is the denominator, row 56)
```

**Two chains leave G, and only the first is long.** `G -> H -> I -> J` is the build chain: the element table must exist before the planner can point at it, the planner must emit a plan before a renderer can draw it, and the renderer must exist before a type can be added to it. `G -> M` is the measurement branch, and it is short but not optional - M gates J's diagram family (row 46) and supplies K's per-class denominator (row 56). Everything else is independent and can run in parallel from day one.

### 15.4 The hot files, and how the collisions are avoided

**A plan claiming its rows touch different files is a claim, not a fact.** Three files are touched by many docs, and each needs a rule.

| Hot file | Touched by | The rule |
|---|---|---|
| `config/idhazh.json` | B, D, E, H, I, K, M | **Each doc owns a disjoint top-level block.** B owns `page_weight`; D owns `collect` and `run`; E owns `retention` and `observability`; H owns `models` and `visuals`; I owns `ui` and `appearance`; M owns the classifier-threshold block it introduces, and no other. A doc never edits a block it does not own |
| `backend/idhazh/contracts/app_config.py` | same set | **Append-only, one field group per doc, never a reorder.** A rename or a reorder here is what turns a clean merge into a silent revert |
| `backend/idhazh/cli.py` | C, G, H, M | **H owns it.** C, G and M add their call sites through helper modules that `cli.py` imports once. If one of them must edit `cli.py` directly, it serialises behind H |
| `.github/workflows/digest.yml` | C, D, H | **C owns it.** D's change is a config value with no workflow edit; H's job removal serialises after C |
| `docs/concepts/telemetry.md` | C only | C owns the doctrine edit outright |

### 15.4a The hot names

Section 15.4 rules on hot files and says nothing about hot names. That is the larger risk of the two, because section 15 hands thirteen parallel agents a domain with no name table - so thirteen agents mint thirteen names for one thing, and the merge is where that is discovered.

**The register is not the defect.** A decision record that writes `Visual Plan` in every sentence reads like a specification, and this is not one; section 0b asks for the plain register outright. Only the identifiers need binding.

**The rule: the glossary binds identifiers; prose stays free.**

| Surface | Bound? | Rule |
|---|---|---|
| Module, class, function, enum member | **Yes** | The glossary term verbatim, in the casing the language uses: `VisualPlan`, `VisualValidator`, `VisualCompiler`, `TrustedElement`, `element_id` |
| Contract field, schema stem, telemetry value, config key, CLI verb, prompt filename | **Yes** | Same, plus O2 - the word "route" appears in none of them |
| A model's size, vendor or revision, anywhere in an identifier | **Never** | Section 11.0 |
| The prose of a plan-doc, a commit message, a code comment | **No** | Plain register, section 0b. "the validator" in a sentence is correct English and correct here |

Two names this document uses that the glossary does not, recorded so they are not litigated twice. **`visual_planner.py`** is O2 and outranks the glossary, which names the step `Visual Planning` and names no file. **`density_floor`** is row 27, where the owner rejected `structural_efficiency` outright. Every other identifier takes the glossary term.

**A glossary definition that is false does not bind, and there is one.** `Ledger` is defined as "never edited in place", and every fold in section 9.2 rewrites at the window edge. The **term** still binds as an identifier; the narrowed definition in 9.2's correction of 2026-09-04 governs what it means. A plan-doc that finds another such term narrows it in the same way rather than working around it.

Each plan-doc in section 15 cites this table before its first contract row. A doc that needs a domain noun the glossary has no word for names it in its own front matter and says why.

### 15.5 Suggested first wave

Four docs, fully parallel, zero shared files, and every one delivers something on its own:

| Doc | Why it goes first |
|---|---|
| **B** | Cheapest, and it speeds up every doc after it |
| **A** | Zero runner cost, backfills every past run, and gives you the eval visibility the rest of the programme is steered by |
| **D** | Independent, and it frees the runner budget the two-call design needs |
| **F** | Independent, and summary quality is the loudest reader-visible defect that is not the dark-theme chart |

**Deliberately not in the first wave:** G, because it is the root of the only real chain and deserves the attention a wave of four would dilute; E, because `dry_run = false` must land after the new renderer, not before it; and M, which cannot start until G gives it an element table to classify.

**One divergence from the proposal's build order, recorded so it is visible rather than discovered.** The proposal's step 1 is the Trusted Element model, which is doc G, and G is the fifth doc started here. The **dependency** order the proposal sequences is intact - 15.3 keeps G before H before I before J, and a compiler still cannot precede the element table. What changed is the **start** order, on 15.2's worth-alone test: B, A, D and F each pay off with no visual work at all.

---

## 16. Standing questions, answered - round 3

Every row here was asked on 2026-09-03 and is answered against the code, not against the proposal.

| # | Question | Answer |
|---|---|---|
| Q1 | Is the pruning design documented so a coding agent can comply? | **Yes - section 9.** It names five properties (config-driven, atomic, shard-aligned, fused, heuristic-ready), the four policies, the rule that decides which applies (**a ledger folds, an asset deletes, a lookup deletes**), a 14-row compliance register naming every artefact this project writes, and the reason sharding is what makes atomic pruning possible at all. It becomes `docs/concepts/adaptive-pruning.md` with `retention.py` named as the doer |
| Q2 | Is the app made wider and adaptive, reflowing rather than pinned to sizes? | **Yes.** O18 and row 25 retire `visuals.canvas_width`/`canvas_height` as a fixed pair. The visual's box becomes a function of what it encodes and the space available. Row 26 is the counterweight so "wider" never means "unreadable": the smallest drawn string must clear `--text-xs` after the scale-to-fit, at every supported width |
| Q3 | Is max articles per shard config driven, and what value? | **Yes, one knob.** `run.safety_ceiling_per_run` goes 160 -> **80**. `max_parallel` stays 4, so 4 workers x 20 items. `shard_size` does not bind above 20 items a day and is left alone. All three are in `config/idhazh.json` under `run` |
| Q4 | Are new visual-planner KPIs planned - deterministic and model execution, chart generation, failure, justification, degradation? | **Yes.** The canonical telemetry event is proposal section 6.1 and it is adopted whole: `planned_type` and `rendered_type` both recorded, `decision`, `purpose`, `confidence`, `downgrade_depth`, `downgrade_reason`, `downgrade_edge`, `gate_floor_applied`, typed `rejection_reason` and `rejection_stage`, `validation_result`, `allowlist_hits`, the six quality components, the integrity invariants, and the full cost family split by call. Row 54 adds `ItemStage.VISUAL`; row 55 adds `state/visuals/` as the store |
| Q5 | How is a chart earning its place measured? | **Section 14.5** - five gates, all machine-checkable: reachability before the model is asked, potential class, validation, `information_delta` above its floor, and the sufficiency bar. Susan's warning stands: the bar must be a compiler oracle, not a review item |
| Q6 | Where are the two pairwise-testing places? | **Two consumers, one instrument.** (a) Proposal section 5.2.3 - weight learning fits a linear ranking model on pairwise preferences, because absolute ratings are unstable across reviewers. (b) Proposal section 6.3.6 - `REVIEW_MODE = absolute \\| pairwise \\| comprehension`, the reviewer-facing mode that produces those pairs, with D9 and L16 deciding what the second candidate is. Both ship (row 67); Andre and Carmack proposed deferring them and were overruled by O16 |
| Q7 | Is it full scope, no v1? | **Yes.** Section 5 lists twelve deferrals and reverses every one. Section 12 maps all 15 decisions, 35 litigation rows, 20 risks, 10 open questions and every proposal section to a disposition |
| Q8 | Section 1 says code reads first; section 10.1 had the model emit surface strings. Which is it, and would the model hallucinate numbers? | **A real disagreement, and 10.1 held the wrong half.** Settled by O37 and section 10.1a: code extracts every quantity and date with offsets - `numeric_facts()` already does this and ships today - and the model labels them by id. Exact-search adjudication on its own stops an invented number but stops neither a mis-pointed one nor a mis-labelled one; 10.1a names both and shows why neither raises |
| Q9 | Is the document tied to a specific model, and can model-neutral language be kept? | **Yes to both - section 11.0.** Names stay neutral: one config entry holds the weights and no identifier carries a size, vendor or revision. `InferenceConfig` is tuned against whatever `models.summarize` names, from that model's card and this runner's measurements, so every setting in 11.2 and 11.2a is quoted with that entry. The hole - one shared `inference` block, so a swap inherits silently - is recorded and assigned to plan-doc H |
| Q10 | A review says the canonical vocabulary is not used verbatim. Is that a defect? | **Partly, and the half that is gets fixed.** Identifiers are bound to the glossary by section 15.4a; prose keeps the plain register section 0b asks for. The review's real find is the one worth having: 15.4 ruled on three hot files and never on hot names, with thirteen parallel agents about to mint them |
| Q11 | Who finds a number, and who finds an entity? Would the model hallucinate a figure? | **Code finds; the model points and names** - ruled in section 10.1a, drawn in section 10.1b. Close authorship, never close discovery: a quantity is discovered by regex and the model may propose a missed one by naming its sentence for code to re-parse from the article's bytes; an entity name is a Tier 2 grouping key that is never drawn, anchored through per-sentence mentions; a quote or a claim is sentence indices, never text. The model cannot type a figure at all, because no field of the schema accepts one. Two defects in `numeric_facts()` surfaced with the ruling - corrections C14 and C15: the `(value, unit)` dedup collapses a figure repeated across two periods, which is the series a trend chart exists to show, and there is no date extractor at all |
| Q12 | Is every box in the proposal's section 1.2 diagram covered, and are its pass and fail states emitted to the console? | **Two audits, both in section 12.** Section 12.6 checks **presence**: every box, every plan field, all eight validator checks and all seven model responsibilities are covered, and *assess visual need*, *choose the form* and *select elements* are the contracted fields `decision`, `purpose` plus `type`, and `element_ids`. Six gaps found and assigned, G1 to G6. Section 12.7 walks the **tail** from the validator fork to the end and checks intent rather than presence, finding five more, G7 to G11. The serious one is G7: `state/visuals/` was specified as a per-publication ledger, which would have left every refusal uncommitted and stopped the machine loop being auditable while it was still the gate |
| Q13 | Does this document contradict itself anywhere? | **In four places, all resolved - section 12.8.** The full-vocabulary rule was cancelled by its own amendment and took row 48 with it; "flat role map, all keys required" could not be reconciled with P.D4's per-type role sets; section 1 printed the slogan the proposal had already narrowed; and O2 renames a **persisted** contract with no migration attached, which `CLAUDE.md` section 11 makes a release blocker. A fifth finding was a hole rather than a contradiction, and the most serious of the five: **no row said what an item gets when call 2 fails.** Resolved as E5 without touching the call structure - the summary is recovered from the bytes the cut already returns, and the item publishes with `decision = none`. **A second review on 2026-09-04 found four more, in section 12.9**: the `state/visuals/` fold has no group key, two build-failing invariants are unruled while a coverage row cites the ruling for a third, the build order's named console panel is in no panel list, and P.7.1.1's pairing rule survives as instances rather than as a rule |

### 16.1 How "6 sources said this" is counted today

**Two different counts exist and they mean different things.** Both are already semantic where it matters.

| Field | What it counts | How | Where |
|---|---|---|---|
| `carried_by` | Syndication of **one address** | `merge()` groups candidates by `url_key`. Exact match only | [backend/idhazh/rank.py](backend/idhazh/rank.py#L441) |
| `also_covered_by` | **Other sources telling the same story** | Cosine similarity over the embedding vectors the day payload already carries, weakest-link clustering at `assemble.duplicate_similarity_min` = 0.94, **across sources only** | [backend/idhazh/assemble.py](backend/idhazh/assemble.py#L375) |

The reader-facing sentence fires at `carried_by >= 2`. Two properties of `also_covered_by` are deliberate and documented in the code: a group is **always across sources**, because one outlet publishing twice is a different problem with a different control; and the encoder is least trustworthy on same-source text, where two press releases from one desk score 0.9867 against each other and are two different documents.

So the semantic machinery already exists and is well reasoned. What it does **not** do is run early enough to save a model call - it runs at assemble, over vectors that only exist after summarisation. That is exactly the gap section 14.2 closes.

### 16.2 Improving the prompts - the iteration loop

The owner wants a loop that writes a prompt, judges it, iterates about three times, and commits the winner - for the summarizer, the visual planner and the extraction pass.

**This needs a rule amendment and the amendment is narrow.** `CLAUDE.md` section 0a bans LLM-as-judge: *"a judge that shares the failure modes of the thing judged is not a measurement."* That ban is about **evaluating published output**. Using a model to critique a **prompt** at development time, offline, with a human committing the result, is a different act - nothing it produces reaches a reader, and its output is a candidate prompt that then faces the existing deterministic evals.

| Element | Ruling |
|---|---|
| Scope of the amendment | Extends O12's exception to cover **offline prompt iteration**. Still banned: an LLM judging a published summary, a published visual, or anything that selects what publishes |
| Where it runs | `backend/utilities/`, on a developer machine or a manual dispatch. **Never in the daily pipeline** |
| The loop | Write a candidate -> critique against a rubric -> revise -> repeat, bounded by `finetune.prompt_iterations` (3) |
| Two judges, not one | A model judge **and** the Editor persona rubric. A single judge that shares the writer's failure modes is the thing section 0a warns about; two disagreeing judges surface it |
| **The gate is deterministic, not the judge** | A candidate prompt only wins if it beats the incumbent on the **existing deterministic scorers** over a frozen article set. **The primary targets are `unsupported_number`, `lead_missing` and `hedge_dropped`** - see 14.4c - because all three are model-free, need no labels, and are computable on committed data today. `verbatim_run` and the new-fact rate join them. HHEM is the slow backstop, not the steering wheel. The model judge proposes; the deterministic suite disposes |
| Frozen set | The committed canary corpus, so the comparison is reproducible and touches no network (Rule #7) |
| What is committed | The winning prompt, the rubric, the scores of every candidate, and the seed. Not the transcripts |
| Word limits | The owner's instruction stands: **do not add hard word limits to the rubric.** `summarize.bands` already sizes prose by source length; the rubric judges whether a line earns its place, not how many words it has |

### 16.3 Other llama-server settings worth testing

Two beyond the settings table in 11.2a. Both are **candidates, not rulings** - neither has been verified against the pinned build b10598, and `server_argv` is the only place a flag may be spelled (Rule #6), so each needs a config field before it can be tried.

| Candidate | What it would buy | Why it is not a ruling |
|---|---|---|
| Partial prefix reuse on a cache miss | Today a prefix either matches or the prompt re-prefills whole. Partial reuse would salvage the shared head when only the tail differs - which is the exact shape of two items sharing one system prompt | The flag name and its behaviour on b10598 must be read from `llama-server --help` on the pinned build, not from memory |
| Slot save and restore to disk | The system prompt is re-prefilled once per shard at startup. Persisting the warmed slot would remove that cost from every shard after the first | Same verification, plus it interacts with `--no-context-shift` and would need a measurement, not an assumption |

What is already known and needs no flag: **prefix caching is working.** `prompt_tokens_cached_total / prompt_tokens_total` is 0.72 to 0.90 across 29 shard rows. The two-call design is built to keep it that way, and row 11's `cached_tokens` assertion is what proves it did.

### 16.4 Room left in the model budget

Halving the day from 160 items to 80 roughly halves the base model work per shard. Section 10.6 spends about 140 output tokens of that on extraction signals - **12.5 minutes of shard wall clock at 20 items** against a margin measured at 78.5 minutes median and 135.4 minutes worst against a 150-minute timeout.

| Candidate use of the remaining margin | Verdict |
|---|---|
| The five accepted extraction signals in 10.6 | **Taken.** 140 tokens, 12.5 min |
| A self-critique pass on the summary, same call | **Worth testing after 16.2.** If the prompt loop fixes the restatement rate, this is unnecessary; if it does not, this is the next lever |
| Question-answer pairs for later retrieval | **Not in call 1.** The only candidate that asks the model to author rather than find. A third call on a sampled subset, or nothing |
| Raising `truncation_cap_tokens` above 5,000 | **Only after M2.** More article read is more summary quality, and it is the single largest quality lever nobody has pulled - but it is also linear in prefill, which is 63 percent of model time |
| More items instead | Refused by O6. The owner chose depth over count, and Editor's row 52 governs which items are lost |

**The honest framing: the margin is not spare, it is the buffer that absorbs a slow host.** The worst measured shard used 90.3 percent of its timeout. Spend the margin on quality per item, not on filling it.

### 16.5 Summary evaluation - what exists, what is published, what is missing

There is a real eval suite. It is better than the console shows.

| Instrument | What it measures | Where |
|---|---|---|
| HHEM-2.1-Open | Faithfulness, on CPU, locally, at a pinned revision | [backend/idhazh/evals/hhem.py](backend/idhazh/evals/hhem.py) |
| `verbatim_run` | Share of the summary's 4-grams appearing verbatim in the source - the anti-copying counterweight | [backend/idhazh/evals/metrics.py](backend/idhazh/evals/metrics.py#L224) |
| `hedge_dropped` | A rumour becoming a fact. A faithfulness scorer cannot see this | same |
| `lead_coverage` | Whether the summary covers the article's own opening | same |
| `unsupported_number` | A figure in the summary that is not in the source | same |
| `ConfidenceBand`, `BandReason` | The published verdict and **why** it was reached | [backend/idhazh/evals/score.py](backend/idhazh/evals/score.py) |
| `faithfulness_floor` | A qualification gate, and it refuses to score if the instrument was not pinned | [backend/idhazh/evals/qualify.py](backend/idhazh/evals/qualify.py#L500) |
| leaderboard vs measured | Whether HHEM performs here as its leaderboard claims | [backend/idhazh/evals/validation.py](backend/idhazh/evals/validation.py) |

**What is missing is not instruments - it is the projection.** `publish_telemetry.PUBLIC_COLUMNS` is eleven columns wide and carries **no eval column at all**. The band distribution and the doubt readout reach `/console/model/` through a build-time read of `state/scores/`; nothing eval-related reaches the runtime viewport the console fetches.

| Gap | Fix |
|---|---|
| Eight per-item timing and token columns invisible to the console | Widen `PUBLIC_COLUMNS`, republish every month - section 14.4b |
| No eval column in the published projection | A second projection over `state/scores/` with the same forbidden-column guard |
| No key-point redundancy metric anywhere | New-fact rate, section 10.5. Baseline 11 of 89, 12.4 percent |
| No visual-stage metric at all | Rows 54, 55 and the proposal's section 6.1 event |
| Nothing measures whether pursuing a visual degraded the summary | `summary_faithfulness` and `summary_informativeness` reported beside the visual metrics - row 64 |

### 16.6 Committed size and growth - the measurement that must be exact

Bytes per published day is the number four decisions rest on, and the two available readings differ by **18x**. It is measurement M2 and it is one command.

What the measurement must record, so it cannot be misread later:

| Field | Why |
|---|---|
| Built-bundle bytes and payload-tree bytes, **separately** | Measured 2026-08-27 they were 128,064,853 and 7,027,075 - a ratio of 18.2, and it was 21 the day before. One cannot stand in for the other |
| Bytes by top-level directory | One moving sum cannot say whether visuals grew or telemetry did |
| Published item count in the **same** tree | Pairing a byte total with a count from a different tree is the whole lesson of `retention.py` |
| Bytes per published item | The stable unit. The day rate moved by a factor of six across seven days while the item rate held at 24,378 with a spread of 23,066 to 26,538 |
| Repository pack size | M10. The prune bounds history; it does nothing about a growing present |
| Two dates, differenced | A level is not a rate, and only a rate answers "when" |



- [`20260902-yen-idhazh-visual-planning-architecture.md`](20260902-yen-idhazh-visual-planning-architecture.md) - the proposal this record disposes of, section by section.
- [`../CLAUDE.md`](../CLAUDE.md) - the engineering contract. Sections 0a, 0b, 6, 9, 11, 13 and 14 are load-bearing throughout.
- [`../docs/agents/guardrails.md`](../docs/agents/guardrails.md) - the authority table behind every ruling in section 4.
- [`../docs/how-to/author-a-plan.md`](../docs/how-to/author-a-plan.md) - what section 15's plan-docs must become before they can be executed.
