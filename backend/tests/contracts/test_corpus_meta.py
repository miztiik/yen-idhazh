"""Do the two readers of the corpus meta read the day the squash last ran alike?

Two readers take `last_run`: the `CorpusMeta` contract, which the harvest and the
squash's own record go through, and `backend/utilities/corpus_squash_due.py`, the
standard-library check in front of the one job that force-pushes `main`, which
cannot import the contract. Each spells the key itself, so the two are held to the
same key here - a payload one of them read differently from the other would be a
squash the record and the gate disagree about. The key was called `pruned_date`
until 2026-09-28, and neither reader takes that name now.
"""

from __future__ import annotations

from typing import Any, Final

import pytest

from idhazh import corpus
from idhazh.contracts.corpus import LAST_RUN_KEY, CorpusMeta
from utilities import corpus_squash_due

pytestmark = pytest.mark.contract

#: Every way a payload can name the day, and both readers must read each one alike.
BOTH_READ: Final[tuple[dict[str, Any], ...]] = (
    {"last_run": "2026-08-30"},
    {"last_run": None},
)


def test_a_last_run_that_is_not_a_day_is_refused() -> None:
    with pytest.raises(ValueError, match="last_run"):
        CorpusMeta.model_validate({"last_run": "yesterday"})


def test_the_contract_and_the_due_check_read_the_same_name() -> None:
    """The key has two homes, and neither may spell it differently from the other."""
    assert corpus_squash_due.LAST_RUN_KEY == LAST_RUN_KEY
    assert LAST_RUN_KEY in CorpusMeta.model_fields
    for payload in BOTH_READ:
        by_contract = CorpusMeta.model_validate(payload).last_run
        by_the_check = corpus_squash_due.last_run(payload)
        assert by_contract == (by_the_check.isoformat() if by_the_check else None), payload


def test_the_old_name_is_refused_by_both_readers() -> None:
    """A file only the old name dates is refused, never read as a squash that never ran."""
    with pytest.raises(ValueError, match="pruned_date"):
        CorpusMeta.model_validate({"pruned_date": "2026-08-30"})
    with pytest.raises(ValueError, match="names no last_run"):
        corpus_squash_due.last_run({"pruned_date": "2026-08-30"})


def test_a_payload_naming_neither_is_where_the_two_readers_part_on_purpose() -> None:
    """The contract writes the key on every save, so its default costs nothing.

    The due check cannot tell a key that was never written from one a rename
    lost, and a lost key read as "never run" is a force push every day - so it
    refuses, and the job stops before it clones anything.
    """
    assert CorpusMeta.model_validate({}).last_run is None
    with pytest.raises(ValueError, match="names no last_run"):
        corpus_squash_due.last_run({})


def test_a_harvest_keeps_the_day_the_squash_last_ran() -> None:
    """The harvest rewrites this file weekly. Dropping the day would make the squash due at once."""
    before = CorpusMeta(version=CorpusMeta.schema_version(), last_run="2026-08-30")

    after = corpus.census(
        [], previous=before.model_copy(update={"harvested_date": "2026-09-24"}), prompt_digest="0" * 64
    )

    assert after.last_run == "2026-08-30"
