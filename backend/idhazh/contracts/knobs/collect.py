"""How many stories a day gathers, from which tier of source, and how far back it looks."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Final, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import Model
from idhazh.contracts.item_health import FailureCode
from idhazh.contracts.knobs.removed import refuse_a_removed_knob


class TierWeights(Model):
    """The ranking weight of a source tier. Tier 1 is the institution that IS the fact."""

    institution: float = Field(default=1.0, ge=0.0, le=1.0)
    trade_press: float = Field(default=0.6, ge=0.0, le=1.0)
    community: float = Field(default=0.3, ge=0.0, le=1.0)


#: The `collect` names this block used to carry, and the knob that answers the
#: same question now. A config still spelling one is refused by name.
SUPERSEDED_COLLECT_NAMES: Final[Mapping[str, str]] = MappingProxyType(
    {"quarantine_after_failures": "availability_strikes_before_rest"}
)


#: The one sentinel a lookback window uses to say "never forget". Not 0, which
#: reads as "look back nothing", and not a very large number, which is a cover
#: that silently becomes finite the day the archive outgrows it.
UNBOUNDED_WINDOW: Final = -1


class CollectConfig(Model):
    availability_strikes_before_rest: int = Field(
        default=5,
        ge=1,
        description=(
            "Consecutive results that count against a feed before a run stops asking "
            "it, and how many runs that rest then lasts. One number for both counters "
            "because there is one question here - how much evidence is enough - and "
            "discover.resting takes it once. It replaced quarantine_after_failures on "
            "2026-09-03, carrying the same 5: the old name read as a policy about "
            "quarantine and this one is named for what it counts."
        ),
    )
    availability_rest_runs: int = Field(
        default=5,
        ge=1,
        description=(
            "How many runs a rested feed is skipped before it is asked again. The rest "
            "ends on its own, so a source that came back is live on that very run and a "
            "source that is still dead costs one request per cycle rather than one per "
            "run. Still unread: the rest lasts availability_strikes_before_rest runs, "
            "because splitting one number into two is a change to the rest rule rather "
            "than a rename, and the rename is what landed."
        ),
    )
    feed_http_410_runs_before_retirement: int = Field(
        default=5,
        ge=1,
        description=(
            "Distinct runs that must each read HTTP 410 from one address before that "
            "address is retired. Distinct runs and not attempts: one bad afternoon "
            "retrying itself is one run's evidence."
        ),
    )
    robots_denied_recheck_runs: int = Field(
        default=1,
        ge=1,
        description=(
            "Runs to wait before asking robots.txt again after a refusal. One, because "
            "permission can be granted back at any moment and a refusal costs one small "
            "request to re-establish - a longer wait buys nothing measurable and delays "
            "a source's return."
        ),
    )
    robots_unreachable_recheck_runs: int = Field(
        default=1,
        ge=1,
        description=(
            "The same, for permission we could not establish at all. Separate from the "
            "denial cadence because the two are different facts: one is a publisher's "
            "stated policy and the other is our own failed read."
        ),
    )
    source_yield_min_complete_days: int = Field(
        default=30,
        ge=1,
        description=(
            "Complete days of item-health evidence a per-source yield judgement needs "
            "before it may be made at all. Below it any yield threshold is an estimate "
            "rather than a measurement (Guardrail #10), and no source may be demoted on one."
        ),
    )
    source_yield_alarm_point: float = Field(
        default=0.5,
        gt=0.0,
        le=1.0,
        description=(
            "The yield below which a run names a source on its own summary - the share "
            "of the addresses a source decided that it turned into a story. It raises a "
            "flag for a person and moves nothing on its own: it never rests a feed, "
            "never scales a rank and never edits config/sources.json. Measured "
            "2026-09-06 over the committed source-health view, 144 sources and 13 "
            "complete days: the record is bimodal, and between 26.5 percent and 77.3 "
            "percent there is not one source with 30 or more decisions. The default "
            "sits in the middle of that 50-point empty band, so anywhere from 30 to 75 "
            "percent names the same three sources and the exact number is cheap. It is "
            "an alarm point and not a floor - reliability_floor clamps a factor, this "
            "compares a ratio, and one word for both is how the two get confused."
        ),
    )
    source_yield_alarm_min_decisions: int = Field(
        default=30,
        ge=1,
        description=(
            "Addresses a source must have decided before its yield may raise the alarm. "
            "A low yield and a low volume are independent axes, and without this floor "
            "the alarm's first run names a source the project already ruled it keeps: "
            "measured 2026-09-06, cnn-world reads 1 of 7 and every other low-volume "
            "source reads at 77.8 percent or better. Distinct from "
            "source_yield_min_complete_days, which counts days of record rather than "
            "decisions a source made, because a busy source clears this in four days "
            "and a weekly one may never clear it - which is the correct answer for "
            "both. The cost is delay: at 8.5 decisions a day the alarm arrives on day "
            "four, and the roughly 25 addresses spent getting there buy the protection."
        ),
    )
    watchlist_max_entities: int = Field(default=30, ge=1)
    settled_failure_codes: tuple[FailureCode, ...] = Field(
        default=(
            FailureCode.ROBOTS_DENIED,
            FailureCode.ROBOTS_UNREACHABLE,
            FailureCode.BLOCKED_ADDRESS,
            FailureCode.HTTP_CLIENT_ERROR,
            FailureCode.PAYWALLED,
            FailureCode.NO_TEXT,
            FailureCode.NOT_PROSE,
            FailureCode.BOILERPLATE,
            FailureCode.TOO_SHORT,
            FailureCode.UNSUPPORTED_FORM,
        ),
        description=(
            "Failure codes that will not change before tomorrow. An address that failed "
            "today with one of these is not planned again today. A paywall, a robots "
            "rule and a 404 are the same answer at 02:20 and at 18:20; a rate limit, a "
            "reset connection and an unreachable model are not, so they are absent and "
            "a later run retries them. Empty means retry everything, which is what the "
            "pipeline did before 2026-08-29."
        ),
    )
    max_per_source: int = Field(
        default=2,
        ge=1,
        description=(
            "Most items one feed may contribute to one vertical in a day. Without it, a "
            "quiet news day is whichever blog published most."
        ),
    )
    max_source_share_per_day: float = Field(
        default=0.05,
        gt=0.0,
        le=1.0,
        description=(
            "Most of one day one feed may hold, counting every desk and every run. "
            "max_per_source bounds a count inside one desk in one run, and a feed sits "
            "on one desk, so what a feed can hold of a whole day is that count times "
            "the runs the day had - a fixed number whose share moves with the day's "
            "size. Measured 2026-08-31 over the eleven committed days, the most one "
            "feed ever held was 10 items, which is 2.32 percent of the 431-item day of "
            "2026-08-30 and 25 percent of the four-item day of 2026-08-21. The default "
            "is above the largest full-day share by a factor of two, so it displaces "
            "nothing that has ever been published; it bounds the thin day, where a "
            "fixed count of ten is a quarter of the page. It is never tighter than "
            "max_per_source for one desk in one run - a day ceiling below that would "
            "tighten the per-desk rule, which is a different decision and was refused."
        ),
    )
    tier_weights: TierWeights = Field(
        default_factory=TierWeights,
        description=(
            "The first and heaviest of the four terms the order is built from - what a "
            "source tier is worth, before the feed's own weight and its recent record "
            "scale it. The ladder spans 0.7, institution 1.0 down to community 0.3, "
            "which is wider than any other term's ceiling and is why it is term one. An "
            "estimate, and this is the measurement that would overturn it. Measured "
            "2026-09-13 over the 13 committed days that carry rank_score, 5,682 "
            "stories: flatten every tier to 1.0 and the story sitting in a median of "
            "19 of the 20 head slots changes, and the lead story changes on 6 of the "
            "13 days - so the ladder, not any bonus, is what decides the head. Of "
            "those stories 5,456 are on a feed config/sources.json still names, and "
            "231 of the 260 head slots are; over that population the 40 institution "
            "feeds supply 5.5 percent of the stream and hold 22.1 percent of the head, "
            "a 4.0x lift, while the 11 community feeds supply 1.8 percent and have "
            "held none of it. So 0.3 is not yet distinguishable from 0 there; raising "
            "it, or saying that tier admits rather than ranks, is the open question. "
            "Named by Editor, 2026-09-13."
        ),
    )
    reliability_window_days: int = Field(
        default=30,
        ge=30,
        description=(
            "Trailing days of committed feed-health read to score a feed's "
            "reliability - how often its reads carried entries rather than failing or "
            "parsing to nothing. At least 30, because a feed publishes a few times a "
            "day at most and a shorter window would let one bad afternoon set the "
            "factor. The read is bounded by this window and never the whole ledger "
            "(Guardrail #12)."
        ),
    )
    reliability_floor: float = Field(
        default=0.5,
        gt=0.0,
        le=1.0,
        description=(
            "The lowest a reliability factor may reach. The factor scales a feed's "
            "authority and is clamped to the range [floor, 1.0], so it only ever "
            "reduces a score and never removes a feed. At 0.5 the worst a feed's "
            "record can do is halve its authority - a two-to-one cut, never more - so "
            "a reliable feed of a lower tier can still be caught but a single desk is "
            "never emptied by this alone. Third of the four terms the order is built "
            "from, and its ceiling is (1 - floor) times the best tier, which is 0.5 "
            "today. An estimate, and this is the measurement that would overturn it. "
            "Measured 2026-09-13 over the trailing 30 days of committed feed health: of "
            "the 149 feeds carrying evidence, 19 score below 1.0 and the floor clamps "
            "exactly 2 of them - bruegel, whose raw ratio is 0.0, and swarajya at 0.16. "
            "At a floor of 0 bruegel would score no authority at all and leave the day, "
            "which is the removal this clamp refuses."
        ),
    )
    carriage_step: float = Field(
        default=0.25,
        ge=0.0,
        description=(
            "What one more of our feeds carrying the same address is worth. A flat step "
            "that fires once at two carriers and never grows - three carriers is not "
            "three times the story. It multiplied authority until 2026-09-13, so a "
            "second carrier DOUBLED the term and a story on six feeds took the day; a "
            "multiplier also paid most to whatever already scored highest, which is the "
            "opposite of what a tie-break does. What it counts is syndication rather "
            "than agreement: carried_by counts feeds carrying one address, so two "
            "outlets writing their own piece produce two addresses and both read 1 "
            "(docs/architecture/publishing/layout.md). An estimate, and it is set by "
            "two written rules rather than by a measurement, because nothing inside "
            "the window they leave is measurable. It may not reach the smallest gap "
            "between two collect.tier_weights values - 0.3 today - or carriage would "
            "promote a community story past a trade-press one; and it may not fall to "
            "ui.lead_shared_subject_weight - 0.2 today - or a recurring subject would "
            "outrank a story two independent feeds carried today. Measured 2026-09-13 "
            "over the 13 committed days that carry rank_score, 5,682 stories: across "
            "the whole of that window 6 of 260 head slots move and no lead does, so "
            "0.25 is the midpoint, which is the value that stays legal when either "
            "bound is edited. Carriage holds 20.8 percent of the framed head today on "
            "5.7 percent of the stream; at 0.25 it holds 7.7 percent, a 1.4x lift. "
            "Row #9a's pricing and then plan 23 row #17's per-run loop are what would "
            "overturn it, with the tier step as a hard bound. Ruled by Editor, "
            "2026-09-13."
        ),
    )
    watchlist_bonus: float = Field(
        default=0.5,
        ge=0.0,
        description=(
            "What a story about a subject on config/watchlist.json is worth, added "
            "once however many watchlist entries it names. It is the fourth and "
            "smallest of the four terms the order is built from - authority times the "
            "feed's weight, then decayed recency, then the feed's reliability, then "
            "this. An estimate, and this is the measurement that would overturn it. "
            "Measured 2026-09-13 over the 13 committed days that carry rank_score, "
            "5,682 stories: a watchlist subject fires on 22.1 percent of the stream, "
            "3.88 times as often as a second feed carrying one address, so the "
            "firing-rate method discovery.md uses for a content signal would price it "
            "at 0.6 / 3.88 = 0.15. That method is the wrong instrument here and the "
            "measurement says so: a watchlist subject is not informative because it is "
            "rare, it is informative because a person chose it. Cutting it to 0.15 "
            "takes the biggest desk's share of the raw top 20 from a median of 80 "
            "percent to 95, distinct desks in that top 20 from 4 to 3, and institution "
            "stories in it from 51 to 16 over the same 13 days. The reason was that "
            "carriage still MULTIPLIED authority when this was read, so it was the "
            "only additive term that could lift an un-syndicated story from a second "
            "desk into the head. Carriage became a flat step later the same day and "
            "now holds 7.7 percent of the head rather than 20.8, so that reason has "
            "weakened - but the argument that killed the 0.15 has not: a frequency "
            "method cannot price a signal a person chose. Re-pricing this against the "
            "new step would move the leading block's order and belongs to plan 23 row "
            "#17's per-run loop. Ruled by Editor, 2026-09-13."
        ),
    )
    recency_weight: float = Field(
        default=0.6,
        ge=0.0,
        description=(
            "How much freshness may move a score, inside the window max_age_hours "
            "allows. It orders what is already fresh enough to publish; it is "
            "max_age_hours, not this, that decides what is too old to add at all. "
            "Second of the four terms the order is built from, by ceiling - and the "
            "ceiling is most of what it is. An estimate, and this is the measurement "
            "that would overturn it. Measured 2026-09-13 over the 13 committed days "
            "that carry rank_score: the bonus is not published, so it is recovered from "
            "the published score, which leaves 5,442 of the day's 5,682 stories "
            "answerable. It fires on every one of them, paying a median of 0.5656 "
            "against a ceiling of 0.6 - 94 percent of the most it can ever pay - and "
            "the middle half of the stream spans 0.5053 to 0.5874, a spread of 0.08 "
            "that is a quarter of the smallest step between two tiers. The median story "
            "is 1.5 hours old when it is scored and three quarters are under 4.5 hours, "
            "so an 18-hour half-life over a 24-hour admission window adds nearly the "
            "same amount to everything. Raising this weight does not fix that - it "
            "scales a flat term. The half-life is what would, and no row owns it yet."
        ),
    )
    recency_half_life_hours: float = Field(
        default=18.0,
        gt=0.0,
        description=("Hours for the recency bonus to halve. At 18 h a day-old item keeps a third."),
    )
    max_age_hours: float = Field(
        default=24.0,
        gt=0.0,
        description=(
            "How old a story may be and still be added. A hard gate, applied to the "
            "date we believe rather than the date the feed claimed. An article we "
            "could not date at all is not too old - first sight is its age, so it "
            "gets the day we found it and no more."
        ),
    )
    max_future_hours: float = Field(
        default=6.0,
        ge=0.0,
        description=(
            "A publish date further ahead than this is not believed and the item falls "
            "back to first sight. Feeds that stamp tomorrow would otherwise take the "
            "top slot every single day."
        ),
    )
    seen_window_days: int = Field(
        default=90,
        ge=1,
        description=(
            "How far back the first-sight store is consulted. It is counted in days "
            "and the store files by day, so the window names the files it opens and "
            "the prune keeps exactly those. Older day files stay committed and "
            "readable until that prune reaches them; they are just not evidence "
            "about today."
        ),
    )
    published_window_days: int = Field(
        default=-1,
        description=(
            "How far back the published record is consulted before an address is "
            "treated as never published. -1 means never forget, and it is the only "
            "sentinel for unbounded - not 0, not null, and not a very large number, "
            "because a large number is a cover that silently becomes finite the day "
            "the archive outgrows it. A finite value must be strictly longer than "
            "seen_window_days: the two stores answer the same question from opposite "
            "ends, and a cover that expires first hands an address to a first-sight "
            "store that has already forgotten it. load_published reads it once a run, "
            "through stage_plan."
        ),
    )
    blocked_url_markers: list[str] = Field(
        default_factory=list,
        description=(
            "Case-insensitive substrings of a canonical address that never enter the "
            "pool. For the promotional page a working news feed syndicates: an affiliate "
            "product review is short declarative prose, so it is trivially entailed and "
            "no faithfulness threshold detects it at any cut. Empty by default - the "
            "entries are a source list and live in config/ (Guardrail #6)."
        ),
    )
    dedup_similarity_min: float = Field(
        default=0.94,
        ge=0.0,
        le=1.0,
        description=(
            "How alike two of a day's planned stories have to be, by cosine over the "
            "headline-and-lead vectors the plan builds, before they are recorded as one "
            "story carried at two addresses. The same number and the same reason as "
            "assemble.duplicate_similarity_min: set by hand labels at 0.94, the first "
            "round hundredth above the highest-scoring pair a person marked as two "
            "stories (measured 2026-09-01, i7-1265U, 3,978 items). The plan pass reuses "
            "it rather than minting a second threshold for the same question one stage "
            "earlier. Raising it misses duplicates; lowering it risks folding two "
            "stories into one, so it leans high."
        ),
    )
    dedup_enforce: bool = Field(
        default=False,
        description=(
            "Whether the plan-stage duplicate pass CUTS the weaker telling of a "
            "repeated story, or only records what it would cut. False is record-only: "
            "the pass logs each would-collapse pair against what it matched and removes "
            "nothing, so a day is measured before it is trimmed. Turning it on cuts the "
            "lower-ranked of each pair before the safety ceiling and changes nothing "
            "else. It ships false, because a cut nobody has read the record of is a cut "
            "nobody can defend."
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _refuse_a_removed_knob(cls, data: Any) -> Any:
        return refuse_a_removed_knob("collect", data, SUPERSEDED_COLLECT_NAMES)

    @model_validator(mode="after")
    def _the_published_window_outlives_the_first_sight_store(self) -> Self:
        """The one mistake this knob must make impossible is a republication.

        An address the published record has forgotten, whose first-sighting row
        expires in the same week, reads as first-seen-today. It clears the
        freshness gate and goes out as new, and nothing anywhere holds the
        evidence that it ran before. So EQUAL IS A HOLE, NOT A BOUND: at 90 and
        90 both stores forget the same address on the same day. Only two answers
        are safe - never forget, or forget later than the first-sight store does.

        Checked after the model rather than on the field, so it re-runs whenever
        either number moves. Raising `seen_window_days` past a finite cover fails
        the config instead of opening the hole quietly.
        """
        if self.published_window_days == UNBOUNDED_WINDOW:
            return self
        if self.published_window_days <= self.seen_window_days:
            raise ValueError(
                f"collect.published_window_days is {self.published_window_days}, which is "
                f"not longer than collect.seen_window_days, which is {self.seen_window_days}. "
                f"Use {UNBOUNDED_WINDOW} to never forget, or a value above "
                f"{self.seen_window_days}. A cover that expires no later than the "
                "first-sight store hands it an address neither one remembers, and an "
                "undated re-listing then republishes as new."
            )
        return self
