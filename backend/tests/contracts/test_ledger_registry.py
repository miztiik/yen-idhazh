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

from idhazh import assemble, ledger, telemetry
from idhazh.contracts.base import ServerJob
from idhazh.contracts.ledger_name import DAY_TREES, LedgerName
from idhazh.contracts.ledgers import Grain, LedgersConfig
from idhazh.ledger import paths
from idhazh.telemetry.publish import day_metrics

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
#:
#: Two folders are not the old module's answer either, because it built no
#: folder for a ledger filed by month or by stamp. Each is the folder its callers
#: reached by joining the ledger's name onto the state root - `retention` for the
#: item-health summary - or, for the judge's archive, the folder `path` files
#: every record into.
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
    "SUMMARY_QUALITY_EVALS": (
        "state/scores/2026/09/18",
        "state/scores/2026/09/18",
        "state/scores",
    ),
    "CANDIDATE_MODELS": (
        "state/candidate-models/2026/09/18",
        "state/candidate-models/2026/09/18",
        "state/candidate-models",
    ),
    "ITEM_HEALTH_SUMMARY": (
        "state/item-health-summary/2026-09.csv",
        "state/item-health-summary/2026-09.csv",
        "state/item-health-summary",
    ),
    "PUBLISHED": (
        "state/published/2026/09/18.csv",
        "state/published/2026/09/18.csv",
        "state/published",
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
        "state/content-similarity-judge/archive",
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
    # The three below were never in the old ledger module. Each row is what its
    # owning module built before the registry took its address: the trace day
    # directory and the trace root from `telemetry.traces` and `retention`, the
    # record and its root from `day_metrics`, and the day's blocks and their root
    # from `assemble` and `retention`.
    "TRACES": (
        "state/traces/2026/09/18",
        "state/traces/2026/09/18",
        "state/traces",
    ),
    "DAY_METRICS": (
        "state/day-metrics/2026/09/18.json",
        "state/day-metrics/2026/09/18.json",
        "state/day-metrics",
    ),
    "DIGEST_FRAGMENTS": (
        "state/digest-fragments/2026/09/18",
        "state/digest-fragments/2026/09/18",
        "state/digest-fragments",
    ),
}

#: What each of those three owners built for one fixed writer on `A_DAY`, file
#: name included, read by calling the owner's own function before it was pointed
#: at the registry.
A_RUN: Final = "2026-09-18-35786586868"
OWNER_BUILT_AT_THE_BASE: Final[dict[str, str]] = {
    "trace": "state/traces/2026/09/18/2026-09-18-1-1-work-00.jsonl",
    "day record": "state/day-metrics/2026/09/18.json",
    "run block": f"state/digest-fragments/2026/09/18/{A_RUN}.json",
}

#: Which directories the old state cleanup protected before the registry claimed
#: them, from the same commit.
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

#: The ledgers that file under `state/raw/` and `state/compact/` through the door.
#: They have no registry address now - the four registry builders refuse them by
#: name - so they have no row above. The gardener was never a CSV tree; the feed
#: retirements and the cleanup record were, and the one-shot migration that moved
#: them spells where they sat.
THROUGH_THE_DOOR: Final = frozenset(
    member for member in LedgerName if paths.entry(member).grain is Grain.RAW_AND_COMPACT
)
#: Every ledger the registry still builds a CSV address for.
CSV_LEDGERS: Final = [member for member in LedgerName if member not in THROUGH_THE_DOOR]


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

    A ledger left out of the old Python set was a directory the trial-tree
    cleanup silently emptied. Here it is a payload that will not validate, and the
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
        "shard-outcomes sits at state/llm-council/ and is listed in family content-similarity-judge"
    ) in str(refusal.value)


def test_a_ledger_with_no_folder_is_refused_even_when_it_is_one_file() -> None:
    """Every family is a folder under `state/`, so no ledger sits loose at its top.

    The retirements were the one ledger that did, as `state/feed-retirements.csv`,
    and the family check named that family by the file's stem. They moved under
    `state/raw/`, and the exception went with them: a flat file with no prefix
    is refused now, the way every other grain already was.
    """
    judge = a_family("content-similarity-judge")
    loose = [
        {**held, "prefix": []} if held["grain"] == Grain.FLAT.value else held
        for held in judge["ledgers"]
    ]
    assert loose != judge["ledgers"], "the judge's family holds no flat ledger to lift out"

    with pytest.raises(ValidationError, match="has no prefix, so its files would sit loose"):
        LedgersConfig.model_validate(
            a_registry([{**judge, "ledgers": loose}, *without("content-similarity-judge")])
        )


