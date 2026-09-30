"""Does an item row reach the host record for the machine that read it?"""

from __future__ import annotations

from typing import Any, Final

import pytest

from idhazh.contracts.base import ServerJob
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.item_health import (
    MACHINE_CELLS_RENAMED,
    ItemHealthRow,
    ItemOutcome,
    ItemStage,
)
from idhazh.ledger import HOST_FINGERPRINT_KEY

pytestmark = pytest.mark.contract

A_DATE = "2026-09-17"
A_RUN = "2026-09-17-1"

#: The item-health column that holds each cell of the host key. The machine's
#: job and shard sit under `machine_` names, because the ledger door stamps its
#: own `job` and `shard` on every row for the writer that filed it.
ITEM_SIDE: Final = tuple(MACHINE_CELLS_RENAMED.get(name, name) for name in HOST_FINGERPRINT_KEY)


def an_item(**cells: Any) -> ItemHealthRow:
    """One published item-health row, built by calling the contract and nothing else."""
    built: dict[str, Any] = {
        "version": ItemHealthRow.schema_version(),
        "date": A_DATE,
        "run_id": A_RUN,
        "item_id": "ai-abcdefghjkmnpqrs",
        "url_key": "a" * 64,
        "canonical_url": "https://example.com/a",
        "vertical": "ai",
        "source_id": "a-source",
        "stage": ItemStage.PUBLISH,
        "outcome": ItemOutcome.OK,
    }
    return ItemHealthRow(**(built | cells))


def a_host(job: ServerJob, shard: int) -> HostFingerprintRow:
    """One host record for one job of one run, built the same way."""
    return HostFingerprintRow(
        version=HostFingerprintRow.schema_version(),
        date=A_DATE,
        run_id=A_RUN,
        job=job,
        shard=shard,
        fingerprint=f"{shard:016x}",
        cpu_model="AMD EPYC 7763 64-Core Processor",
        measured_at="2026-09-17T06:00:00Z",
    )


def test_a_worker_row_and_its_host_record_spell_one_key() -> None:
    """The item row's four cells are the host key's four values, so the join is an equality.

    The item row names the machine's job and shard `machine_job` and
    `machine_shard`, and the host row names them `job` and `shard`: the values
    are the same, only the headings differ. Both rows are built here rather than
    read off a committed day, so the pair this asserts about is one this
    repository has never written and can still be asked about (`CLAUDE.md`
    section 13).
    """
    item = an_item(machine_shard=3, machine_job=ServerJob.WORK)
    host = a_host(ServerJob.WORK, 3)

    assert HOST_FINGERPRINT_KEY == ("date", "run_id", "job", "shard")
    assert ITEM_SIDE == ("date", "run_id", "machine_job", "machine_shard")
    assert tuple(item.csv_row()[name] for name in ITEM_SIDE) == tuple(
        host.csv_row()[name] for name in HOST_FINGERPRINT_KEY
    )


def test_three_of_the_four_columns_resolve_to_more_than_one_machine() -> None:
    """**The test that would have caught the absence.**

    Without `machine_job` an item row could spell only three of the four, and
    three of the four is not a key: `plan`, `work`, `assemble` and `runtime` all
    write shard 0, so a lookup on the short key finds every job of the run rather
    than the one that read the item.

    Two host rows are built for one run, because the archive cannot be asked
    this question - it holds the shape that made the gap, not the shape that
    shows it.
    """
    records = [a_host(ServerJob.WORK, 0), a_host(ServerJob.VISUALS, 0)]
    short = ("date", "run_id", "shard")
    wanted = an_item(machine_shard=0, machine_job=ServerJob.WORK).csv_row()

    def found(key: tuple[str, ...]) -> list[HostFingerprintRow]:
        return [
            record
            for record in records
            if all(
                record.csv_row()[name] == wanted[MACHINE_CELLS_RENAMED.get(name, name)]
                for name in key
            )
        ]

    assert len(found(short)) == 2, "date, run and shard name every job of the run"
    assert [record.job for record in found(HOST_FINGERPRINT_KEY)] == [ServerJob.WORK]


def test_a_job_on_an_item_row_names_a_worker_as_well() -> None:
    """Half a key points at every shard that job ran, which is not an answer."""
    with pytest.raises(ValueError, match="names a machine_shard as well"):
        an_item(machine_job=ServerJob.WORK)


def test_a_shard_with_no_job_is_the_shape_every_committed_row_holds() -> None:
    """The converse is deliberately not a rule, and it is the half that had to be got right.

    Every read validates each row back through the contract, so a
    two-directional rule would refuse every row written before the job column
    on the first run after it landed.
    """
    assert an_item(machine_shard=0).machine_job is None


def test_a_row_written_before_the_column_reads_back_with_no_job() -> None:
    """An absent heading is an absent reading, never shard 0's job.

    Built here as the header an earlier generation wrote - the shard under its
    old heading `shard`, and no job column at all - so the case is present
    rather than waited for.
    """
    earlier = an_item(machine_shard=3, machine_job=ServerJob.WORK).csv_row()
    del earlier["machine_job"]
    earlier["shard"] = earlier.pop("machine_shard")

    read_back = ItemHealthRow.from_csv_row(earlier)

    assert read_back.machine_job is None
    assert read_back.machine_shard == 3, "the old heading still reads, under the new name"
