"""Where does the merge line in force stand against the pairs somebody marked?

Four cells. For every marked pair, the line either joins it or leaves it apart,
and the mark either agrees or does not - so a reading is two counts of agreement
and two of disagreement, plus a fifth count for the pairs neither cell could be
counted for at all.

**It scores the LINE, not the judge.** The marks carry no verdict and nothing
here calls a model. A pair is joined here exactly when the weighted score
reaches the line, which is the one branch of `collapse_same_story` the line
decides. The two overrides beside it - two headlines that reduce to the same
words joining at 1.0, and a clash of figures refusing outright - are left out on
purpose: they fire or they do not whatever the line is set to, so counting them
would credit the line with a merge it did not make. `$lib/console/holdout.ts`
leaves the same two out, for the same reason and with the same cost, which
`docs/architecture/publishing/autotune-content-similarity.md` states.

**One spelling of each rule.** The cosine, the norm, the width check and the word
reduction all come from `idhazh.assemble`, which is the module the published day
was built by. A second spelling here would be a reading of a line this pipeline
does not apply.

**What it reads, and what bounds it** (Guardrail #12). The hand-marked file,
then one published day payload for each distinct date that file's rows name. The
bound is the length of the marked file: a published day nothing marks is never
opened, and another year of archive adds no read at all. The days it opens are
outside any window a knob sets, because a mark on a day the window no longer
reaches still says something about the line.
"""

from __future__ import annotations

import csv
import math
from array import array
from dataclasses import dataclass
from pathlib import Path

from idhazh import assemble, ledger
from idhazh.contracts.base import derive_url_key
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.knobs.placement import HOLDOUT_RESOLVED_SHARE_MIN
from idhazh.contracts.similarity_holdout_pair import SimilarityHoldoutPair


@dataclass(frozen=True, slots=True)
class _Article:
    """One published story reduced to the three things a pair score reads."""

    words: frozenset[str]
    vector: array[int]
    norm: float


@dataclass(frozen=True, slots=True)
class ScoredMark:
    """One marked pair, scored under the weights in force."""

    same_story: bool
    score: float


@dataclass(frozen=True, slots=True)
class Reading:
    """Every mark the day tree could answer for, and how many it could not."""

    scored: tuple[ScoredMark, ...]
    #: How many rows the marked file holds, scored or not.
    marked: int
    #: How many of those rows name a day or an article the tree no longer has.
    unresolved: int
    #: How many rows are marked as two different stories, scored or not. The
    #: population the false-merge cell is drawn from, counted over the whole
    #: file so that a rate is never read against a shrinking denominator.
    two_story_marks: int
    #: How many distinct published days were opened to answer it.
    days_opened: int


@dataclass(frozen=True, slots=True)
class Cells:
    """What the line did to the marked pairs, and what the marks say about it."""

    merged_and_one_story: int
    merged_and_two_stories: int
    apart_and_one_story: int
    apart_and_two_stories: int
    unresolved: int
    two_story_marks: int
    marked: int

    @property
    def resolved(self) -> int:
        """The four cells added together, which is every pair that was counted."""
        return (
            self.merged_and_one_story
            + self.merged_and_two_stories
            + self.apart_and_one_story
            + self.apart_and_two_stories
        )


def marked_pairs(state_dir: Path) -> list[SimilarityHoldoutPair]:
    """Every row of the hand-marked file, or nothing where the file is absent.

    An absent file is an ordinary state - a fresh clone has no marks - and it is
    the caller that decides what to do with a reading of nothing.

    A row that does not parse stops the read rather than being skipped. This is
    the evidence a floor is set from, and a silently short count reads as a
    smaller holdout rather than as a broken one.
    """
    path = ledger.similarity_holdout_path(state_dir)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [SimilarityHoldoutPair.from_csv_row(row) for row in csv.DictReader(handle)]


