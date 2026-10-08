"""Does every ledger on the door keep no CSV path, and can every door row be filed?

A ledger moves to the door when its entry in `config/ledgers.json` switches to
`raw-and-compact`, and that switch is the only one: every rule here reads it.
Each test holds one place a CSV ledger is written down - the day trees'
settlement table, the union merge driver, the prune verb's CSV targets, a
compaction, a folder a declaration owns - to the moved ledgers. Every test reads
the committed registry and the committed declarations under `config/gardener/`,
never a fixture garden, which holds declarations the committed config does not.

The door table gets a ledger's row before the ledger moves, so it is held here
too: a key or a field the door cannot file fails here rather than at the
ledger's first write.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

import pytest

from idhazh import config, ledger, path_classes
from idhazh.contracts import file_envelope
from idhazh.contracts.file_envelope import Tier
from idhazh.contracts.knobs.gardener import CompactionPolicy
from idhazh.contracts.ledger_name import DAY_TREES, LedgerName
from idhazh.contracts.ledgers import Grain
from idhazh.ledger import arrow_schema, keys
from idhazh.telemetry import prune

pytestmark = pytest.mark.contract

#: Each door ledger's row fields that share a name with a key of the file
#: envelope. The envelope names the file and its writer, and a field of the same
#: name may mean something else; where the door also writes that name on every
#: row, the field takes the place of the door's own cell. So each one is a line
#: written here on purpose, and a ledger with none is written with an empty set.
ENVELOPE_NAMED_FIELDS: Final[Mapping[LedgerName, frozenset[str]]] = {
    LedgerName.GARDENER: frozenset({"attempt", "job", "run_id", "shard"}),
    LedgerName.VISUAL_PRUNES: frozenset({"run_id"}),
    LedgerName.FEED_RETIREMENTS: frozenset(),
    LedgerName.ITEM_HEALTH: frozenset({"run_id", "tier"}),
    LedgerName.ITEM_HEALTH_SUMMARY: frozenset(),
    LedgerName.SUMMARY_QUALITY_EVALS: frozenset({"compression", "run_id"}),
    LedgerName.HOST_FINGERPRINT: frozenset({"job", "run_id", "shard"}),
    LedgerName.COUNTERFACTUAL_SCORES: frozenset({"run_id"}),
    LedgerName.CANDIDATE_MODELS: frozenset({"run_id"}),
    LedgerName.FEED_HEALTH: frozenset({"run_id"}),
    LedgerName.SEEN: frozenset(),
    LedgerName.PUBLISHED: frozenset(),
    LedgerName.RUN_PLAN: frozenset({"run_id"}),
    LedgerName.COUNCIL_RUN_RECORDS: frozenset({"run_id"}),
    LedgerName.CONTENT_SIMILARITY_JUDGE_SCORED_PAIRS: frozenset({"run_id"}),
    LedgerName.CONTENT_SIMILARITY_JUDGE_METRICS: frozenset({"run_id"}),
}


def _door_ledgers() -> frozenset[LedgerName]:
    """Every ledger the committed registry files under the two roots."""
    door = frozenset(
        member for member in LedgerName if ledger.entry(member).grain is Grain.RAW_AND_COMPACT
    )
    assert door, "the registry files no ledger under the two roots, so nothing is checked"
    return door


def _under_state(*segments: str) -> str:
    """A folder under `state/`, spelled the way a declaration's `owns` spells one."""
    return "/".join((ledger.STATE_DIRNAME, *segments))


def test_a_door_ledger_has_no_csv_shape() -> None:
    """A moved ledger leaves the day trees' settlement table and the day trees with it."""
    door = _door_ledgers()

    assert sorted(member.value for member in door & set(keys._TREE_SHAPES)) == []
    assert sorted(member.value for member in door & DAY_TREES) == []


def test_a_door_ledger_takes_no_union_driver() -> None:
    """Every file under the two roots has one writer, so a union has nothing to settle."""
    folders = {_under_state(*ledger.entry(member).prefix) for member in _door_ledgers()}

    assert sorted(folders & set(path_classes.UNION_SAFE)) == []


def test_a_door_ledger_is_not_a_csv_prune_target() -> None:
    """The prune verb's CSV targets delete CSV files, and a moved ledger has none."""
    door = _door_ledgers()

    assert sorted(member.value for member in door & set(prune._TARGET_LEDGERS)) == []


def test_a_compaction_and_a_door_ledger_come_together() -> None:
    """Every door ledger has its compaction, and nothing compacts a ledger on CSV.

    The loader refuses a compaction not named for its ledger's folder, so a
    compaction that loads is the file `config/gardener/compact-<folder>.json`,
    `<folder>` being the ledger's door folder with each `/` written `-`.
    """
    tasks = config.load_gardener().tasks
    compacted = {policy.ledger for policy in tasks.values() if isinstance(policy, CompactionPolicy)}
    door = _door_ledgers()

    assert sorted(member.value for member in door - compacted) == [], (
        "a door ledger has no compaction, so nothing bounds its files under the two roots"
    )
    assert sorted(member.value for member in compacted - door) == [], (
        "a compaction names a ledger the registry still files as CSV"
    )


def test_every_folder_a_declaration_owns_is_one_the_registry_builds() -> None:
    """A declaration owning a folder no ledger is filed in deletes where nothing writes.

    A ledger still on CSV sits at `state/<prefix>`; a door ledger at
    `state/raw/<prefix>` and `state/compact/<prefix>`, and never at its old folder.
    """
    door = _door_ledgers()
    built = {
        _under_state(*ledger.entry(member).prefix) for member in LedgerName if member not in door
    } | {_under_state(tier.value, *ledger.entry(member).prefix) for member in door for tier in Tier}
    tasks = config.load_gardener().tasks
    declared_trial_folders = {
        f"{root}/{tier}/{'/'.join(ledger.door_folders(policy.ledger))}"
        for name, policy in tasks.items()
        if name.startswith("compact-trial-") and isinstance(policy, CompactionPolicy)
        for root in policy.state_roots
        for tier in ("raw", "compact")
    }

    stray = sorted(
        f"config/gardener/{name}.json owns {folder}"
        for name, policy in tasks.items()
        for folder in policy.owns or ()
        if folder.split("/")[0] == ledger.STATE_DIRNAME
        and folder not in built
        and folder not in declared_trial_folders
        and (name, folder)
        not in {
            ("trials", "state/pipeline-tests-production-settings"),
            ("trials", "state/pipeline-tests-no-visual-plan"),
            ("trials", "state/pipeline-tests-parallel-summarization"),
        }
        and not (
            name == "trials"
            and folder.startswith("state/pipeline-tests/")
            and folder.endswith("/traces")
        )
    )

    assert stray == [], (
        f"{stray}: a folder under state/ that the registry does not build for any ledger"
    )


@pytest.mark.parametrize("member", list(keys._DOOR_SHAPES), ids=lambda member: member.value)
def test_every_door_key_names_fields_its_contract_declares(member: LedgerName) -> None:
    """A key cell the contract lacks settles nothing, and an unmapped field stops the write."""
    shape = keys._DOOR_SHAPES[member]
    fields = list(shape.model.model_fields)

    assert sorted(set(shape.key) - set(fields)) == []
    assert [column.name for column in arrow_schema.columns_of(shape.model)] == fields


def test_every_door_field_with_an_envelope_name_is_listed() -> None:
    named = set(file_envelope._KEYS)
    found = {
        member: frozenset(set(shape.model.model_fields) & named)
        for member, shape in keys._DOOR_SHAPES.items()
    }

    assert found == dict(ENVELOPE_NAMED_FIELDS)
