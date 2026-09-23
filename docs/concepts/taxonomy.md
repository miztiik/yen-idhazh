# Taxonomy

**Last Updated**: 2026-09-23

The words this project puts on a story, and which word answers which question.

> A **vertical** says which feed carried the story. A **desk** says where the
> day published it. A **lens** says what else it is about. An **event** says
> what happened. One vertical an item, one desk, any number of lenses, any
> number of events.

That sentence is the whole page in short. The rest says who decides each word,
what changing one costs, and what a model is told each word means.

| Word | How many an item | Who decides | What it changes | Where the list lives |
| --- | --- | --- | --- | --- |
| Vertical | exactly one | the feed that carried the item (`FeedDef.vertical`) | the item's address, and whether that vertical's feeds are asked at all | `verticals` in [`../../config/taxonomy.json`](../../config/taxonomy.json) |
| Desk | exactly one | nothing yet - it falls back to the vertical | the heading, the pill and the topic route a reader finds the story under | the same list |
| Lens | zero or more | the item's own words, against curated terms | a rank bonus, and a chip on the item | `lenses` in the same file |
| Event | zero or more | the item's own words, against curated terms | nothing a reader sees | `events` in the same file |

## A vertical is a partition, and it is the only one

Every item has exactly one vertical and it is not optional. A feed declares its
vertical in [`../../config/sources.json`](../../config/sources.json), and every
article that feed carries inherits it. Two things then hang off that one word:

- **The item's address.** `Article` refuses an `item_id` that does not begin
  `<vertical>-`, so the vertical is part of the identity rather than a label
  beside it. That is also why the vertical can never be repointed at a reading
  of the article: repointing it would reject, at read time, every item whose
  desk moved.
- **Whether that vertical's feeds are asked at all.** `min_feeds` is a floor on
  how many of its addresses a run may lawfully ask - 35 for `ai` and 21 for the
  other four, in the committed config today. Below the floor it **plans nothing**
  rather than thinning out: `rank.plan_vertical` returns an empty list, the run
  succeeds, the digest publishes, and that section is simply absent.

A lens and an event carry none of that. Neither has a feed list, neither is in
an address, and neither decides whether anything runs. That is the difference
worth holding: **the vertical is a place, and the other two are remarks.**

## A desk is where the day published the story

The vertical is the feed's word about itself. The desk is where the story is
read: it decides the heading, the pill, and the `/<date>/<desk>/` route.

**They are two fields and one vocabulary.** `DigestItem.desk` sits beside
`DigestItem.vertical`, and both take an id out of the same `verticals` list. A
null desk is the ordinary state and means nothing has read the article; a page
falls back to the vertical, and a null is never read as a desk of its own.
Nothing fills the field today - the run that will is a later row.

