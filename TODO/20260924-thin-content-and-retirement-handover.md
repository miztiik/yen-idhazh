# Handover: thin content should influence whether a feed is retired

**Last Updated**: 2026-09-24

Non-authoritative working material (CLAUDE.md section 3). Nothing here is a
decision except where it says the owner already made one.

## The intent

**A source that keeps sending near-empty articles should lose standing for it.**
Owner instruction, 2026-09-24. "Thin content should influence
`collect.source_quality_auto_retire`."

Half of that shipped. The other half is a measured finding that the shipped half
does almost nothing, and a choice about what to do with that. Read the whole
page before touching anything: the obvious next move is the wrong one.

## What already landed

Branch `short-articles-stop-publishing`, commit `f08422ae5`. **Committed
locally, not pushed, no pull request.** The first job is to decide whether that
commit ships as it stands.

| id | Change | Where |
| --- | --- | --- |
| A1 | `extract.reject_too_short` turns on, so a body under the 60-word floor stops publishing | [config/idhazh.json](config/idhazh.json) |
| A2 | `too_short` leaves the source-neutral set, so a rejected stub counts against its feed's yield | [backend/idhazh/contracts/item_health.py](backend/idhazh/contracts/item_health.py) |
| A3 | `counts_against_source` reads the row's outcome before its code, so anything that reached the digest costs its feed nothing | [backend/idhazh/contracts/item_health.py](backend/idhazh/contracts/item_health.py) |
| A4 | Corpus harvest follows the knob rather than being exempted from it; the tests that fill the bottom length band now build it through a feed declared `abstract` | [backend/tests/test_corpus.py](backend/tests/test_corpus.py), [backend/tests/conftest.py](backend/tests/conftest.py) |

A3 is what keeps A2 honest. A feed a curator registered as publishing abstracts
still publishes its short items, so its rows stay `ok` and it is still charged
nothing - which is the whole reason that registration exists.

Source yield is the number the dwell reads, and the dwell is what
`source_quality_auto_retire` acts on. So after `f08422ae5`, thin content already
reaches the retirement decision. **The wiring is done. The question is whether
it carries any current.**

## The finding that changes the job

**Simulated against the 31 days to 2026-09-24: the new charge pushes exactly one
feed under the alarm point, and that feed is already retired.**

`lemonde-en` goes from 1.000 yield to 0.000 on 164 charges. Every other feed
stays where it was. No live feed moves at all.

The reason is arithmetic, not a defect. Over that window only **37** thin
articles came from feeds that are still active, spread across **17** feeds, none
losing more than **5** in the month. The alarm needs 30 decisions at under 50
percent yield. Five thin articles against a month of ordinary publishing is
nowhere near it.

**Read that as the mechanism working rather than failing.** A feed that breaks
in bulk - `lemonde-en` sent 154 stubs - is caught hard and immediately. A feed
that occasionally publishes a short piece is not punished for it. Whether that
is the behaviour the owner wanted is the open question, and it is theirs to
settle, not yours.

## The decision to put to the owner

Ask in one message using the CLAUDE.md section 0c shape. Do not pick for them.

| id | Option | What it costs | What it gives up |
| --- | --- | --- | --- |
| B1 | Ship `f08422ae5` as it stands and stop | Nothing. Thin content reaches the retire decision and catches a feed that collapses. | Teeth against a feed that is merely mediocre. |
| B2 | Give thin content its own threshold, separate from general yield | A second dial to reason about, and a second way to retire a feed nobody reviewed. | Simplicity. Two thresholds means two things that can be set wrong. |
| B3 | Teach `feed_reliability` to read item quality, not just feed availability | A real design change. It is the 0-to-1 factor that multiplies every feed's ranking weight, so it touches every feed's placement, not just a retirement. | The most work of the three. Also the only one that gives a middle setting. |
| B4 | Also turn `source_quality_auto_retire` on | One line. See the separate finding below. | Nothing measurable, but it is a distinct decision and must not be bundled. |

**B3 is the one worth explaining properly**, because it is what the owner was
reaching for when they asked whether the system is binary. Today there are four
levers on a source and only one of them can see article quality:

| id | Lever | Shape | Sees article quality? |
| --- | --- | --- | --- |
| C1 | `feed_reliability`, a 0-to-1 factor scaling the feed's rank weight, floored at `reliability_floor` | Graded. A weak feed quietly wins fewer slots. | **No.** It counts whether the RSS read returned entries. |
| C2 | Quarantine: `availability_strikes_before_rest` then `availability_rest_runs` | Temporary, lifts itself | No. It counts whether the address answered. |
| C3 | Source yield to dwell to retirement | Binary and sticky | **Yes**, and only since `f08422ae5` |
| C4 | `max_per_source`, `max_source_share_per_day`, `tier_weights` | Fixed ceilings a curator sets | No |

