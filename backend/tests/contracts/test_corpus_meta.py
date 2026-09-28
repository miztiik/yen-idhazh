"""Does the corpus meta read the day the squash last ran under both of its names?

`last_run` was called `pruned_date` until 2026-09-28. Two readers take it: the
`CorpusMeta` contract, which the harvest and the squash's own record go through,
and `backend/utilities/corpus_squash_due.py`, the standard-library check in front
of the one job that force-pushes `main`, which cannot import the contract. Each
carries its own copy of the old name, so the copies are held to the same keys and
the same preference here - a payload one of them read differently from the other
would be a squash the record and the gate disagree about.
"""

from __future__ import annotations

import json
from typing import Any, Final

import pytest

from idhazh import corpus
from idhazh.contracts.corpus import LAST_RUN_KEY, LEGACY_LAST_RUN_KEY, CorpusMeta
from utilities import corpus_squash_due

pytestmark = pytest.mark.contract

#: Every way a payload can name the day, and both readers must read each one alike.
BOTH_READ: Final[tuple[dict[str, Any], ...]] = (
    {"last_run": "2026-08-30"},
    {"pruned_date": "2026-08-30"},
    {"last_run": "2026-09-01", "pruned_date": "2026-08-30"},
    {"last_run": None, "pruned_date": "2026-08-30"},
    {"last_run": None},
    {"pruned_date": None},
)


def test_the_old_name_is_read_as_last_run_and_written_as_it() -> None:
    read = CorpusMeta.from_json(json.dumps({"version": "2026-08-28", "pruned_date": "2026-08-30"}))

    assert read.last_run == "2026-08-30"
    written = json.loads(read.to_json())
    assert written[LAST_RUN_KEY] == "2026-08-30"
    assert LEGACY_LAST_RUN_KEY not in written


def test_the_new_name_wins_when_a_payload_carries_both() -> None:
    read = CorpusMeta.model_validate({"last_run": "2026-09-01", "pruned_date": "2026-08-30"})
    assert read.last_run == "2026-09-01"


def test_a_last_run_that_is_not_a_day_is_refused_and_never_falls_back() -> None:
    with pytest.raises(ValueError, match="last_run"):
        CorpusMeta.model_validate({"last_run": "yesterday", "pruned_date": "2026-08-30"})


def test_the_contract_and_the_due_check_read_the_same_names_and_prefer_the_same_one() -> None:
    """The alias has two homes, and neither may learn a name the other does not."""
    assert (corpus_squash_due.LAST_RUN_KEY, corpus_squash_due.LEGACY_LAST_RUN_KEY) == (
        LAST_RUN_KEY,
        LEGACY_LAST_RUN_KEY,
    )
    assert LAST_RUN_KEY in CorpusMeta.model_fields
    assert LEGACY_LAST_RUN_KEY not in CorpusMeta.model_fields
    for payload in BOTH_READ:
        by_contract = CorpusMeta.model_validate(payload).last_run
        by_the_check = corpus_squash_due.last_run(payload)
        assert by_contract == (by_the_check.isoformat() if by_the_check else None), payload


def test_a_payload_naming_neither_is_where_the_two_readers_part_on_purpose() -> None:
    """The contract writes the key on every save, so its default costs nothing.

    The due check cannot tell a key that was never written from one a rename
    lost, and a lost key read as "never run" is a force push every day - so it
    refuses, and the job stops before it clones anything.
    """
    assert CorpusMeta.model_validate({}).last_run is None
    with pytest.raises(ValueError, match="neither"):
        corpus_squash_due.last_run({})


def test_a_harvest_keeps_the_day_the_squash_last_ran() -> None:
    """The harvest rewrites this file weekly. Dropping the day would make the squash due at once."""
    before = CorpusMeta(version=CorpusMeta.schema_version(), last_run="2026-08-30")

    after = corpus.census(
        [], previous=before.model_copy(update={"harvested_date": "2026-09-24"}), prompt_digest="0" * 64
    )

    assert after.last_run == "2026-08-30"
