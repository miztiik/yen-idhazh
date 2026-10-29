# Classification

**Last Updated**: 2026-10-29

Every label this project puts on an article: what the word means, who decided
it, and whether a reader ever sees it.

[taxonomy.md](taxonomy.md) is the companion and the two do not overlap. That
page answers **what the vocabularies are** - vertical, desk, lens, event, and
how they differ. This one is the register: **for each label an item carries,
where the value came from and what happens to it.**

## A classification is a label, not a grade

Everything on this page says something about the **article**. Nothing on it
ranks a publisher, scores a summary or decides what publishes.

That line is this page's own scope, not a contract rule.
[`../../CLAUDE.md`](../../CLAUDE.md) section 1a now makes LLM-as-judge primary
evaluation: a model verdict may run in a production workflow, may score live
content, and may determine publication. None of that happens here. **A label
says what a story is about; it never decides whether the story runs.**

Where a label does reach a reader it reaches them as a word about the article,
never as a judgement of the newsroom. The practical test is the `announcement`
mark: it tells a reader the organisation in the story is the one talking, which
is a fact about the piece. It is one edit away from reading as a verdict on the
publisher, and one false positive on real reporting would cost every other mark
on the page its credibility.

## The register: what an item carries today

The feed declares the article's source vertical. The work stage uses configured
semantic comparison groups to assign the desk and supported taxonomy labels;
the curated phrase tagger remains the explicit fallback if valid classification
encoding fails.

| Field | Vocabulary | Who decided it | What a reader sees |
| --- | --- | --- | --- |
| `vertical` | `verticals` in `config/taxonomy.json` | the feed that carried the item, through `FeedDef.vertical` | the desk heading, and the item's own address |
| `desk` | active vertical definitions in `config/taxonomy.json` | the article classifier, when the configured confidence and ambiguity rules allow one | the desk heading |
| `source_kind` | `SourceKind`, a closed enum | the feed's own declaration in `config/sources.json` | a mark on four of the six kinds, and nothing on the other two |
| `lenses` | active entries in `config/taxonomy.json` | the article classifier, with phrase tags as the encoder-failure fallback | a tinted chip the item earned, in one wrapper |
| `events` | active entries in `config/taxonomy.json` | the article classifier, with phrase tags as the encoder-failure fallback | **nothing** |
| `entities` | active organisation entries in `config/watchlist.json` | the article classifier, requiring a configured name or alias as evidence | **nothing** |

The article classifier uses a local encoder and configured comparison text; it
does not ask a prompt to name a lens or event. The article's sanitized title and
body are compared with configured target descriptions. Feed vertical remains
the identity and provenance of the source; semantic assignment never rewrites
it. On an encoder failure only, the deterministic phrase tagger remains a
fallback. `entity` also appears in
`backend/idhazh/prompts/label_article_elements.txt`, as the field naming what a
number in the element table is about. Different word, different job.

**Two of the five reach no reader at all.** `events` and `entities` are matched,
stored, versioned and schema-gated, and `FORBIDDEN_FIELDS` in
`frontend/src/lib/payload/project.ts` strips both out of the published day
payload. That is a cost carried knowingly rather than a defect: it is written
down here so the next person meets it as a decision rather than as a surprise.

How each mark is drawn - the chip, its tint, the four-child cap above the title,
and why `reporting` and `analysis` carry no mark - is
[../architecture/publishing/what-a-story-shows-and-where-each-fact-sits.md](../architecture/publishing/what-a-story-shows-and-where-each-fact-sits.md).
This page does not restate it.

## The rules a label obeys, and what each one is protecting

**1. The vocabulary is config, never code.** One JSON file holds the id, the
display name, the definition sentence and any weight. Change the sentence and
the next run labels against it: no Python edit, no schema regeneration, no
release. The schema bounds the shape and never the words
([taxonomy.md](taxonomy.md)).

**2. The definition text is the label.** An id and a display name tell a model
nothing, so what a word means is the sentence committed beside it. Anything
measured against the old sentence is stale the day the sentence moves, which is
why a measurement records the version of `config/taxonomy.json` it was taken
under.

**3. Nothing is derived from an id or a display name.** Measured 2026-08-26 over
1,889 published items, deriving lens terms from the id tagged 88.2 percent of
them, because `ai` sits inside `said`. A rule that cannot be stated in the
vocabulary file has to be written in it.

**4. Label the exceptions, never the rule.** A mark that appears on nearly every
item is wallpaper by item four, and a mark that is wallpaper warns nobody about
anything. This is why the two commonest source kinds carry no mark at all.

**5. Describe who is talking, never what is missing.** "Unverified" describes an
absence; an absence is somebody's fault; a reader decides the fault is the
publisher's, and the mark becomes a verdict on a newsroom. "The company's own
account" describes a presence. Same warning to the reader, and no blame.

