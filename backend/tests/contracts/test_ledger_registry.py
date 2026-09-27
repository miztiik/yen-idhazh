"""The registry holds: it names every ledger, and it puts each one where it was.

Four checks, and each one catches what the others cannot. The bijection is the
only one that is new - the other three exist so that replacing twenty-odd
hand-written path functions with one config file moved no byte on disk.

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
from idhazh.contracts.ledgers import Grain, LedgersConfig, LedgerState
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
AT_THE_BASE: Final[dict[str, tuple[str | None, str | None, str | None]]] = {
    "SEEN": ("state/seen/2026/09/18.csv", "state/seen/2026/09/18.csv", "state/seen"),
    "HEALTH": (
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
    "VALIDATION": (
        "state/validation/2026/09/18",
        "state/validation/2026/09/18",
        "state/validation",
    ),
    "TELEMETRY_AGGREGATE": (
        "state/telemetry-aggregate/2026-09.csv",
        "state/telemetry-aggregate/2026-09.csv",
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
    "SCORED_PAIRS": (
        "state/content-similarity-judge/scored-pairs/2026/09/18.csv",
        "state/content-similarity-judge/scored-pairs/2026/09/18.csv",
        "state/content-similarity-judge/scored-pairs",
    ),
    "FITTED_THRESHOLDS": (
        "state/content-similarity-judge/fitted-thresholds/2026/09/18.csv",
        "state/content-similarity-judge/fitted-thresholds/2026/09/18.csv",
        "state/content-similarity-judge/fitted-thresholds",
    ),
    "SIMILARITY_HOLDOUT": (
        "state/content-similarity-judge/holdout-pairs.csv",
        "state/content-similarity-judge/holdout-pairs.csv",
        None,
    ),
    "SCORE_DISTRIBUTION": (
        None,
        "state/content-similarity-judge/score-distribution.json",
        None,
    ),
    "SCORE_ARCHIVE": (
        "state/content-similarity-judge/archive/20260918T120000Z.json",
        "state/content-similarity-judge/archive/20260918T120000Z.json",
        None,
    ),
    "JUDGE_METRICS": (
        "state/content-similarity-judge/metrics/2026/09/18.csv",
        "state/content-similarity-judge/metrics/2026/09/18.csv",
        "state/content-similarity-judge/metrics",
    ),
    "MERGE_LINE_HOLDOUT_SCORES": (
        "state/content-similarity-judge/merge-line-holdout-scores/2026/09/18.csv",
        "state/content-similarity-judge/merge-line-holdout-scores/2026/09/18.csv",
        "state/content-similarity-judge/merge-line-holdout-scores",
    ),
    "SHARD_OUTCOMES": (
        "state/llm-council/shard-outcomes/2026/09/18.csv",
        "state/llm-council/shard-outcomes/2026/09/18.csv",
        "state/llm-council/shard-outcomes",
    ),
    "DAY_VALIDATIONS": (None, None, "state/day-validations"),
}

#: Which directories `prune-state` protected before the registry claimed them,
#: from the same commit. `day-validations` is deliberately absent and the test
#: below names it as the one difference.
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


def a_registry(entries: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """The committed registry as a payload, with its entry list optionally replaced."""
    held: dict[str, Any] = json.loads(REGISTRY.read_text(encoding="utf-8"))
    if entries is not None:
        held["ledgers"] = entries
    return held


def committed_entries() -> list[dict[str, Any]]:
    """The entry list as the file holds it."""
    entries: list[dict[str, Any]] = a_registry()["ledgers"]
    return entries


def test_the_committed_registry_names_every_ledger_exactly_once() -> None:
    """The bijection, over the file the build really reads."""
    entries = LedgersConfig.from_json(REGISTRY.read_text(encoding="utf-8")).ledgers

    assert {held.name for held in entries} == set(LedgerName)
    assert len(entries) == len(LedgerName)


def test_a_ledger_with_no_entry_stops_the_build_naming_it() -> None:
    """The refusal that replaces the hand-coded set, proved able to fire.

    A ledger left out of the old Python set was a directory `prune-state`
    silently emptied. Here it is a payload that will not validate, and the
    message names the ledger an operator has to add.
    """
    kept = [
        held for held in committed_entries() if held["name"] != LedgerName.ITEM_HEALTH.value
    ]

    with pytest.raises(ValidationError) as refusal:
        LedgersConfig.model_validate(a_registry(kept))

    assert "no entry for item-health" in str(refusal.value)


def test_a_ledger_named_twice_stops_the_build_naming_it() -> None:
    """Two entries for one ledger are two answers, and nothing chooses between them."""
    held = committed_entries()

    with pytest.raises(ValidationError) as refusal:
        LedgersConfig.model_validate(a_registry([*held, dict(held[0])]))

    assert "has more than one entry" in str(refusal.value)
    assert held[0]["name"] in str(refusal.value)


def test_an_entry_for_no_ledger_is_refused_by_the_name_it_carries() -> None:
    """The other half of the bijection: a name nobody declared."""
    held = committed_entries()
    invented = [*held, {**held[0], "name": "a-ledger-nobody-declared"}]

    with pytest.raises(ValidationError) as refusal:
        LedgersConfig.model_validate(a_registry(invented))

    assert "a-ledger-nobody-declared" in str(refusal.value)


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


def test_the_registry_claims_what_the_old_set_claimed_and_day_validations() -> None:
    """Known-set parity: exact, except `state/day-validations/`.

    `day-validations` is a real child of `state/`, written by the `validate_days`
    stage, and it was absent from the hand-coded set - so the trial sweep read it
    as a trial tree and deleted files in a production ledger. The registry claims
    every ledger it knows, so it is now protected. `validate_days` and this
    ledger are being decommissioned, which is what erases the difference; it is
    asserted by name here rather than waived.
    """
    claimed = ledger.claimed_roots()

    assert claimed - CLAIMED_AT_THE_BASE == {"day-validations"}
    assert CLAIMED_AT_THE_BASE - claimed == set()


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
        "day-validations",
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


def test_every_committed_ledger_is_live() -> None:
    """Nothing is paused or retired today, and a change to that is a change to read.

    All three states are claimed, so this asserts what the pipeline does rather
    than what survives: a retired ledger keeps its rows either way.
    """
    assert {paths.entry(member).state for member in LedgerName} == {LedgerState.LIVE}


def test_an_entry_that_walks_out_of_state_is_refused() -> None:
    """A prefix segment is one directory name, so a config cannot address a parent."""
    held = committed_entries()
    escaping = [{**held[0], "prefix": ["..", "elsewhere"]}, *held[1:]]

    with pytest.raises(ValidationError, match="it never leaves state/"):
        LedgersConfig.model_validate(a_registry(escaping))