def test_a_member_named_for_the_wrong_place_stops_the_build_naming_it() -> None:
    """The name rule, proved able to fire by filing one ledger inside another family.

    `day-metrics` moves under the judge's folder, so every other rule still holds
    and `LedgerName.DAY_METRICS` becomes the one name that no longer says where
    it sits. It is a ledger the registry still builds a CSV address for: a ledger
    filed under the two roots is refused first for a prefix that is not its name.
    """
    judge = a_family("content-similarity-judge")
    metrics = a_family(LedgerName.DAY_METRICS.value)["ledgers"][0]
    nested = {**metrics, "prefix": ["content-similarity-judge", LedgerName.DAY_METRICS.value]}
    widened = {**judge, "ledgers": [*judge["ledgers"], nested]}

    with pytest.raises(ValidationError) as refusal:
        LedgersConfig.model_validate(
            a_registry(
                [widened, *without("content-similarity-judge", LedgerName.DAY_METRICS.value)]
            )
        )

    assert "LedgerName.DAY_METRICS should be CONTENT_SIMILARITY_JUDGE_DAY_METRICS" in str(
        refusal.value
    )


@pytest.mark.parametrize("member", CSV_LEDGERS, ids=lambda m: m.value)
def test_a_ledger_sits_where_it_sat_before_the_registry(member: LedgerName) -> None:
    """Path parity, extension included, against the module git holds at the base."""
    old_relpath, old_path, _ = AT_THE_BASE[member.name]
    covers = COVERS[paths.entry(member).grain]

    if old_path is not None:
        assert paths.path(STATE, member, covers).as_posix() == old_path
    if old_relpath is not None:
        assert paths.relpath(member, covers) == old_relpath


@pytest.mark.parametrize("member", CSV_LEDGERS, ids=lambda m: m.value)
def test_a_day_tree_root_is_where_it_was(member: LedgerName) -> None:
    """Tree-root parity, the nested trees included."""
    _, _, old_root = AT_THE_BASE[member.name]

    if old_root is None:
        with pytest.raises(ValueError, match="no day tree to walk"):
            paths.tree_root(STATE, member)
        return
    assert paths.tree_root(STATE, member).as_posix() == old_root


def test_the_two_forms_of_one_folder_agree() -> None:
    """`tree_relpath` is `tree_root` in POSIX form, the way `relpath` is `path`'s."""
    for member in CSV_LEDGERS:
        if paths.entry(member).grain is Grain.FLAT:
            continue
        assert paths.tree_relpath(member) == paths.tree_root(STATE, member).as_posix()


def test_every_month_ledger_and_every_stamped_ledger_has_a_folder() -> None:
    """A ledger filed by month or by stamp names each file after its period, in one folder.

    That folder is what a caller walks to find every month or every stamp, so it
    has to be the directory each of the ledger's files sits in.
    """
    periods = {Grain.MONTH_FILE, Grain.STAMPED}
    members = [member for member in LedgerName if paths.entry(member).grain in periods]

    assert {paths.entry(member).grain for member in members} == periods
    for member in members:
        filed = paths.path(STATE, member, COVERS[paths.entry(member).grain])
        assert filed.parent == paths.tree_root(STATE, member)


def test_a_flat_ledger_has_no_folder_to_walk_and_the_refusal_names_it() -> None:
    """A flat file shares its folder, so a walk handed that folder would read other files."""
    flat = [member for member in LedgerName if paths.entry(member).grain is Grain.FLAT]

    assert flat
    for member in flat:
        with pytest.raises(ValueError, match=f"^{member.value} is one file in a folder"):
            paths.tree_root(STATE, member)
        with pytest.raises(ValueError, match=f"^{member.value} is one file in a folder"):
            paths.tree_relpath(member)


def test_the_two_forms_of_one_address_agree() -> None:
    """`path` and `relpath` are the same answer, so neither can drift alone."""
    root = Path("anywhere")
    for member in CSV_LEDGERS:
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
        paths.path(STATE, LedgerName.CONTENT_SIMILARITY_JUDGE_HOLDOUT_PAIRS, A_DAY)


def test_the_claimed_roots_differ_from_the_base_only_by_the_names_given() -> None:
    """The protected set, compared by name with what the sweep protected before.

    A claim is a family name now, so every folder claimed before is still
    claimed under the name it has today. One addition is a file's stem, which
    the sweep never meets because it only looks at directories. Two are the
    renamed empty ledgers, which leave their old names behind, and one more is
    the eval ledger, renamed after its files were moved; the ID folder it had
    is gone. Three are the folders other modules used to own, protected before
    by a list typed into the sweep itself and now by the registry. One is the
    gardener's own ledger, which files under the two roots and is claimed like
    every family. The last two are not families at all: they are the roots the
    ledger door files under, claimed so the sweep never reads them as a trial
    run's trees.
    """
    assert ledger.claimed_roots() - CLAIMED_AT_THE_BASE == {
        "feed-retirements",
        "candidate-models",
        "item-health-summary",
        "summary-quality-evals",
        "traces",
        "day-metrics",
        "digest-fragments",
        "gardener",
        "raw",
        "run-plan",
        "compact",
    }
    assert CLAIMED_AT_THE_BASE - ledger.claimed_roots() == {
        "validation",
        "telemetry-aggregate",
        "scores",
        "score-index",
    }