## Recorded is not rendered

A label can exist on the payload, be committed, be versioned and schema-gated,
and render nowhere. `events` and `entities` are in that state today.

That is the safe starting state for a label rather than a failure of one. A mark
on the reading page is a claim we are making to a reader, and the evidence for
making it is a distribution somebody has looked at - which cannot exist until
the label has been recorded for a while. So the order is: record, read the
numbers, then decide whether a reader is better off seeing it.

**The reverse order has a name and it is the failure mode this section exists to
prevent**: a mark shipped on the day the field was added, drawn on a distribution
nobody had seen, on an item where it happened to look right.

## Independent classification encoding configuration

`classification_encoding` in `config/idhazh.json` controls semantic assignment
independently of `assist`, which controls archive search. It declares its own
model revision, assets, digests, width, token limit, encoding modes, comparison
groups and assignment thresholds. The current declaration points to the same
committed model bytes as search, but neither settings nor defaults are shared.

Each comparison group names a JSON source, one entry list, the identity field,
ordered text fields, exact-match filters and a destination. Text fields accept
strings or string lists; lists are flattened in order and joined with `. `.
Sources are fixed paths in config, not discovered directories. Active vertical
definitions feed desk assignment, active lenses and events feed their own fields,
and active organisation entries from the watchlist feed entity assignment. A
`comparison_only` group may provide an additional comparison set without writing
an article field. Adding a group requires configuration only when its source fits
the declared descriptor shape and its destination is already supported.

At the start of a work run, the consumer validates each configured source and
encodes each selected target once. After extraction sanitizes fetched text, each
article is encoded and compared with all groups in memory. The desk destination
may set `article.desk`; it never changes `article.vertical`, which remains the
feed's identity. Lens and event destinations assign configured ids above their
own thresholds. Entity assignment also requires literal evidence from a
configured name or alias; topical similarity alone cannot prove which named
organisation appears in a story. The existing phrase tagger remains the explicit
fallback when a valid encoder fails during target or article encoding. Invalid
configuration, missing assets, bad digests, or malformed source entries fail
with a named validation error instead of looking like an empty classification.

The configured similarity floors and ambiguity margins are provisional estimates
from a small local comparison, not measured accuracy. Keep them independent per
group and treat them as tunable policy, not as claims about classifier quality.
The consumer stores no target vectors, article vectors, scores or comparison
matrices. Vectors exist only in the consuming process. New day-metrics records
omit the retired `label_similarity` diagnostic; the optional field remains in
the read contract for existing historical records. Historical state is not
rewritten or deleted.

## Design rationale

**Why keep classification settings separate from search.** The same model bytes
can serve both jobs, but changing a search limit or model must not silently
change article assignment. Separate declarations make each behavior reviewable
and independently evolvable.

**Why compare targets once per work run.** Configured taxonomy text changes only
when its source changes. Holding the corresponding vectors in the work process
avoids repeating encoder work for every article without creating a persistent
cache, a generated artifact or a stale-vector rebuild step.

**Why named entities need literal evidence.** Similarity to an organisation
profile says that a story is about a related industry, not that it names that
organisation. A configured name or alias supplies the identity evidence; the
similarity and ambiguity rules only help choose among evidenced candidates.

**Why the score thresholds are estimates.** The initial floors and margins are
conservative starting values from a bounded local comparison. No labelled
reference set establishes their accuracy, so they are not reported as measured
quality. A future change to them should follow the evidence gathered for the
specific assignment decision.

**Why new day records omit comparison diagnostics.** Comparison scores are used
to decide configured article fields during the consuming run. Persisting a
separate daily aggregate adds no input to that decision and would retain a
second, non-reader-facing measure with no demonstrated use.

**Test scope for this change.** The maintainer directed that these two changes
add no tests or tooling. Existing affected expectations may be updated; this
ruling is limited to this work and does not change the general test policy.
## See also

- [taxonomy.md](taxonomy.md) - what a vertical, a desk, a lens and an event are, and how they differ.
- [../architecture/publishing/what-a-story-shows-and-where-each-fact-sits.md](../architecture/publishing/what-a-story-shows-and-where-each-fact-sits.md) - how each mark is drawn, and the cap on how many an item may carry.
- [../architecture/sources/discovery.md](../architecture/sources/discovery.md) - why a lens and an entity never get a feed list of their own.
- [../architecture/sources/trust-boundary.md](../architecture/sources/trust-boundary.md) - why fetched text is data and never instruction.
- [digest.md](digest.md) - what a published day holds.
- [../how-to/measure-a-classifier.md](../how-to/measure-a-classifier.md) - how the reference dataset behind an accuracy figure is built, and what makes that figure still mean something a month later.
- [../../CLAUDE.md](../../CLAUDE.md) - section 1a (what a model verdict may decide) and Guardrail #11 (fetched text is data).