def _day_articles(
    date: str, digest_root: Path, wanted: frozenset[str]
) -> dict[str, _Article] | None:
    """The items of one published day that the marked file actually names.

    `None` where the day is no longer published, which is a designed state
    rather than a failure: retention deletes days the marked file still names.

    Everything the marks do not name is dropped on the way past. The day payload
    is the biggest file this read opens and the vector block is most of it, so
    the wanted keys are worked out before the file is opened.
    """
    path = assemble.day_dir(digest_root, date) / "digest.json"
    if not path.exists():
        return None
    day = DigestDay.from_json(path.read_text(encoding="utf-8"))
    block = day.embeddings
    if block is None:
        return {}
    found: dict[str, _Article] = {}
    for item in day.items:
        # Recomputed from the address on both sides, which is the identity the
        # marked row carries too: a person types that file, so there is no cell
        # a typist can get wrong and none that can go stale.
        key = derive_url_key(item.source_url)
        if key not in wanted:
            continue
        encoded = block.vectors.get(item.item_id)
        if encoded is None:
            continue
        raw = assemble.vector_bytes(encoded, block.dimensions)
        if raw is None:
            continue
        vector = array("b", raw)
        found[key] = _Article(
            words=assemble.key_point_words(item),
            vector=vector,
            norm=assemble.vector_norm(vector),
        )
    return found


def score_marks(
    marks: list[SimilarityHoldoutPair],
    *,
    digest_root: Path,
    cosine_weight: float,
    key_point_weight: float,
) -> Reading:
    """Score every marked pair, and count the ones the tree cannot answer for.

    A pair the tree cannot answer for is counted with the others rather than
    dropped. A dropped row would make the comparison look complete at whatever
    size retention had left it.
    """
    wanted = frozenset(
        key for mark in marks for key in (mark.left_url_key, mark.right_url_key)
    )
    dates = sorted({date for mark in marks for date in (mark.left_date, mark.right_date)})
    days = {date: _day_articles(date, digest_root, wanted) for date in dates}

    scored: list[ScoredMark] = []
    unresolved = 0
    for mark in marks:
        left_day, right_day = days.get(mark.left_date), days.get(mark.right_date)
        left = None if left_day is None else left_day.get(mark.left_url_key)
        right = None if right_day is None else right_day.get(mark.right_url_key)
        if left is None or right is None:
            unresolved += 1
            continue
        cosine = assemble.cosine_int8(
            left.vector, right.vector, left_norm=left.norm, right_norm=right.norm
        )
        overlap = assemble.key_point_overlap(left.words, right.words)
        scored.append(
            ScoredMark(
                same_story=mark.same_story,
                score=cosine_weight * cosine + key_point_weight * overlap,
            )
        )
    return Reading(
        scored=tuple(scored),
        marked=len(marks),
        unresolved=unresolved,
        two_story_marks=sum(1 for mark in marks if not mark.same_story),
        days_opened=len(dates),
    )


def count_cells(reading: Reading, *, line: float) -> Cells:
    """The four cells at one line, plus the pairs that could not be counted.

    **A pair scoring exactly the line is a merge.** `collapse_same_story` refuses
    on `score < floor_min`, so the pair sitting on the boundary is joined - and
    counting it apart would file the one pair the line is closest to on the safe
    side of the reading.
    """
    merged = [mark for mark in reading.scored if mark.score >= line]
    apart = [mark for mark in reading.scored if mark.score < line]
    return Cells(
        merged_and_one_story=sum(1 for mark in merged if mark.same_story),
        merged_and_two_stories=sum(1 for mark in merged if not mark.same_story),
        apart_and_one_story=sum(1 for mark in apart if mark.same_story),
        apart_and_two_stories=sum(1 for mark in apart if not mark.same_story),
        unresolved=reading.unresolved,
        two_story_marks=reading.two_story_marks,
        marked=reading.marked,
    )


def resolved_floor(marked: int) -> int:
    """How many pairs a reading has to have counted before its cells mean anything.

    Half the marked file, rounded up. Below it the four cells still add up and
    still look like a reading, while most of what was marked went uncounted -
    and four small cells read as a line that got almost everything right rather
    than as a comparison that has mostly vanished.

    Retention is what takes the days away, so this floor is reached by the
    calendar rather than by a bug. That is the case it exists for.
    """
    return math.ceil(marked * HOLDOUT_RESOLVED_SHARE_MIN)


def two_story_max(reading: Reading) -> float | None:
    """The highest-scoring pair marked as two different stories, or nothing.

    The retaken reading behind `HOLDOUT_TWO_STORY_MAX`, which is declared once in
    the knobs module and checked here (Guardrail #10). Nothing stores it: a
    committed copy would be the second source that constant is not allowed to
    have.
    """
    scores = [mark.score for mark in reading.scored if not mark.same_story]
    return max(scores) if scores else None
