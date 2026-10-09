"""Does every ledger on the door have its compaction and its folders, and can every door row be filed?

A ledger is on the door when its entry in `config/ledgers.json` is
`raw-and-compact`, and that one switch is what every rule here reads. No ledger
keeps a CSV path any more, so what is left to hold each one to is the rest of
what a ledger on the door owes: a compaction, folders a declaration may own,
and a door row the door can file. Every test reads the committed registry and
the committed declarations under `config/gardener/`, never a fixture garden,
which holds declarations the committed config does not.

The door table holds each door ledger's key and row contract, so it is held
here too: a key or a field the door cannot file fails here rather than at the
ledger's first write.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

import pytest

from idhazh import config, ledger
from idhazh.contracts import file_envelope
from idhazh.contracts.file_envelope import Tier
from idhazh.contracts.knobs.gardener import CompactionPolicy
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.ledgers import Grain
from idhazh.ledger import arrow_schema, keys
from idhazh.ledger.paths import TRIAL_TRACES_DIRNAME

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
    LedgerName.CONTENT_SIMILARITY_JUDGE_MERGE_LINE_HOLDOUT_SCORES: frozenset({"run_id"}),
    LedgerName.CONTENT_SIMILARITY_JUDGE_HOLDOUT_PAIRS: frozenset(),
    LedgerName.RUN_PLAN: frozenset({"run_id"}),
    LedgerName.COUNCIL_RUN_RECORDS: frozenset({"run_id"}),
    LedgerName.CONTENT_SIMILARITY_JUDGE_SCORED_PAIRS: frozenset({"run_id"}),
    LedgerName.CONTENT_SIMILARITY_JUDGE_METRICS: frozenset({"run_id"}),
    LedgerName.CONTENT_SIMILARITY_JUDGE_FITTED_THRESHOLDS: frozenset({"run_id"}),
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


def test_a_compaction_and_a_door_ledger_come_together() -> None:
    """Every door ledger has its compaction, and nothing compacts a ledger outside the door.

    The loader refuses a compaction not named for its folder, so a compaction that
    loads is the file `config/gardener/compact-<folder>.json`.
    """
    tasks = config.load_gardener().tasks
    compacted = {policy.ledger for policy in tasks.values() if isinstance(policy, CompactionPolicy)}
    door = _door_ledgers()

    assert sorted(member.value for member in door - compacted) == [], (
        "a door ledger has no compaction, so nothing bounds its files under the two roots"
    )
    assert sorted(member.value for member in compacted - door) == [], (
        "a compaction names a ledger the registry does not file through the door"
    )


def test_every_folder_a_declaration_owns_is_one_the_registry_builds() -> None:
    """A declaration owning a folder no ledger is filed in deletes where nothing writes.

    A ledger outside the door sits at `state/<prefix>`; a door ledger at
    `state/raw/<prefix>` and `state/compact/<prefix>`, and never at its old folder.
    """
    door = _door_ledgers()
    built = {
        _under_state(*ledger.entry(member).prefix) for member in LedgerName if member not in door
    } | {_under_state(tier.value, *ledger.entry(member).prefix) for member in door for tier in Tier}
    tasks = config.load_gardener().tasks
    state_prefix = f"{ledger.STATE_DIRNAME}/"
    declared_trial_folders = {
        _under_state(tier, root[len(state_prefix) :], *ledger.door_folders(policy.ledger))
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
        and not (
            name == "trials"
            and folder.startswith(f"state/{TRIAL_TRACES_DIRNAME}/")
        )
    )

    assert stray == [], (
        f"{stray}: a folder under state/ that the registry does not build for any ledger"
    )


@pytest.mark.parametrize(
    "member", sorted(keys.door_table_ledgers()), ids=lambda member: member.value
)
def test_every_door_key_names_fields_its_contract_declares(member: LedgerName) -> None:
    """A key cell the contract lacks settles nothing, and an unmapped field stops the write."""
    model = keys.door_contract(member)
    fields = list(model.model_fields)

    assert sorted(set(keys.door_key(member)) - set(fields)) == []
    assert [column.name for column in arrow_schema.columns_of(model)] == fields


def test_every_door_field_with_an_envelope_name_is_listed() -> None:
    named = set(file_envelope._KEYS)
    found = {
        member: frozenset(set(keys.door_contract(member).model_fields) & named)
        for member in keys.door_table_ledgers()
    }

    assert found == dict(ENVELOPE_NAMED_FIELDS)
