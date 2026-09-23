"""Does an item row reach the host record for the machine that read it?"""

from __future__ import annotations

from typing import Any

import pytest

from idhazh.contracts.base import ServerJob
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.item_health import ItemHealthRow, ItemOutcome, ItemStage
from idhazh.ledger import HOST_FINGERPRINT_KEY

pytestmark = pytest.mark.contract

A_DATE = "2026-09-17"
A_RUN = "2026-09-17-1"


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
    """The four columns are the same four values, so the join is an equality.

    Both rows are built here rather than read off a committed day, so the pair
    this asserts about is one this repository has never written and can still be
    asked about (`CLAUDE.md` section 13).
    """
    item = an_item(shard=3, job=ServerJob.WORK)
    host = a_host(ServerJob.WORK, 3)

    assert HOST_FINGERPRINT_KEY == ("date", "run_id", "job", "shard")
    assert tuple(item.csv_row()[name] for name in HOST_FINGERPRINT_KEY) == tuple(
        host.csv_row()[name] for name in HOST_FINGERPRINT_KEY
    )


def test_three_of_the_four_columns_resolve_to_more_than_one_machine() -> None:
    """**The test that would have caught the absence.**

    Without `job` an item row could spell only three of the four, and three of
    the four is not a key: `plan`, `work`, `assemble` and `runtime` all write
    shard 0, so a lookup on the short key finds every job of the run rather than
    the one that read the item.

    Two host rows are built for one run, because the archive cannot be asked
    this question - it holds the shape that made the gap, not the shape that
    shows it.
    """
    records = [a_host(ServerJob.WORK, 0), a_host(ServerJob.VISUALS, 0)]
    short = ("date", "run_id", "shard")
    wanted = an_item(shard=0, job=ServerJob.WORK).csv_row()

    def found(key: tuple[str, ...]) -> list[HostFingerprintRow]:
        return [
            record
            for record in records
            if all(record.csv_row()[name] == wanted[name] for name in key)
        ]

    assert len(found(short)) == 2, "date, run and shard name every job of the run"
    assert [record.job for record in found(HOST_FINGERPRINT_KEY)] == [ServerJob.WORK]


def test_a_job_on_an_item_row_names_a_worker_as_well() -> None:
    """Half a key points at every shard that job ran, which is not an answer."""
    with pytest.raises(ValueError, match="names a shard as well"):
        an_item(job=ServerJob.WORK)


def test_a_shard_with_no_job_is_the_shape_every_committed_row_holds() -> None:
    """The converse is deliberately not a rule, and it is the half that had to be got right.

    Every read of a committed day parses each row back through `from_csv_row`
    (`day_shards.parsed`), so a two-directional rule would refuse every row
    written before this column on the first run after it landed.
    """
    assert an_item(shard=0).job is None


def test_a_row_written_before_the_column_reads_back_with_no_job() -> None:
    """An absent heading is an absent reading, never shard 0's job.

    Built here as the header an earlier generation wrote - the current column
    list with `job` taken out of it - so the case is present rather than waited
    for.
    """
    earlier = an_item(shard=3, job=ServerJob.WORK).csv_row()
    del earlier["job"]

    read_back = ItemHealthRow.from_csv_row(earlier)

    assert read_back.job is None
    assert read_back.shard == 3, "the column beside it still reads"
