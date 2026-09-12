# Taxonomy

**Last Updated**: 2026-09-12

The words this project puts on a story, and which word answers which question.

> A **vertical** says where the story lives. A **lens** says what else it is
> about. An **event** says what happened. One vertical an item, any number of
> lenses, any number of events.

That sentence is the whole page in short. The rest says who decides each word,
what changing one costs, and what a model is told each word means.

| Word | How many an item | Who decides | What it changes | Where the list lives |
| --- | --- | --- | --- | --- |
| Vertical | exactly one | the feed that carried the item (`FeedDef.vertical`) | the item's address, the page it renders on, and whether the desk runs at all | `verticals` in [`../../config/taxonomy.json`](../../config/taxonomy.json) |
| Desk | exactly one | the same feed, today | the heading a reader sees | the same list |
| Lens | zero or more | the item's own words, against curated terms | a rank bonus, and a chip on the item | `lenses` in the same file |
| Event | zero or more | the item's own words, against curated terms | nothing a reader sees | `events` in the same file |

## A vertical is a partition, and it is the only one

Every item has exactly one vertical and it is not optional. A feed declares its
vertical in [`../../config/sources.json`](../../config/sources.json), and every
article that feed carries inherits it. Three things then hang off that one word:

- **The item's address.** `Article` refuses an `item_id` that does not begin
  `<vertical>-`, so the vertical is part of the identity rather than a label
  beside it.
- **The page.** A day's stories are published per vertical at
  `/<date>/<vertical>/`.
- **Whether the desk runs at all.** `min_feeds` is a floor on how many of that
  vertical's addresses a run may lawfully ask - 35 for `ai` and 21 for the other
  four, in the committed config today. Below the floor the desk **plans nothing**
  rather than thinning out: `rank.plan_vertical` returns an empty list, the run
  succeeds, the digest publishes, and that section is simply absent.

A lens and an event carry none of that. Neither has a feed list, neither is in
an address, and neither decides whether anything runs. That is the difference
worth holding: **the vertical is a place, and the other two are remarks.**

## A desk is a vertical as a reader meets it

`desk` is the word this repository uses for a vertical on the day's page -
`DigestVerticalRef`'s own docstring opens "One desk of the day". Today the two
words name one thing decided by one decider: the feed declares a vertical, and
the page renders it as a desk.

They are one list of words whichever way the label arrives, which is why the
vertical vocabulary is what the model would be offered if it were ever asked to
read the article and name a desk. Nothing asks it today.

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
| `retired` | no | yes, on a day that already carries it | A tombstone. The word stops matching and stops being offered, and `retired_on` says when |

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

## What changing the vocabulary costs

| Change | Cost |
| --- | --- |
| A definition sentence | A config edit. Nothing else, and the next run uses it |
| A display name | A config edit. The id is what payloads carry, so nothing is orphaned |
| A vertical | A config edit: the id is an open slug |
| A lens id or an event id | A code change and a schema regeneration - both are closed Python enums today |
| Retiring any of them | `status` and `retired_on` in config. The id stays |

## Design rationale

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

- [classification.md](classification.md) - what a label on an article is, where each one comes from, and what a reader sees.
- [feed.md](feed.md) - what a feed is, and where it declares its vertical.
- [digest.md](digest.md) - what a published day holds.
- [config.md](config.md) - every tunable knob, including the ones named here.
- [../architecture/sources/discovery.md](../architecture/sources/discovery.md) - how a vertical's feeds are chosen and weighted.
- [../architecture/contracts/schemas.md](../architecture/contracts/schemas.md) - how a contract becomes the committed schema.
- [../../config/taxonomy.json](../../config/taxonomy.json) - the vocabulary itself.
- [../../backend/idhazh/contracts/taxonomy.py](../../backend/idhazh/contracts/taxonomy.py) - the shape it has to fit.
- [../../CLAUDE.md](../../CLAUDE.md) - Rule #6 (no hardcoding) and section 11 (schema versioning).