So quality can currently produce exactly one outcome: eventual retirement. B3 is
the work of making quality produce a gradual one instead.

## A separate finding, not part of this job

`collect.source_quality_auto_retire` is still `false`, and the loop behind it has
never retired anything - [state/feed-retirements.csv](state/feed-retirements.csv)
holds a header and no rows.

Its evidence floor is met: 30 complete days against a minimum of 30. Turning it
on would retire **one** feed, `openai-news`, on **2026-09-25**. That feed
published 0 of 71 decided items over 30 days - 99 `http_client_error`, 3 not
attempted, zero successes. It was un-retired on 2026-09-06 after a probe found
articles returning, and has delivered nothing since. The `ai` desk keeps 53
feeds against a floor of 35, so no desk goes under.

Nothing else is close. `straitstimes-opinion` is 1 day into a dwell that would
end 2026-10-06 and publishes 38 of 103, its failures being `paywalled`, which is
arguably a fact about the source rather than a fault. `finshots-daily` has 3
decisions against a floor of 30 and cannot be retired.

This is row B4 above. It is a one-line config change and it is reversible - a
curator un-retired this same feed once already.

## Verified facts, 2026-09-24

Numbers in this repository go stale in days. Re-check every one before building
on it. Each row carries the command that settles it.

| id | Fact | How to re-check |
| --- | --- | --- |
| D1 | Band 0 of `summarize.bands` is `min_source_words: 0`, so it IS the under-60-word band that the knob empties for ordinary feeds | `python -c "import json;print(json.load(open('config/idhazh.json'))['summarize']['bands'][0])"` |
| D2 | `nber-new` is the only feed declared `abstract`, and it supplied none of the 196 thin articles in the window | `python -c "import json;print([f['id'] for f in json.load(open('config/sources.json'))['feeds'] if f.get('form')=='abstract'])"` |
| D3 | `corpus_shortfalls` records a missing tier and never blocks a run | read the docstring in [backend/idhazh/evals/qualify.py](backend/idhazh/evals/qualify.py) |
| D4 | Of 15,646 committed item-health rows, none are charged to a source while having reached the digest, so A3 moved no code but `too_short` | walk `state/item-health/**` for rows where `outcome == "ok"` and the code is outside `SOURCE_NEUTRAL_FAILURE_CODES` |
| D5 | 196 thin articles published in 31 days, 159 of them from three already-retired hosts | walk `state/item-health/**` for `code == "too_short"`, group by `source_id`, cross-check against the `retired` list in `config/sources.json` |
| D6 | The dwell axis is complete: 30 of a minimum 30 days | read `days_under_the_mark` and `complete_dates` in [frontend/public/source-health.json](frontend/public/source-health.json) |

**Take these measurements with a throwaway script under `backend/var/` and
delete it before running any gate.** `mypy` lints that tree despite
`.gitignore`, so a leftover scratch file fails the type check. Do not add a test
that walks the committed archive - CLAUDE.md section 13 forbids it, and
Guardrail #12 is why.

## Traps that cost time on this branch

| id | Trap | What it looks like |
| --- | --- | --- |
| E1 | The item-health outcome vocabulary is `ok` and `failed`. There is no `published`. | A filter on `outcome == "published"` returns zero and reads like a real finding. |
| E2 | A digest item carries `item_id` and `source_url`, never `url_key`. | Joining item-health to the digest tree on `url_key` silently matches nothing. |
| E3 | Three guard tests pin the old charge rule, and one says in its own docstring that flipping a switch is the reason to think again. | They fail together in `test_taxonomy_and_prompts.py`. That is the contract working; update them, do not route around them. |
| E4 | Two shared test fixtures sat under the 60-word floor. | A title test or a `no_title` census fixture reports `too_short` and never reaches the branch it was written for. |
| E5 | `test_a_push_nothing_will_take_gives_up_on_the_clock_and_says_what_it_spent` fails on a loaded machine. | It gives a push loop 3 seconds and wants 2 attempts. Unrelated to this work; a sibling branch is already fixing that class of test. |

## What done looks like

1. The owner has answered the B table.
2. `f08422ae5` is pushed, has a pull request, and CI is green - or it has been
   revised to carry whatever the owner chose.
3. Whatever landed is written into the living doc that owns it. The charge rule
   belongs in [docs/architecture/sources/item-health.md](docs/architecture/sources/item-health.md);
   the knob belongs in [docs/concepts/config/summary-length.md](docs/concepts/config/summary-length.md).
   Both already carry the `f08422ae5` version of the story, so a change to that
   commit is a change to those pages in the same commit.
4. This page is deleted. A handover that outlives its job becomes a second
   source of truth, and `docs/` is the memory (Guardrail #4).
