"""Do declarations grant only their own named ledger and collection folders?"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import CONFIG_DIR, FIXTURES_DIR
from pydantic import TypeAdapter, ValidationError

from idhazh.contracts.knobs.gardener import TaskPolicy
from idhazh.contracts.ledger_name import LedgerName
from idhazh.gardener import ownership
from idhazh.gardener.outcome import Shard
from idhazh.ledger import staging

pytestmark = pytest.mark.contract


def policy(path: Path) -> TaskPolicy:
    return TypeAdapter(TaskPolicy).validate_json(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("name", "ledgers"),
    [
        ("traces", (LedgerName.TRACES,)),
        ("digest-fragments", (LedgerName.DIGEST_FRAGMENTS,)),
        ("telemetry-aggregate", (LedgerName.ITEM_HEALTH_SUMMARY,)),
        ("workflow-artifacts", ()),
        ("workflow-runs", ()),
        ("trials", ()),
    ],
)
def test_named_ledger_and_nonledger_tasks_keep_their_configured_folders(
    name: str, ledgers: tuple[LedgerName, ...]
) -> None:
    declared = policy(CONFIG_DIR / "gardener" / f"{name}.json")
    assert ownership.owned_prefixes(declared, ledgers) == tuple(declared.owns)


def test_a_compaction_derives_its_ledger_folders_from_the_registry() -> None:
    declared = policy(FIXTURES_DIR / "gardener/garden/compact-gardener.json")
    assert ownership.owned_prefixes(declared) == (
        staging.staged_path(LedgerName.GARDENER),
        "state/compact/gardener",
    )
    wrong = declared.model_copy(update={"ledger": LedgerName.COUNCIL_RUN_RECORDS})
    with pytest.raises(ValueError, match="not an owned folder"):
        ownership.owned_prefixes(wrong)


def test_naming_a_ledger_does_not_grant_the_raw_writer_folder_to_a_compact_only_task() -> None:
    declared = policy(FIXTURES_DIR / "gardener/garden/compact-gardener.json")
    compact_only = declared.model_copy(update={"owns": ["state/compact/gardener"]})
    assert ownership.owned_prefixes(compact_only) == ("state/compact/gardener",)


def test_a_ledger_declaration_refuses_a_different_ledgers_configured_folder() -> None:
    declared = policy(CONFIG_DIR / "gardener/traces.json")
    with pytest.raises(ValueError, match="not an owned folder"):
        ownership.owned_prefixes(declared, (LedgerName.DIGEST_FRAGMENTS,))


@pytest.mark.parametrize("root", ["state", "state/raw", "state/compact"])
def test_neither_a_task_nor_a_shard_may_claim_a_blanket_state_root(root: str) -> None:
    declared = policy(CONFIG_DIR / "gardener/trials.json").model_copy(update={"owns": [root]})
    with pytest.raises(ValueError, match="blanket state"):
        ownership.owned_prefixes(declared)
    with pytest.raises(ValidationError, match="blanket state"):
        Shard(
            index=0,
            task_names=(),
            record_path="state/raw/gardener/record.json",
            written_paths=frozenset({"state/raw/gardener/record.json"}),
            deleted_paths=frozenset(),
            owned_prefixes=frozenset({root}),
            message="gardener fixture",
        )
