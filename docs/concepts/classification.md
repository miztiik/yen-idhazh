# Classification

**Last Updated**: 2026-09-13

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

## The encoder alarm: a number that labels nothing

The pipeline already encodes every published item - the headline and our
summary - into a 384-dimension vector, so a reader can search a day on their own
device. `config/taxonomy-vectors.bin` holds one vector for each label the
vocabulary still offers, encoded from the same words a model would be asked to
choose against. Once a day, the run asks each item's vector how close it sits to
the closest of those label vectors, and writes the day's spread of that answer
onto `state/day-metrics/<YYYY>/<MM>/<DD>.json`.

**It is allowed under [`../../CLAUDE.md`](../../CLAUDE.md) section 0a, and here
is the reason written down so nobody has to work it out again.** The number
reaches no reader: it lands on an operator record and never on a page a reader
opens. It selects nothing: no item is ordered by it, held back by it or
published because of it. It picks no label - the closest label is worked out and
thrown away, and nothing anywhere records what one item scored. That is a model
verdict that reaches no reader and selects nothing to publish, which section 0a
permits. **The day it starts choosing anything, it is a classifier and it needs
everything a classifier needs.**

**Neither end of the number is better than the other.** A day at 0.34 is not a
better day than one at 0.31, and nobody can say which way is good. The cosine
between an item vector and a label vector is uncalibrated - one encodes a news
sentence and the other a definitional one - so a fixed threshold would be a
number somebody picked rather than a fact. Only a change means anything, and a
day file cannot hold a change: it holds the level, and comparing days is
somebody else's job.

**What a change has to beat, measured rather than guessed.** Over the 23
committed days - 8,266 item vectors, Windows 11, 8 vCPU, 2026-09-13, under
`config/taxonomy.json` version 2026-09-12 - the day mean ran from **0.1870 to
0.2324**, a spread of **0.0455**, and the step from one day to the next had a
median of **0.0124** and a worst case of **0.0357**. Those steps are the day's
own story mix moving, not the encoder. Under them sits the rounding floor: both
sides are stored as int8, which shifts the reading by a median of **0.0017** and
at worst **0.0062** against the same comparison done in full precision. So the
noise floor is about seven times smaller than ordinary day-to-day movement,
which is what leaves room for a real change to show - and any firing rule has to
clear roughly **0.036**, the worst ordinary step, before it is saying anything.

**Say what it actually moves on, because the name oversells it.** The encoder
weights are committed and digest-checked, and the pooling, the quantisation and
the text that gets encoded all have tests. On any green day the only live input
is our own writing - so this moves when summaries get longer, when the
summariser's register drifts, or when more items reach the encoder's reading cap.
Read a shift as a question about the summaries first and the encoder second.

**A stale vectors file is the one way this can be wrong, so it is the one way it
is allowed to fail.** The file's header carries the digest of exactly the label
sentences that were encoded and the reference of the weights that encoded them.
A run whose committed file names a different vocabulary, or different weights,
stops and names the file. Comparing today's items against last month's lenses
would produce a number that looks exactly like a real one, and a quiet wrong
number is worse than a loud failure. A file that is simply **absent** is not
stale: the day records no reading and publishes as it always did.

**It costs a run nothing.** No encoder pass, no byte on an item, no vector added
to a day payload. The label vectors are 4,224 bytes committed once, and the item
vectors were going to be written anyway. Rebuild the file with
`python backend/utilities/build_taxonomy_vectors.py` after any edit to an active
vertical or lens, and after the encoder weights move.

**There is no knob, and that is deliberate rather than an omission.** The
vocabulary is already config, so editing `config/taxonomy.json` and rebuilding
changes what is measured. The width, the quantisation and the text template are
contract rather than tuning: a run comparing today's items against vectors built
under a different template is silently meaningless, which is the same failure the
stale-file refusal exists to stop. The knobs that will be needed - how many days
a change has to hold and how far it has to move before anybody is told - belong
to whatever surface draws the series, because both are properties of a
comparison and this record carries no comparison.

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

**Why the label vectors are committed rather than encoded each run.** Eleven
sentences change only when somebody edits the vocabulary, so encoding them on
every runner on every run is repeated work for an identical answer. 4,224 bytes
of vectors plus an 83-byte header is the whole cost, it is derived from
`config/taxonomy.json` exactly as that file is written by hand, and it sits in
`config/` rather than `state/` because `state/` is what a run appends and this is
what a person commits.

**Why the reading is the closest label rather than the disagreement with the
desk.** Counting items whose nearest vertical is not the feed's desk would
compute a label for every item and then throw it away - a classifier with only
the write suppressed, and the machinery is what needs a classifier's gates.
It also reads as an error rate, and a change detector with a good end becomes a
target. The closest-label reading has no good end and no pick to suppress
(Andre, 2026-09-13).

**Why the display name is encoded in front of the definition.** Seven of the
eleven display words do not appear in their own definition - `ai` spells out
"artificial intelligence" and never says AI, `cyber` says "an attack on a
computer system", `chips` says "semiconductors" - so the definition alone drops
the most distinguishing word the vocabulary has. It also gives both sides of the
comparison one composition rule: the item side is "headline. summary" and the
label side is "name. definition", so a change to either is a change to both.

## See also

- [taxonomy.md](taxonomy.md) - what a vertical, a desk, a lens and an event are, and how they differ.
- [../architecture/publishing/frontend.md](../architecture/publishing/frontend.md) - how each mark is drawn, and the cap on how many an item may carry.
- [../architecture/sources/discovery.md](../architecture/sources/discovery.md) - why a lens and an entity never get a feed list of their own.
- [../architecture/sources/trust-boundary.md](../architecture/sources/trust-boundary.md) - why fetched text is data and never instruction.
- [digest.md](digest.md) - what a published day holds.
- [../../CLAUDE.md](../../CLAUDE.md) - section 0a (what a model verdict may decide) and Guardrail #11 (fetched text is data).
