"""The registry holds: it names every ledger, and it puts each one where it was.

Four checks, and each one catches what the others cannot. The bijection is the
only one that is new - the other three exist so that replacing twenty-odd
hand-written path functions with one config file moved no byte on disk.

The family checks sit beside them. A family is one top-level folder under
`state/` and carries the lifecycle status, so each refusal below is a registry
that would give one folder two answers.

The paths on the right of every row were computed from `backend/idhazh/ledger/
__init__.py` as it stood before the registry landed, not typed from memory.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

import pytest
from pydantic import ValidationError

from idhazh import ledger
from idhazh.contracts.ledger_name import DAY_TREES, LedgerName
from idhazh.contracts.ledgers import Grain, LedgersConfig, LifecycleStatus
from idhazh.ledger import paths

pytestmark = pytest.mark.contract

REPO_ROOT: Final = Path(__file__).resolve().parents[3]
REGISTRY: Final = REPO_ROOT / "config" / paths.REGISTRY_FILENAME

A_DAY: Final = "2026-09-18"
A_MONTH: Final = "2026-09"
A_STAMP: Final = "20260918T120000Z"
STATE: Final = Path("state")

#: What each builder answered before the registry existed: the POSIX form, the
#: path under a state root named `state`, and the whole-tree directory a reader
#: walks. `None` where the old module offered no such function.
#:
#: Computed from `5a9c6f32f:backend/idhazh/ledger/__init__.py` by calling those
#: functions, so a row here is the old answer rather than a reading of it.
#:
#: Two rows are not the old answer, and the difference is only their first
#: segment. `candidate-models` was `validation` and `item-health-summary` was
#: `telemetry-aggregate`, renamed to say what they hold while neither had a
#: single committed file - so the old addresses held nothing to move.
AT_THE_BASE: Final[dict[str, tuple[str | None, str | None, str | None]]] = {
    "SEEN": ("state/seen/2026/09/18.csv", "state/seen/2026/09/18.csv", "state/seen"),
    "FEED_HEALTH": (
        "state/feed-health/2026/09/18",
        "state/feed-health/2026/09/18",
        "state/feed-health",
    ),
    "ITEM_HEALTH": (
        "state/item-health/2026/09/18",
        "state/item-health/2026/09/18",
        "state/item-health",
    ),
    "HOST_FINGERPRINT": (
        "state/host-fingerprint/2026/09/18",
        "state/host-fingerprint/2026/09/18",
        "state/host-fingerprint",
    ),
    "SCORES": ("state/scores/2026/09/18", "state/scores/2026/09/18", "state/scores"),
    "SCORE_INDEX": (
        "state/score-index/2026/09/18",
        "state/score-index/2026/09/18",
        "state/score-index",
    ),
    "CANDIDATE_MODELS": (
        "state/candidate-models/2026/09/18",
        "state/candidate-models/2026/09/18",
        "state/candidate-models",
    ),
    "ITEM_HEALTH_SUMMARY": (
        "state/item-health-summary/2026-09.csv",
        "state/item-health-summary/2026-09.csv",
        None,
    ),
    "SPAN_ROLLUP": (
        "state/span-rollup/2026/09/18",
        "state/span-rollup/2026/09/18",
        "state/span-rollup",
    ),
    "PUBLISHED": (
        "state/published/2026/09/18.csv",
        "state/published/2026/09/18.csv",
        "state/published",
    ),
    "FEED_RETIREMENTS": ("state/feed-retirements.csv", "state/feed-retirements.csv", None),
    "VISUAL_PRUNES": (
        "state/visual-prunes/2026/09/18.csv",
        "state/visual-prunes/2026/09/18.csv",
        "state/visual-prunes",
    ),
    "COUNTERFACTUAL_SCORES": (
        "state/counterfactual-scores/2026/09/18",
        "state/counterfactual-scores/2026/09/18",
        "state/counterfactual-scores",
    ),
    "CONTENT_SIMILARITY_JUDGE_SCORED_PAIRS": (
        "state/content-similarity-judge/scored-pairs/2026/09/18.csv",
        "state/content-similarity-judge/scored-pairs/2026/09/18.csv",
        "state/content-similarity-judge/scored-pairs",
    ),
    "CONTENT_SIMILARITY_JUDGE_FITTED_THRESHOLDS": (
        "state/content-similarity-judge/fitted-thresholds/2026/09/18.csv",
        "state/content-similarity-judge/fitted-thresholds/2026/09/18.csv",
        "state/content-similarity-judge/fitted-thresholds",
    ),
    "CONTENT_SIMILARITY_JUDGE_HOLDOUT_PAIRS": (
        "state/content-similarity-judge/holdout-pairs.csv",
        "state/content-similarity-judge/holdout-pairs.csv",
        None,
    ),
    "CONTENT_SIMILARITY_JUDGE_SCORE_DISTRIBUTION": (
        None,
        "state/content-similarity-judge/score-distribution.json",
        None,
    ),
    "CONTENT_SIMILARITY_JUDGE_ARCHIVE": (
        "state/content-similarity-judge/archive/20260918T120000Z.json",
        "state/content-similarity-judge/archive/20260918T120000Z.json",
        None,
    ),
    "CONTENT_SIMILARITY_JUDGE_METRICS": (
        "state/content-similarity-judge/metrics/2026/09/18.csv",
        "state/content-similarity-judge/metrics/2026/09/18.csv",
        "state/content-similarity-judge/metrics",
    ),
    "CONTENT_SIMILARITY_JUDGE_MERGE_LINE_HOLDOUT_SCORES": (
        "state/content-similarity-judge/merge-line-holdout-scores/2026/09/18.csv",
        "state/content-similarity-judge/merge-line-holdout-scores/2026/09/18.csv",
        "state/content-similarity-judge/merge-line-holdout-scores",
    ),
    "LLM_COUNCIL_SHARD_OUTCOMES": (
        "state/llm-council/shard-outcomes/2026/09/18.csv",
        "state/llm-council/shard-outcomes/2026/09/18.csv",
        "state/llm-council/shard-outcomes",
    ),
}

#: Which directories `prune-state` protected before the registry claimed them,
#: from the same commit.
CLAIMED_AT_THE_BASE: Final[frozenset[str]] = frozenset(
    {
        "content-similarity-judge",
        "counterfactual-scores",
        "feed-health",
        "host-fingerprint",
        "item-health",
        "llm-council",
        "published",
        "score-index",
        "scores",
        "seen",
        "span-rollup",
        "telemetry-aggregate",
        "validation",
        "visual-prunes",
    }
)

#: The period each grain is asked for, so one table drives every builder check.
COVERS: Final[dict[Grain, str | None]] = {
    Grain.FLAT: None,
    Grain.DAY_FILE: A_DAY,
    Grain.DAY_TREE: A_DAY,
    Grain.MONTH_FILE: A_MONTH,
    Grain.STAMPED: A_STAMP,
}


def a_registry(families: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """The committed registry as a payload, with its family list optionally replaced."""
    held: dict[str, Any] = json.loads(REGISTRY.read_text(encoding="utf-8"))
    if families is not None:
        held["families"] = families
    return held


def committed_families() -> list[dict[str, Any]]:
    """The family list as the file holds it."""
    families: list[dict[str, Any]] = a_registry()["families"]
    return families


def a_family(name: str) -> dict[str, Any]:
    """One committed family, as the file holds it."""
    return next(family for family in committed_families() if family["name"] == name)


def without(*names: str) -> list[dict[str, Any]]:
    """The committed families, less the ones named."""
    return [family for family in committed_families() if family["name"] not in names]


def test_the_committed_registry_names_every_ledger_exactly_once() -> None:
    """The bijection, over the file the build really reads."""
    families = LedgersConfig.from_json(REGISTRY.read_text(encoding="utf-8")).families
    entries = [held for family in families for held in family.ledgers]

    assert {held.name for held in entries} == set(LedgerName)
    assert len(entries) == len(LedgerName)


def test_a_ledger_with_no_entry_stops_the_build_naming_it() -> None:
    """The refusal that replaces the hand-coded set, proved able to fire.

    A ledger left out of the old Python set was a directory `prune-state`
    silently emptied. Here it is a payload that will not validate, and the
    message names the ledger an operator has to add.
    """
    with pytest.raises(ValidationError) as refusal:
        LedgersConfig.model_validate(a_registry(without(LedgerName.ITEM_HEALTH.value)))

    assert "no entry for item-health" in str(refusal.value)


def test_a_ledger_named_twice_stops_the_build_naming_it() -> None:
    """Two entries for one ledger are two answers, and nothing chooses between them."""
    seen = a_family(LedgerName.SEEN.value)
    doubled = {**seen, "ledgers": [*seen["ledgers"], dict(seen["ledgers"][0])]}

    with pytest.raises(ValidationError) as refusal:
        LedgersConfig.model_validate(a_registry([doubled, *without(LedgerName.SEEN.value)]))

    assert "seen has more than one entry" in str(refusal.value)


def test_an_entry_for_no_ledger_is_refused_by_the_name_it_carries() -> None:
    """The other half of the bijection: a name nobody declared."""
    seen = a_family(LedgerName.SEEN.value)
    invented = {
        **seen,
        "ledgers": [*seen["ledgers"], {**seen["ledgers"][0], "name": "a-ledger-nobody-declared"}],
    }

    with pytest.raises(ValidationError) as refusal:
        LedgersConfig.model_validate(a_registry([invented, *without(LedgerName.SEEN.value)]))

    assert "a-ledger-nobody-declared" in str(refusal.value)


def test_a_family_named_twice_stops_the_build_naming_it() -> None:
    """Two lists for one folder would give that folder two statuses.

    The judge's seven ledgers split across two families of one name, so every
    ledger is still listed exactly once and only the family repeats.
    """
    judge = a_family("content-similarity-judge")
    halves = [
        {**judge, "ledgers": judge["ledgers"][:3]},
        {**judge, "ledgers": judge["ledgers"][3:]},
    ]

    with pytest.raises(ValidationError) as refusal:
        LedgersConfig.model_validate(a_registry([*halves, *without("content-similarity-judge")]))

    assert "family content-similarity-judge is listed more than once" in str(refusal.value)


def test_a_ledger_listed_in_two_families_stops_the_build_naming_both() -> None:
    """A ledger in two families takes two statuses, and nothing chooses between them."""
    health = a_family(LedgerName.FEED_HEALTH.value)
    widened = {
        **health,
        "ledgers": [*health["ledgers"], dict(a_family(LedgerName.SEEN.value)["ledgers"][0])],
    }

    with pytest.raises(ValidationError) as refusal:
        LedgersConfig.model_validate(a_registry([widened, *without(LedgerName.FEED_HEALTH.value)]))

    assert "seen is listed in families feed-health and seen" in str(refusal.value)


def test_a_ledger_outside_its_familys_folder_stops_the_build_naming_it() -> None:
    """A family is the folder its ledgers sit in, so a ledger filed elsewhere is refused.

    The council's one ledger moved into the judge's list: its prefix still says
    `state/llm-council/`, so it would sit in one folder under another's status.
    """
    judge = a_family("content-similarity-judge")
    council = a_family("llm-council")["ledgers"][0]
    moved = {**judge, "ledgers": [*judge["ledgers"], dict(council)]}

    with pytest.raises(ValidationError) as refusal:
        LedgersConfig.model_validate(
            a_registry([moved, *without("content-similarity-judge", "llm-council")])
        )

    assert (
        "shard-outcomes sits at state/llm-council/ and is listed in family "
        "content-similarity-judge"
    ) in str(refusal.value)


def test_a_file_at_the_top_of_state_names_its_family_by_its_stem() -> None:
    """The one ledger with no folder is named for its file, and a rename is refused."""
    retirements = a_family(LedgerName.FEED_RETIREMENTS.value)
    renamed = {**retirements, "name": "retirements"}

    with pytest.raises(ValidationError) as refusal:
        LedgersConfig.model_validate(
            a_registry([renamed, *without(LedgerName.FEED_RETIREMENTS.value)])
        )

    assert (
        "feed-retirements sits at state/feed-retirements.csv and is listed in family "
        "retirements"
    ) in str(refusal.value)


def test_a_member_named_for_the_wrong_place_stops_the_build_naming_it() -> None:
    """The name rule, proved able to fire by filing one ledger inside another family.

    `seen` moves under the judge's folder, so every other rule still holds and
    `LedgerName.SEEN` becomes the one name that no longer says where it sits.
    """
    judge = a_family("content-similarity-judge")
    seen = a_family(LedgerName.SEEN.value)["ledgers"][0]
    nested = {**seen, "prefix": ["content-similarity-judge", LedgerName.SEEN.value]}
    widened = {**judge, "ledgers": [*judge["ledgers"], nested]}

    with pytest.raises(ValidationError) as refusal:
        LedgersConfig.model_validate(
            a_registry([widened, *without("content-similarity-judge", LedgerName.SEEN.value)])
        )

    assert "LedgerName.SEEN should be CONTENT_SIMILARITY_JUDGE_SEEN" in str(refusal.value)


@pytest.mark.parametrize("member", list(LedgerName), ids=lambda m: m.value)
def test_a_ledger_sits_where_it_sat_before_the_registry(member: LedgerName) -> None:
    """Path parity, extension included, against the module git holds at the base."""
    old_relpath, old_path, _ = AT_THE_BASE[member.name]
    covers = COVERS[paths.entry(member).grain]

    if old_path is not None:
        assert paths.path(STATE, member, covers).as_posix() == old_path
    if old_relpath is not None:
        assert paths.relpath(member, covers) == old_relpath


@pytest.mark.parametrize("member", list(LedgerName), ids=lambda m: m.value)
def test_a_day_tree_root_is_where_it_was(member: LedgerName) -> None:
    """Tree-root parity, the nested trees included."""
    _, _, old_root = AT_THE_BASE[member.name]

    if old_root is None:
        with pytest.raises(ValueError, match="no day tree to walk"):
            paths.tree_root(STATE, member)
        return
    assert paths.tree_root(STATE, member).as_posix() == old_root


def test_the_two_forms_of_one_address_agree() -> None:
    """`path` and `relpath` are the same answer, so neither can drift alone."""
    root = Path("anywhere")
    for member in LedgerName:
        covers = COVERS[paths.entry(member).grain]
        under = paths.path(root, member, covers).relative_to(root).as_posix()
        assert paths.relpath(member, covers) == f"{paths.STATE_DIRNAME}/{under}"


@pytest.mark.parametrize("member", sorted(DAY_TREES), ids=lambda m: m.value)
def test_a_dated_ledger_handed_no_period_refuses(member: LedgerName) -> None:
    """`path` never guesses a day, because a guessed day files a row out of reach."""
    with pytest.raises(ValueError, match="needs the YYYY-MM-DD day"):
        paths.path(STATE, member)


def test_a_flat_ledger_handed_a_period_refuses() -> None:
    """One file has no period, so a caller passing one has the wrong ledger."""
    with pytest.raises(ValueError, match="names no period"):
        paths.path(STATE, LedgerName.FEED_RETIREMENTS, A_DAY)


def test_the_claimed_roots_differ_from_the_base_only_by_the_names_given() -> None:
    """The protected set, compared by name with what the sweep protected before.

    A claim is a family name now, so every folder claimed before is still
    claimed under the name it has today. One addition is a file's stem, which
    the sweep never meets because it only looks at directories. The other two
    are the renamed empty ledgers, which leave their old names behind.
    """
    assert ledger.claimed_roots() - CLAIMED_AT_THE_BASE == {
        "feed-retirements",
        "candidate-models",
        "item-health-summary",
    }
    assert CLAIMED_AT_THE_BASE - ledger.claimed_roots() == {"validation", "telemetry-aggregate"}


def test_every_directory_under_state_is_claimed_or_owned_elsewhere() -> None:
    """The census behind the parity check, driven from a fixed list rather than a walk.

    Every child of `state/` in the checkout today, and who answers for it. Four
    are ledgers other modules own and one is a trial root; everything else is the
    registry's. A directory in neither set is a directory the trial sweep would
    empty, which is the failure this row removes. The list is fixed, so this
    costs the same whatever the archive holds (Guardrail #12).
    """
    elsewhere = {"traces", "day-metrics", "digest-fragments", "score-archive"}
    trial = {"pipeline-tests"}
    on_disk = {
        "content-similarity-judge",
        "counterfactual-scores",
        "day-metrics",
        "digest-fragments",
        "feed-health",
        "host-fingerprint",
        "item-health",
        "llm-council",
        "pipeline-tests",
        "published",
        "score-index",
        "scores",
        "seen",
        "span-rollup",
        "traces",
        "visual-prunes",
    }

    assert ledger.claimed_roots() & elsewhere == set()
    assert on_disk - ledger.claimed_roots() - elsewhere == trial


def test_every_entry_carries_the_fields_its_grain_needs() -> None:
    """A flat file names itself; a day directory has no extension."""
    for member in LedgerName:
        held = paths.entry(member)
        assert (held.stem is not None) == (held.grain is Grain.FLAT)
        assert (held.suffix is None) == (held.grain is Grain.DAY_TREE)


def test_every_day_tree_files_as_a_day_directory() -> None:
    """The segment writers and the registry agree on which ledgers hold day directories."""
    assert {member for member in LedgerName if paths.entry(member).grain is Grain.DAY_TREE} == set(
        DAY_TREES
    )


def test_every_family_is_active_until_the_write_path_reads_the_status() -> None:
    """Nothing may be paused or retired yet, because nothing would stop the writes.

    The status is read by no writer today, so a paused family would still be
    written on the next run while the registry said otherwise. All three
    statuses are claimed, so this is about what the pipeline does rather than
    what survives: a retired family keeps its rows either way.
    """
    families = LedgersConfig.from_json(REGISTRY.read_text(encoding="utf-8")).families
    not_active = sorted(
        f"{family.name} ({family.lifecycle_status.value})"
        for family in families
        if family.lifecycle_status is not LifecycleStatus.ACTIVE
    )

    assert not not_active, (
        f"{', '.join(not_active)} is not active. A family cannot be paused or retired "
        "until the write path honours lifecycle_status: today every writer ignores it, "
        "so the family would go on being written."
    )


def test_an_entry_that_walks_out_of_state_is_refused() -> None:
    """A prefix segment is one directory name, so a config cannot address a parent."""
    seen = a_family(LedgerName.SEEN.value)
    escaping = {**seen, "ledgers": [{**seen["ledgers"][0], "prefix": ["..", "elsewhere"]}]}

    with pytest.raises(ValidationError, match="it never leaves state/"):
        LedgersConfig.model_validate(a_registry([escaping, *without(LedgerName.SEEN.value)]))