**A story may have one more claim, and it is a claim rather than a filing.**
`DigestItem.secondary_desk` is the one other desk the same reading named, and it
takes an id out of the same list again. It is where the day sends a story whose
desk is over its ceiling, and after such a move the two swap, so the story keeps
its claim on the desk it left. It never equals the desk the day filed the story
under, so a story names at most two desks. No page draws it yet and both counts
below still answer for the desk a story is filed under
([placement.md](placement.md#what-the-number-on-a-pill-promises)).

**Two counts, because the two words count different things.**
`DigestVerticalRef.count` is stories whose carrying feed declares this vertical,
and `desk_count` is stories the day publishes under the name. A page draws
`desk_count` and falls back to `count`; the three shortfall fields -
`considered`, `too_old`, `below_feed_floor` - stay beside `count`, because
collection is per feed and a feed declares a vertical rather than a desk. Every
day published before 2026-09-12 carries neither `desk` nor `desk_count`, which
is exactly the fallback case.

**A desk under its own floor is not a place a story may be moved to.** The floor
counts feeds, so a vertical below it plans nothing and renders nothing. A story
relabelled onto that name would render under a heading the same day's payload
flags as having planned nothing, so `rank.desk_of` sends it back to the word its
feed declared. The rule in one line: **the floor is about supply, and supply is
collected per feed.**

## A lens is a question asked of items already collected

A lens costs no extra request. It is a theme that cuts across the desks - China,
chips, trade - and an item carries as many as its words earn.

A lens is assigned when one of its curated terms appears in the item's words as
a whole-word phrase, case-folded ([`../../backend/idhazh/tag.py`](../../backend/idhazh/tag.py)).
Nothing is derived from the id or the display name, and that clause is
load-bearing: deriving terms from the id was measured on 2026-08-26 over 1,889
published items and moved lens coverage from 8.8 percent to 88.2 percent,
because `ai` sits inside `said`, `remains` and `chair`. One unstated choice moved
the answer tenfold and turned a filter into noise.

`LensDef.weight` is the one thing a lens can do besides label: it adds to a
story's rank when one of its terms is in the headline. Zero is the default and
the answer for most lenses. A weighted lens must be an **under-carried** theme -
the bonus rescues a story one outlet has and nobody has repeated, and on a theme
every wire already carries it only compounds a lead repetition gave.

## An event is what happened, and no reader sees one

An event is matched exactly as a lens is and carries no weight. `release`,
`funding`, `incident` and the other six say what kind of thing occurred.

**Nothing renders one.** `FORBIDDEN_FIELDS` in
`frontend/src/lib/payload/project.ts` strips `events` out of the published day
payload, so the vocabulary is matched, stored and versioned and reaches no page.
That is a known cost carried on purpose rather than an oversight, and it is
written here so nobody rediscovers it as a bug.

## The definition text is the label

An id and a display name tell a model nothing. `research` means whatever
sentence sits next to it, so every entry carries a `definition`: one plain
sentence saying what an article has to be for this word to fit.

**It is config.** Edit the sentence in
[`../../config/taxonomy.json`](../../config/taxonomy.json) and the next run
labels against the new text. No Python changes, no schema regenerates, nothing
is released. The schema bounds the **shape** - which keys are there, the id
pattern, the sentence's length - and never the words. Enumerating the members in
the schema would make adding a word a schema change and a release, which is the
state this vocabulary spent weeks in.

`Taxonomy.definition_block()` renders the sentences, and it is the only thing
that does - so a prompt built from it cannot carry a word this file does not.
The vocabulary's own order is kept: a model asked to pick from a list is not
indifferent to the list's order, so the order is a committed fact rather than
whatever a dictionary iterated to that day.

**Two bounds, and both have a reason rather than a taste behind them.**

- **240 characters a sentence.** A definition is about 26 tokens: the 20
  committed today are **512 tokens** together, and the block they render into -
  headings, ids and display names included - is **636**. Measured 2026-09-12
  with `llama-tokenize` against the pinned `Qwen3-8B-Q4_K_M`; tokenization is
  deterministic, so there is no spread, and two runs returned 636 both times.
  240 characters is roughly twice the committed average: room to sharpen a
  sentence, not room for a paragraph. The bound matters because a labelling
  prompt has to carry every sentence it labels against, so the block is a cost
  paid on every such request.
- **An offered entry must carry one.** A word put in front of a model with no
  sentence beside it is a word it cannot read, so `Taxonomy` refuses a taxonomy
  whose active entries are not all defined.

**Changing a sentence has a cost, and it is not the run.** Every figure measured
against the old text is stale from that day. A measurement records which version
of this file it was taken under for exactly that reason, and a stale figure is
marked rather than deleted - the comparison between a number taken before a
definition sharpened and one taken after is the interesting one.

## Draft, active, retired: what reaches a prompt

`status` is a control rather than a convention, and `definition_block` is where
it is enforced.

| Status | In a prompt | On a page | What it means |
| --- | --- | --- | --- |
| `draft` | no | no | The word exists in the file so a person can read it in context. Nobody has approved it |
| `active` | yes | yes | A person committed it, and it carries its definition |
| `retired` | no | yes, on a day that already carries it, under its own display name | A tombstone. The word stops matching and stops being offered, and `retired_on` says when |

A draft contributes no byte at all - not a heading, not a blank line - which is
asserted by writing a sentence onto a draft entry and requiring the rendered
block to be unchanged. `is_auto_discovered` says a model proposed the entry
rather than a person writing it, and the marker survives promotion: a word that
arrived from an article read six weeks ago reads exactly like one a person
chose, and the difference is the first thing anybody asks when a label looks
wrong.

**A retired id is tombstoned, never deleted.** The precedent is committed and
already paid for: `ai-roi` was retired on 2026-08-30 rather than removed, so the
days that carry it stay valid. Deleting an id rewrites what a published day said.
Since 2026-09-12 the contract no longer makes deletion impossible, so this is a
rule a person keeps rather than one the type keeps for them - and
[Every id is an open slug](#every-id-is-an-open-slug-and-the-vocabulary-is-this-file)
says what the page does on the day somebody breaks it.

## Science and Climate, and the eight lines that decide them

Two desks and one lens arrived on 2026-09-14, all three as **drafts**: committed,
defined, offered to nobody. They exist because twenty people labelling 641
articles independently reported the same holes - a science desk (13 of the 20), a
climate desk and lens (11), and four more nobody has built yet. Roughly one
article in five had been filed on a desk that named nothing about it, mostly
absorbed by `business-economy` as a shrug.

**They are drafts because no feed declares either word.** `min_feeds` is 21 and
the supply is zero, so an active desk would publish nothing while claiming a
page - which is the failure `test_every_vertical_clears_its_own_feed_floor` was
written to catch. The `climate` lens carries no keywords for the mirror reason:
keywords would start tagging published items before anybody chose to. Promotion
is a person adding feeds, or keywords, and flipping one word.

**The eight tie-breaks below are the interesting part, and every one of them came
from a labeller who hit it and could not resolve it from the definitions alone.**
A definition is capped at 240 characters and has to be short enough to score a
model against; these are the sentences that did not fit.

1. **A single disaster is `world`, not `climate`.** A flood, a storm, a wildfire
   or a heatwave reported as an event - casualties, rescue, damage - is `world`.
   It is `climate` when the piece is about the climate behind it.
2. **`science` is the study; `climate` is the warming.** For an earth or life
   science piece: if the method or the finding is the news, `science`. If warming
   or habitat loss is the cause the piece is about, `climate`.
3. **Research in any field is `science`** - economics, mathematics, archaeology,
   psychology, as much as physics or biology. **And the news has to be the
   finding**: a study used as evidence in a country story leaves the story where
   it was. That second half is rule 2 generalised, and it is what stops `science`
   swallowing most foreign reporting.
4. **A paper about a computational or statistical model is `ai`, whatever it is a
   model of** - a weather model, a glucose model, an earth-observation model. A
   physical model is not one; a Hamiltonian is physics.
5. **A quantum result or experiment is `science`; a quantum product, acquisition
   or funding round is `business-economy`.** Finding or deal.
6. **Chemical pollution, waste, plastics and land-use disputes are not
   `climate`.** The desk covers greenhouse gases, warming and the living world.
   There is no environment desk, and three separate labellers asked for one.
7. **Air pollution is not greenhouse gas.** A particulate or smog story is a
   health or policy story unless carbon is the subject.
8. **How power is made, priced or financed stays `energy`**, even framed as
   decarbonisation. A net-zero target is `climate`; a gigawatt of solar is
   `energy`. Equally both, keep `energy` and add the `climate` lens.

**A lens never repeats its own desk.** `climate` on the `climate` desk is a chip
that says what the page already says, and by the fourth item it is wallpaper. The
lens marks a warming thread running through a story that is mainly about
something else, which is what makes it worth a chip at all. Three of six
labellers asked; this is the answer, and the lens definition now carries it.

**What is still missing, named rather than left to be rediscovered.** No desk
covers health or medicine outside research, crime and courts, culture or sport,
consumer technology, or the environment when it is not warming. Each was asked
for by more than one reader. Adding a desk is a config edit; deciding a desk is
not, and nobody has.

## What changing the vocabulary costs

| Change | Cost |
| --- | --- |
| A definition sentence | A config edit, and the label-vector rebuild in the last row. The next run uses it |
| A display name | A config edit. The id is what payloads carry, so nothing is orphaned |
| A vertical | A config edit, **and an icon**. Every vertical needs `frontend/src/lib/icons/svg/topic-<id>.svg`, because a topic pill builds its icon id from the config - `frontend/tests/icons.spec.ts` resolves the set against this file and fails naming any id nothing draws. Adding `science` and `climate` on 2026-09-14 turned that test red, which is the test working |
| A lens id or an event id | A config edit: since 2026-09-12 these are open slugs too. A lens needs its display name in `frontend/src/lib/payload/lenses.ts`, which a contract test checks in both directions |
| Retiring any of them | `status` and `retired_on` in config. The id stays, and so does its name |
| Deleting one outright | A config edit, and every published day that carries the id starts showing the id itself in place of the name. Retire instead |
| Any of the above that reaches an **active** vertical or lens | One thing more, every time: rebuild and commit `config/taxonomy-vectors.bin` with `python backend/utilities/build_taxonomy_vectors.py`. Its header pins the exact label sentences that were encoded, and until it is rebuilt the next run **stops and names the file**. An event, and an entry that was already retired, reach none of this |

**That last row is a tripwire, not a build step, and nothing but a person can
clear it.** The refusal is the right failure, because a stale file compares
today's stories against last month's lenses
([classification.md](classification.md#the-encoder-alarm-a-number-that-labels-nothing)).
But it only tells somebody to go and type a command, and the day a fit moves a
word there is nobody to tell.
[../architecture/publishing/autotune-desk-assignment.md](../architecture/publishing/autotune-desk-assignment.md)
owns that gap, and the published search index has the same one.

## Every id is an open slug, and the vocabulary is this file

A lens id and an event id were closed Python enums until 2026-09-12, so adding
or retiring a word meant editing `backend/idhazh/contracts/taxonomy.py`,
regenerating four schemas and cutting a release. That is the opposite of the
rule this page opens with, and it is why the lens vocabulary had not moved.

**What closes the vocabulary is this file, and it always was.** Nothing can
invent a label: [`../../backend/idhazh/tag.py`](../../backend/idhazh/tag.py)
returns keys of the mapping it is handed, and the only mapping the pipeline
hands it is built here - so a hostile page can win itself a word we already
publish and can never mint one (Guardrail #11). The Python type was a second copy of
that guarantee, and a second copy is what drifts.

**What the open type buys is that a frozen day still reads.** A closed type
refuses a payload whose word this file has since stopped carrying, so the only
safe way to remove a lens was never to remove one. An open slug reads it, which
is what makes `status` a real choice rather than the only choice.

**A published day is never edited by a vocabulary change.** Measured 2026-09-12
over the 22 committed days and 8,922 items, `ai-roi` is carried by 18 of them -
12 on 2026-08-27, 3 on 2026-08-28 and 3 on 2026-08-29 - and until that day the
page rendered none of the 18, because the reading side dropped any id it could
not name. It now keeps the id and shows:

| What config holds | What the chip says |
| --- | --- |
| An active entry | Its `display_name` |
| A retired entry | Its `display_name`, unchanged. A tombstone stops matching new items; it does not un-say an old one |
| No entry at all | The raw id, `supply-chain` rather than a blank. It is deliberately ugly: it is only reachable once somebody deletes a word a published day still carries, and the alternative is a day quietly saying less than it said |

The id a chip falls back to is our own committed slug and never fetched text,
so this is the same move `Sources` already makes for a retired feed - a
tombstoned `source_id` that stops resolving shows its slug rather than
relabelling the item.

## Design rationale

**The closed enum was a second copy of the vocabulary, and it was the expensive
one.** `LensId` and `EventType` were `StrEnum`s until 2026-09-12, which made the
Python type and `config/taxonomy.json` two places one list of words lived. The
type never protected anything the file did not already protect - the matcher can
only return a key of the mapping this file builds - and it charged a code change,
four regenerated schemas and a release for a word. What it did protect was the
wrong thing: it made DELETING an id impossible, which reads as safety and is
really the closed type refusing to read a day it can no longer name.

**What that cost was paid in silence, which is why it took a measurement to
find.** The reading side dropped any id it could not name, so the 18 committed
items carrying the retired `ai-roi` each rendered one chip fewer than their own
payload held, and no test, no gate and no schema said so. A rule stated as "a
tombstone can never return to the page" sounds like restraint; what it did was
edit three published days.

**An id is immutable and a display name is not.** Payloads carry the id, so
renaming what a reader sees never orphans a day written under the old label.
That split is why a rename is a config edit rather than a migration.

**Nothing is derived from an id or a display name.** The measured cost of the
obvious shortcut is in the lens section above: 88.2 percent of items tagged,
because `ai` is a substring of ordinary English. A matching rule that cannot be
stated in the file has to be written in it.

**The definition text is config, and that is a choice with a name.** The
alternative is a prompt template carrying the words, which puts the vocabulary
in two files that drift, and makes every wording change a code review rather
than a config edit. The property that matters is testable and is tested: change
one sentence, and the block the prompt is built from changes, with no Python
edit and no schema regeneration.

**The schema gates shape only.** Listing the members would mean adding a word is
a schema change, a regeneration and a release. A vocabulary that expensive to
move does not move, which is the state the lenses were in for weeks.

## See also

- [glossary.md](glossary.md) - the other half of the vocabulary: the words for the machinery that runs, rather than the words put on a story.
- [classification.md](classification.md) - what a label on an article is, where each one comes from, and what a reader sees.
- [../architecture/publishing/autotune-desk-assignment.md](../architecture/publishing/autotune-desk-assignment.md) - **every definition, floor, ceiling and feed minimum here is a person's judgement, and nothing measures whether it still draws the line a reader would.** That page is where a fitted boundary would be argued; it is a stub today.
- [feed.md](feed.md) - what a feed is, and where it declares its vertical.
- [digest.md](digest.md) - what a published day holds.
- [config.md](config.md) - every tunable knob, including the ones named here.
- [../architecture/sources/discovery.md](../architecture/sources/discovery.md) - how a vertical's feeds are chosen and weighted.
- [../architecture/contracts/schemas.md](../architecture/contracts/schemas.md) - how a contract becomes the committed schema.
- [../../config/taxonomy.json](../../config/taxonomy.json) - the vocabulary itself.
- [../../backend/idhazh/contracts/taxonomy.py](../../backend/idhazh/contracts/taxonomy.py) - the shape it has to fit.
- [../../CLAUDE.md](../../CLAUDE.md) - Guardrail #6 (no hardcoding) and section 11 (schema versioning).
