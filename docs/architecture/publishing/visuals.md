# Visual routing and rendering

**Last Updated**: 2026-08-22

How an item gets a chart, a diagram, or - most of the time - nothing at all.

The rule this subsystem serves is in [`../../concepts/digest.md`](../../concepts/digest.md): a
visual must carry a fact the sentence beside it does not. A picture that decorates is worse than
no picture, because the product is trust and an invented axis label costs it permanently.

## The stage runs on its own model, in its own pass

Routing is a separate CLI stage from `work`, not a step inside it:

```
idhazh work  --date <D>    # the 8B summarizes
idhazh route --date <D>    # the 4B routes and renders
idhazh assemble --date <D> # the day payload picks up whatever routed
```

One llama-server serves one set of weights, and classification is the easy task, so the router
runs on Qwen3-4B while the summarizer keeps the 8B. Splitting the stage also means **a run that
never starts a router still publishes.** Every item simply carries no picture, which is already
the common and correct answer.

## The model never writes a number

This is the whole safety design, and it is structural rather than instructed.

1. The extractor pulls every quantity out of the article text with a regex, and gives each one an
   index and a unit.
2. The model is shown that indexed menu and asked to choose bars **by index**.
3. The spec is built here in Python from the chosen indices.

A chart value that is not in the article is therefore unreachable, not merely unlikely. The Row #8
oracle - "every value in a rendered chart is present in the source article" - is a property of the
shape rather than a hope about the prompt, and the test asserts it directly.

## What the extractor drops, and why

| Dropped | Reason |
| --- | --- |
| A bare four-digit integer in 1900-2100 with no unit | It is a year. A year is a label, not a bar height. Dropping it costs nothing, because a label is a free string the model can still write. |
| A number preceded by a hyphen after a word character | `COVID-19`, `GPT-4`, `Qwen3-4B`. Identifiers, not quantities. |
| A magnitude of a bare `m` or `k` | `15 m` is fifteen metres or fifteen million. The model never writes a number, but the extractor does, and a guess here is a one-million-fold error on a published bar. The spelled-out words and the unambiguous `bn`/`mn`/`tn` are kept. |
| Anything at or below 2 with no unit | A list marker. `2 percent` keeps its unit and survives. |
| A repeat of the same value **in the same unit** | One figure quoted in a lead and a body paragraph is one fact. Twelve percent and twelve people are two. |

The menu is capped at `visuals.max_facts` (default 16). A long indexed list is lost-in-the-middle
for a small model choosing an integer.

## Two controls that run after the model has answered

**Bars must measure the same thing.** The largest group of chosen bars that share a unit is kept
and the rest are dropped. This never invents a bar and never mixes units; it only ever removes. If
what remains is below `visuals.min_chart_points`, the item routes to nothing.

**A caption written about dropped bars is discarded.** If any bar was removed, the model's caption
described a chart that no longer exists.

## Rendering runs without a browser

| Kind | Persisted spec | Renderer |
| --- | --- | --- |
| `chart` | Vega-Lite JSON | `vl-convert`, the Vega toolchain compiled as a Rust extension |
| `diagram` | Mermaid source | ours, about a hundred lines of SVG layout |
| `image` | - | **descoped 2026-08-23 on measurement.** Unreachable: `visuals.enabled_kinds` does not name it. |

**Why there is no image renderer.** Measured on `ubuntu-latest` (4 vCPU, 16 GB),
2026-08-23, run `32654562728`: `Tongyi-MAI/Z-Image-Turbo` at bfloat16 loads in
159.2 s at 9.2 GB resident, then spends **527 s per denoising step** at 512x512.
Nine steps is about **79 minutes for one image** - longer than the whole `route`
job's 60-minute bound, and about 196 hours for a 149-item day against a 6-hour
job limit. The job was cancelled at step 7 of 9 and never reached 768px or a byte
count. The plan's second candidate, `alpha-vllm/Anima-2.9B`, answers 401
Repository Not Found: it does not exist. Reducing steps does not rescue it -
three steps is still 26 minutes, and one step is noise. Rule #2 says the budget
is the platform, so the feature goes rather than the budget. The `image` member
stays in the enum because a payload must be able to say it; the config gate is
what makes it unreachable.