def test_the_three_owners_build_the_paths_they_built_before() -> None:
    """Each owner now composes its address from the registry, and lands on the same bytes.

    The parity table above holds each ledger's directory. This holds the whole
    file name as well, because two of the three mint a name inside that
    directory and the name is where a writer and a reader would part company.
    """
    built = {
        "trace": telemetry.committed_trace_path(
            STATE, run_id="2026-09-18-1", attempt=1, job=ServerJob.WORK, shard=0
        ),
        "day record": day_metrics.day_metrics_path(STATE, A_DAY),
        "run block": assemble.fragment_path(STATE, date=A_DAY, run_id=A_RUN),
    }
    spelled = {
        "trace": telemetry.committed_trace_relpath(
            run_id="2026-09-18-1", attempt=1, job=ServerJob.WORK, shard=0
        ),
        "day record": day_metrics.day_metrics_relpath(A_DAY),
    }

    assert {what: where.as_posix() for what, where in built.items()} == OWNER_BUILT_AT_THE_BASE
    for what, relpath in spelled.items():
        assert relpath == OWNER_BUILT_AT_THE_BASE[what]


def test_every_entry_carries_the_fields_its_grain_needs() -> None:
    """Directory-backed ledgers have no extension; only a flat file needs a stem."""
    unsuffixed = {Grain.DAY_TREE, Grain.RAW_AND_COMPACT}
    for member in LedgerName:
        held = paths.entry(member)
        assert (held.stem is not None) == (held.grain is Grain.FLAT)
        assert (held.suffix is None) == (held.grain in unsuffixed)


def test_a_ledger_under_the_two_roots_has_no_registry_address() -> None:
    """All four registry builders refuse it by name and point at the ones that can build it."""
    assert {
        LedgerName.GARDENER,
        LedgerName.FEED_RETIREMENTS,
        LedgerName.VISUAL_PRUNES,
    } <= THROUGH_THE_DOOR
    for member in sorted(THROUGH_THE_DOOR):
        refusal = f"^{member.value} files by raw-and-compact: .* Ask raw_path"
        with pytest.raises(ValueError, match=refusal):
            paths.path(STATE, member, A_DAY)
        with pytest.raises(ValueError, match=refusal):
            paths.relpath(member, A_DAY)
        with pytest.raises(ValueError, match=refusal):
            paths.tree_root(STATE, member)
        with pytest.raises(ValueError, match=refusal):
            paths.tree_relpath(member)


def test_a_door_ledger_that_is_its_own_family_keeps_its_own_prefix() -> None:
    """A self-family ledger stays at `<root>/<name>/`, not a nested spelling."""
    gardener = a_family(LedgerName.GARDENER.value)
    moved = {**gardener, "ledgers": [{**gardener["ledgers"][0], "prefix": ["gardener", "x"]}]}

    with pytest.raises(ValidationError, match="is its own family"):
        LedgersConfig.model_validate(a_registry([moved, *without(LedgerName.GARDENER.value)]))


def test_a_nested_door_ledger_prefix_must_end_with_its_value() -> None:
    """The envelope keeps the ledger value, so the folder ends with that value too."""
    judge = a_family("content-similarity-judge")
    scored = next(
        held
        for held in judge["ledgers"]
        if held["name"] == LedgerName.CONTENT_SIMILARITY_JUDGE_SCORED_PAIRS.value
    )
    moved = {
        **judge,
        "ledgers": [
            *[held for held in judge["ledgers"] if held is not scored],
            {
                **scored,
                "grain": Grain.RAW_AND_COMPACT.value,
                "prefix": ["content-similarity-judge", "deep"],
                "suffix": None,
            },
        ],
    }

    with pytest.raises(ValidationError, match="not scored-pairs"):
        LedgersConfig.model_validate(a_registry([moved, *without("content-similarity-judge")]))


def test_every_day_tree_files_as_a_day_directory() -> None:
    """Every settled day tree is a day directory, and the two that are not settled are named.

    A trace is JSON lines and a run's block of a day is one JSON file, so
    neither has rows for a settlement key to repeat: both are day directories a
    writer files into, and neither is a settled day tree. A third day directory
    fails here until somebody decides which it is.
    """
    day_directories = {
        member for member in LedgerName if paths.entry(member).grain is Grain.DAY_TREE
    }

    assert day_directories - set(DAY_TREES) == {LedgerName.TRACES, LedgerName.DIGEST_FRAGMENTS}
    assert set(DAY_TREES) <= day_directories


def test_an_entry_that_walks_out_of_state_is_refused() -> None:
    """A prefix segment is one directory name, so a config cannot address a parent."""
    seen = a_family(LedgerName.SEEN.value)
    escaping = {**seen, "ledgers": [{**seen["ledgers"][0], "prefix": ["..", "elsewhere"]}]}

    with pytest.raises(ValidationError, match="it never leaves state/"):
        LedgersConfig.model_validate(a_registry([escaping, *without(LedgerName.SEEN.value)]))
