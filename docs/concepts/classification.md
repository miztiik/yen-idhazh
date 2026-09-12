# Classification

**Last Updated**: 2026-09-12

Every label this project puts on an article: what the word means, who decided
it, and whether a reader ever sees it.

[taxonomy.md](taxonomy.md) is the companion and the two do not overlap. That
page answers **what the vocabularies are** - vertical, desk, lens, event, and
how they differ. This one is the register: **for each label an item carries,
where the value came from and what happens to it.**

## A classification is a label, not a grade

Everything on this page says something about the **article**. Nothing on it
ranks a publisher, scores a summary or decides what publishes.

That line is not a preference, it is
[`../../CLAUDE.md`](../../CLAUDE.md) section 0a. A model verdict that reaches no
reader and selects nothing to publish is not a deviation from it. Two things
stay refused whatever else is true: a model may not grade a published summary or
a published visual, and a model may not select what publishes. **A label says
what a story is about; it never decides whether the story runs.**

Where a label does reach a reader it reaches them as a word about the article,
never as a judgement of the newsroom. The practical test is the `announcement`
mark: it tells a reader the organisation in the story is the one talking, which
is a fact about the piece. It is one edit away from reading as a verdict on the
publisher, and one false positive on real reporting would cost every other mark
on the page its credibility.

## The register: what an item carries today

Every label below is decided **without a model**. One comes from the feed's own
declaration; the rest come from the article's words matched against curated
terms.

| Field | Vocabulary | Who decided it | What a reader sees |
| --- | --- | --- | --- |
| `vertical` | `verticals` in `config/taxonomy.json` | the feed that carried the item, through `FeedDef.vertical` | the desk heading, and the item's own address |
| `source_kind` | `SourceKind`, a closed enum | the feed's own declaration in `config/sources.json` | a mark on four of the six kinds, and nothing on the other two |
| `lenses` | `lenses` in `config/taxonomy.json` | the item's words, whole-word and case-folded | a tinted chip the item earned, in one wrapper |
| `events` | `events` in `config/taxonomy.json` | the same matching rule | **nothing** |
| `entities` | `config/watchlist.json` | the same matching rule | **nothing** |

**No model labels anything on this page today.** No prompt this pipeline sends
names a lens or an event, and every label above is either a feed's declaration
or a deterministic string match. A bare search is not clean and the reason is
worth recording: `entity` does appear in
`backend/idhazh/prompts/label_article_elements.txt`, as the field naming what a
number in the element table is about. Different word, different job.

**Two of the five reach no reader at all.** `events` and `entities` are matched,
stored, versioned and schema-gated, and `FORBIDDEN_FIELDS` in
`frontend/src/lib/payload/project.ts` strips both out of the published day
payload. That is a cost carried knowingly rather than a defect: it is written
down here so the next person meets it as a decision rather than as a surprise.

How each mark is drawn - the chip, its tint, the four-child cap above the title,
and why `reporting` and `analysis` carry no mark - is
[../architecture/publishing/frontend.md](../architecture/publishing/frontend.md).
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

## Design rationale

**Why a register page at all.** The words are defined once in
[taxonomy.md](taxonomy.md) and drawn once in
[../architecture/publishing/frontend.md](../architecture/publishing/frontend.md),
and neither answers the question somebody actually arrives with: *this word is
on this item - who put it there, and can I trust it?* That question crosses a
config file, a matcher, a payload and a component, so it has no home in any of
them.

**Why the five rules sit here rather than beside each label.** Four of the five
were argued once and then re-argued per label, because nothing wrote them down
where a person adding a label would meet them. A rule restated in five places
drifts in five directions.

## See also

- [taxonomy.md](taxonomy.md) - what a vertical, a desk, a lens and an event are, and how they differ.
- [../architecture/publishing/frontend.md](../architecture/publishing/frontend.md) - how each mark is drawn, and the cap on how many an item may carry.
- [../architecture/sources/discovery.md](../architecture/sources/discovery.md) - why a lens and an entity never get a feed list of their own.
- [../architecture/sources/trust-boundary.md](../architecture/sources/trust-boundary.md) - why fetched text is data and never instruction.
- [digest.md](digest.md) - what a published day holds.
- [../../CLAUDE.md](../../CLAUDE.md) - section 0a (what a model verdict may decide) and Guardrail #11 (fetched text is data).