Both write SVG into `frontend/public/digest/<YYYY>/<MM>/<DD>/<vertical>-<NN>.svg`, beside the
payload that references them. A render failure records why and the item publishes without a
picture. No failure path raises.

Measured 2026-08-22 (Windows 11, 8 vCPU, `vl-convert-python` 1.9.0.post1): a Vega-Lite render takes
2568 ms for the first call in a process and 49 ms warm, and produces about 7 KB of SVG. The cold
cost is engine boot, paid once per run rather than once per item.

## Design rationale

**Why the model picks an index instead of writing a spec.** The obvious design is to ask the model
for a Vega-Lite object. It is also the design where a hallucinated axis value is one sampling
accident away, and where the only defence is checking the output against the article afterwards -
a check that has to parse an arbitrary spec and decide which of its numbers are data. Indices
invert that: the model's entire numeric vocabulary is `0..len(facts)-1`, a bound check is two
lines, and the property holds for specs nobody has thought of yet.

**Why our own SVG for diagrams rather than Mermaid's own renderer.** `mermaid-cli` drives a
headless Chromium. That is roughly 300 MB of install and seconds per render, on a runner with a
6 h budget, to draw a chain of labelled boxes for perhaps one item in ten. The Mermaid source is
still what gets persisted, so the record is portable and anyone can re-render it with the real
toolchain. What we decline to do is ship a browser to lay out six rectangles.

**Why every field of the model's reply is required, including the empty ones.** A field with a
default is absent from the schema's `required` list, and a constrained decoder emits exactly what
`required` forces. On the first live run the model returned a confident `kind` of `chart` with no
bars in it, twice, because `points` was optional. Required-and-empty is the honest shape.

**Why `reason` is decoded before `kind`.** Pydantic emits properties in declaration order and
llama.cpp builds its grammar in that order, so **field order is decode order**. With `kind` first
the model committed to an answer and then filled `reason` by copying the prompt's own rules back -
observed live, verbatim. With `reason` first, one plain sentence about the item grounds the choice
that follows.

**Why the prompt states no base rate.** The first prompt said "Almost always it does not", "the
right answer roughly two times in three", and "When in doubt, choose none". At `temperature=0`
there is no sampling to recover from a shifted argmax, so a stated prior becomes a deterministic
flip rather than a nudge. The rewrite keeps `none` as the common answer by making it the terminal
branch of an ordered test, which reaches the same place without leaning on the logits.

**Why the feed floor of one prompt rule became two code controls.** "Do not chart a year" and "do
not chart quantities that measure different things" were requests. A request is negotiable by a
4B reading an article that mentions years. Both are now enforced - the first in the extractor, the
second after the model answers - and the prompt is shorter for it.

## Rejected alternatives

| Option | Why rejected |
| --- | --- |
| Ask the model for a Vega-Lite spec directly | A fabricated axis value becomes reachable, and verifying it afterwards means parsing an arbitrary spec to work out which numbers are data. |
| Diffusion for charts | Produces a beautiful picture of a chart with hallucinated axis labels. |
| A charting library in the renderer | `vl-convert` takes a spec to PNG or SVG with no browser and no runtime JavaScript. |
| `mermaid-cli` for diagrams | A headless Chromium to lay out a linear chain of boxes. |
| PNG or WebP for charts and diagrams | A bar chart is a dozen paths. The vector is smaller than any raster of it, stays sharp on a phone, and costs the retention budget less. Raster stays the right answer for a photographic image. |
| Discard the whole chart when one bar disagrees on units | Observed live: the model picked three correct year-on-year megawatt bars and appended the sector headcount. Three good bars thrown away to reject one bad one. |
| Route on the 8B | Classification is the easy task. The big model belongs on summarization, and a second set of weights would not fit the pass anyway. |
| Keep `image` out of the enum until it is built | A payload must be able to say `image`, and the four-way vocabulary is a contract. The gate belongs in config, so switching it on is an edit rather than a schema change. |

## See also

- [`../../concepts/digest.md`](../../concepts/digest.md) - the visual rule this serves.
- [`../sources/trust-boundary.md`](../sources/trust-boundary.md) - why article text is data.
- [`../contracts/determinism.md`](../contracts/determinism.md) - why decoding is pinned in one place.
- [`../../concepts/evaluation.md`](../../concepts/evaluation.md) - how a stage gets measured.
