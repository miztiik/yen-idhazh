"""Do the index and watermark shapes accept what a compaction writes, and refuse everything else?

One test per cell of the shapes' accept-and-refuse table. An accepted payload is
a committed sample, read inside the test that accepts it; a refused one is built
from a sample by the test that refuses it, so every refusal differs from a
payload that loads in exactly the one way it is about (CLAUDE.md section 13).
Nothing here reads a committed ledger.

A refusal comes from one of two places, and each is checked for what it can
say. The validators know the ledger and the day or period, so their
message has to name both: that is what tells an operator which file to open. A
refusal the field types make on their own - a name this project did not mint, a
stamp with a fraction of a second, a count nobody may write any more, a run id
that is only a number - is raised before any validator runs, so it names the
field it came from and the value it refused, and the path the caller was
reading names the rest.

What this cannot settle: whether these shapes serve the compaction well. That
is answered by the first run that writes them.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest
from conftest import CONTRACT_FIXTURES_DIR, read_text
from pydantic import ValidationError
from pydantic_core import ErrorDetails

from idhazh.contracts.base import Contract
from idhazh.contracts.file_envelope import FileEnvelope
from idhazh.contracts.ledger_index import CompactIndex, EntryState, RawDayIndex, Watermark

pytestmark = pytest.mark.contract


def _sample(stem: str, name: str) -> dict[str, Any]:
    """One committed sample as plain JSON, read by the test that asks for it."""
    payload: dict[str, Any] = json.loads(read_text(CONTRACT_FIXTURES_DIR / stem / f"{name}.json"))
    return payload


def _refusal(model: type[Contract], payload: dict[str, Any]) -> ErrorDetails:
    """The one error a refused payload raises. More than one means the case is not one change."""
    with pytest.raises(ValidationError) as raised:
        model.model_validate(payload)
    errors = raised.value.errors()
    assert len(errors) == 1, f"the case should break one rule and it broke {len(errors)}: {errors}"
    return errors[0]


def _names_the_file(error: ErrorDetails, *words: str) -> None:
    """A validator's refusal names the ledger and the day or period it was checking."""
    assert error["type"] == "value_error", error
    for word in words:
        assert word in error["msg"], f"the refusal does not name {word!r}: {error['msg']}"


@pytest.mark.parametrize("stamp", ["2026-09-30", "2026-10-01"])
@pytest.mark.parametrize(
    ("model", "stem", "name"),
    [
        (FileEnvelope, "file-envelope", "a-raw-file"),
        (RawDayIndex, "raw-day-index", "a-populated-day"),
        (CompactIndex, "compact-index", "a-yearly-index"),
        (Watermark, "watermark", "a-yearly-watermark"),
    ],
)
def test_surviving_ledger_payloads_keep_their_fields_when_read_under_an_older_stamp(
    model: type[Contract], stem: str, name: str, stamp: str
) -> None:
    payload = _sample(stem, name)
    original = model.model_validate(payload)

    reread = model.model_validate(payload | {"version": stamp})

    assert reread.version == stamp
    assert reread.model_dump(exclude={"version"}) == original.model_dump(exclude={"version"})


# --- RawDayIndex -------------------------------------------------------------


@pytest.mark.parametrize("name", ["a-populated-day", "an-empty-day", "a-json-format-day"])
def test_a_raw_day_index_accepts_a_populated_day_an_empty_day_and_a_json_format_day(
    name: str,
) -> None:
    payload = _sample("raw-day-index", name)

    index = RawDayIndex.model_validate(payload)

    assert index.files == payload["files"]
    assert index.date == payload["date"]


@pytest.mark.parametrize("name", ["a-populated-day", "an-empty-day", "a-json-format-day"])
def test_every_raw_day_sample_carries_the_digest_of_its_own_list(name: str) -> None:
    """The digest is taken over the names joined with one newline, so an empty day digests ''."""
    index = RawDayIndex.model_validate(_sample("raw-day-index", name))

    joined = "\n".join(index.files).encode("utf-8")
    assert hashlib.sha256(joined).hexdigest() == index.content_sha256


def test_a_raw_day_index_refuses_two_files_listed_out_of_order_by_ledger_and_day() -> None:
    """The digest is taken over the list as written, so one set in two orders would carry two."""
    payload = _sample("raw-day-index", "a-populated-day")
    first, second, *rest = payload["files"]

    error = _refusal(RawDayIndex, payload | {"files": [second, first, *rest]})

    _names_the_file(error, payload["ledger"], payload["date"], "out of order")


def test_a_raw_day_index_refuses_a_file_it_names_twice_by_ledger_and_day() -> None:
    payload = _sample("raw-day-index", "a-populated-day")
    files = payload["files"]

    error = _refusal(RawDayIndex, payload | {"files": [files[0], *files]})

    _names_the_file(error, payload["ledger"], payload["date"], "more than once", files[0])


def test_a_raw_day_index_refuses_a_csv_name_because_the_project_never_minted_one() -> None:
    """A filename can reach a fetch address, so only a name this project minted is admitted."""
    payload = _sample("raw-day-index", "a-populated-day")
    minted = payload["files"][0]
    stem = minted.removesuffix(".parquet")

    error = _refusal(RawDayIndex, payload | {"files": [f"{stem}.csv"]})

    assert (error["type"], error["loc"]) == ("string_pattern_mismatch", ("files", 0))


def test_a_raw_day_index_refuses_a_listed_at_with_a_fraction_of_a_second() -> None:
    """One spelling of an instant, so a document read and written again is the same bytes."""
    payload = _sample("raw-day-index", "a-populated-day")
    fractional = payload["listed_at"].removesuffix("Z") + ".5Z"

    error = _refusal(RawDayIndex, payload | {"listed_at": fractional})

    assert (error["type"], error["loc"]) == ("string_pattern_mismatch", ("listed_at",))


def test_a_raw_day_index_refuses_a_file_count_even_when_the_count_is_right() -> None:
    """The length of `files` is the count, so a second copy of it is refused rather than kept."""
    payload = _sample("raw-day-index", "a-populated-day")

    error = _refusal(RawDayIndex, payload | {"file_count": len(payload["files"])})

    assert (error["type"], error["loc"]) == ("extra_forbidden", ("file_count",))


# --- CompactIndex ------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "period"),
    [("a-daily-index", "daily"), ("a-monthly-index", "monthly"), ("a-yearly-index", "yearly")],
)
def test_a_compact_index_accepts_an_ordered_daily_monthly_and_yearly_index(
    name: str, period: str
) -> None:
    payload = _sample("compact-index", name)

    index = CompactIndex.model_validate(payload)

    assert index.period.value == period
    assert [entry.covers for entry in index.entries] == [e["covers"] for e in payload["entries"]]


def test_a_compact_index_writes_one_entry_a_line_and_reads_back_what_it_wrote() -> None:
    index = CompactIndex.model_validate(_sample("compact-index", "a-daily-index"))

    text = index.to_json()

    entry_lines = [line for line in text.splitlines() if line.strip().startswith('{"')]
    assert len(entry_lines) == len(index.entries)
    assert CompactIndex.from_json(text).to_json() == text


def test_a_daily_index_refuses_an_entry_that_covers_a_month_by_ledger_and_period() -> None:
    """A stamp may be a day or a month, so the index is what says which one it lists."""
    payload = _sample("compact-index", "a-daily-index")
    a_month = _sample("compact-index", "a-monthly-index")["entries"][-1]

    error = _refusal(CompactIndex, payload | {"entries": [*payload["entries"], a_month]})

    _names_the_file(error, payload["ledger"], payload["period"], a_month["covers"])


def test_a_yearly_index_refuses_an_entry_that_covers_a_month_by_ledger_and_period() -> None:
    """A year and a month are both stamps, so a yearly index must say it lists years."""
    payload = _sample("compact-index", "a-yearly-index")
    a_month = _sample("compact-index", "a-monthly-index")["entries"][-1]

    error = _refusal(CompactIndex, payload | {"entries": [*payload["entries"], a_month]})

    _names_the_file(error, payload["ledger"], payload["period"], a_month["covers"], "YYYY")


def test_a_compact_index_refuses_entries_out_of_order_by_ledger_and_period() -> None:
    """The newest daily entry is the newest day compacted only while the list ascends."""
    payload = _sample("compact-index", "a-daily-index")

    error = _refusal(CompactIndex, payload | {"entries": list(reversed(payload["entries"]))})

    _names_the_file(error, payload["ledger"], payload["period"], "out of order")


def test_a_compact_index_refuses_a_period_it_lists_twice_by_ledger_and_period() -> None:
    """Two entries for one day would be two answers to how many rows that day holds."""
    payload = _sample("compact-index", "a-daily-index")
    newest = payload["entries"][-1]

    error = _refusal(CompactIndex, payload | {"entries": [*payload["entries"], newest]})

    _names_the_file(error, payload["ledger"], payload["period"], newest["covers"], "more than once")


@pytest.mark.parametrize(
    ("name", "state"),
    [("an-empty-day", EntryState.EMPTY), ("a-lost-day", EntryState.LOST)],
)
def test_a_daily_index_accepts_a_day_with_no_file_among_packed_days(
    name: str, state: EntryState
) -> None:
    """A day the packing looked at and wrote no file for is an entry, so it is not a hole."""
    index = CompactIndex.model_validate(_sample("compact-index", name))

    with_no_file = [entry for entry in index.entries if entry.state is not EntryState.PACKED]
    assert [entry.state for entry in with_no_file] == [state]
    assert (with_no_file[0].rows, with_no_file[0].bytes, with_no_file[0].lost_days) == (0, 0, [])


def test_a_monthly_index_accepts_a_month_that_names_its_lost_days() -> None:
    index = CompactIndex.model_validate(_sample("compact-index", "a-month-with-lost-days"))

    empty, packed = index.entries
    assert (empty.state, empty.rows, empty.bytes) == (EntryState.EMPTY, 0, 0)
    assert (packed.state, packed.lost_days, packed.set_aside) == (
        EntryState.PACKED,
        ["2026-08-12", "2026-08-13"],
        1,
    )


def test_an_index_written_before_entries_had_a_state_reads_as_all_packed() -> None:
    """Every committed index has this shape, and none is rewritten to gain the new fields."""
    payload = _sample("compact-index", "an-index-written-before-entries-had-a-state")
    assert all(set(entry) == {"covers", "rows", "bytes"} for entry in payload["entries"])

    index = CompactIndex.model_validate(payload)

    assert index.version == payload["version"]
    assert [(entry.state, entry.lost_days, entry.set_aside) for entry in index.entries] == [
        (EntryState.PACKED, [], 0) for _ in payload["entries"]
    ]
    assert [(entry.covers, entry.rows, entry.bytes) for entry in index.entries] == [
        (entry["covers"], entry["rows"], entry["bytes"]) for entry in payload["entries"]
    ]


@pytest.mark.parametrize(("field", "count"), [("bytes", 7950), ("rows", 3)])
@pytest.mark.parametrize("name", ["an-empty-day", "a-lost-day"])
def test_an_entry_with_no_file_that_counts_rows_or_bytes_is_refused_by_ledger_and_period(
    name: str, field: str, count: int
) -> None:
    """An entry says either that a file exists or that none does, never both."""
    payload = _sample("compact-index", name)
    target = next(entry for entry in payload["entries"] if entry["state"] != "packed")
    entries = [entry | {field: count} if entry is target else entry for entry in payload["entries"]]

    error = _refusal(CompactIndex, payload | {"entries": entries})

    _names_the_file(error, payload["ledger"], payload["period"], target["covers"], "no file")


def test_a_lost_day_outside_its_month_is_refused_by_ledger_and_period() -> None:
    payload = _sample("compact-index", "a-month-with-lost-days")
    month = payload["entries"][-1]
    stray = month | {"lost_days": [*month["lost_days"], "2026-09-01"]}

    error = _refusal(CompactIndex, payload | {"entries": [*payload["entries"][:-1], stray]})

    _names_the_file(error, payload["ledger"], payload["period"], month["covers"], "2026-09-01")


def test_a_lost_day_that_is_no_calendar_day_is_refused_by_ledger_and_period() -> None:
    """`DateStamp` counts digits only, so the index is what refuses 2026-08-32."""
    payload = _sample("compact-index", "a-month-with-lost-days")
    month = payload["entries"][-1]
    stray = month | {"lost_days": ["2026-08-32"]}

    error = _refusal(CompactIndex, payload | {"entries": [*payload["entries"][:-1], stray]})

    _names_the_file(error, payload["ledger"], payload["period"], month["covers"], "2026-08-32")


@pytest.mark.parametrize(
    "lost_days",
    [["2026-08-13", "2026-08-12"], ["2026-08-12", "2026-08-12"]],
    ids=["descending", "twice"],
)
def test_lost_days_out_of_order_are_refused_by_ledger_and_period(lost_days: list[str]) -> None:
    payload = _sample("compact-index", "a-month-with-lost-days")
    month = payload["entries"][-1] | {"lost_days": lost_days}

    error = _refusal(CompactIndex, payload | {"entries": [*payload["entries"][:-1], month]})

    _names_the_file(error, payload["ledger"], payload["period"], month["covers"], "out of order")


def test_a_daily_entry_that_lists_lost_days_is_refused_by_ledger_and_period() -> None:
    """A lost day of a daily index is an entry of its own, so it is told in one place only."""
    payload = _sample("compact-index", "a-daily-index")
    first, *rest = payload["entries"]
    listed = first | {"lost_days": [first["covers"]]}

    error = _refusal(CompactIndex, payload | {"entries": [listed, *rest]})

    _names_the_file(error, payload["ledger"], payload["period"], first["covers"], "lost_days")


def test_a_state_the_contract_does_not_declare_is_refused() -> None:
    payload = _sample("compact-index", "an-empty-day")
    first, *rest = payload["entries"]

    error = _refusal(CompactIndex, payload | {"entries": [first | {"state": "missing"}, *rest]})

    assert (error["type"], error["loc"]) == ("enum", ("entries", 0, "state"))


def test_a_negative_set_aside_count_is_refused() -> None:
    payload = _sample("compact-index", "a-lost-day")
    first, *rest = payload["entries"]

    error = _refusal(CompactIndex, payload | {"entries": [first | {"set_aside": -1}, *rest]})

    assert (error["type"], error["loc"]) == ("greater_than_equal", ("entries", 0, "set_aside"))


# --- Watermark ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "through"),
    [
        ("a-daily-watermark", "2026-09-23"),
        ("a-monthly-watermark", "2026-08"),
        ("a-yearly-watermark", "2025"),
    ],
)
def test_a_watermark_accepts_a_day_a_month_or_a_year_on_a_watermark_of_that_period(
    name: str, through: str
) -> None:
    mark = Watermark.model_validate(_sample("watermark", name))

    assert mark.through == through


def test_a_daily_watermark_refuses_to_stand_on_a_month_by_ledger_and_period() -> None:
    """A compaction resumes after this stamp, and a daily one cannot resume after a month."""
    payload = _sample("watermark", "a-daily-watermark")
    a_month = _sample("watermark", "a-monthly-watermark")["through"]

    error = _refusal(Watermark, payload | {"through": a_month})

    _names_the_file(error, payload["ledger"], payload["period"], a_month)


def test_a_monthly_watermark_refuses_to_stand_on_a_year_by_ledger_and_period() -> None:
    """A month and a year are both stamps, and a monthly compaction resumes after a month."""
    payload = _sample("watermark", "a-monthly-watermark")
    a_year = _sample("watermark", "a-yearly-watermark")["through"]

    error = _refusal(Watermark, payload | {"through": a_year})

    _names_the_file(error, payload["ledger"], payload["period"], a_year)


def test_a_watermark_refuses_a_run_id_that_is_only_the_run_number() -> None:
    """A run id is `<YYYY-MM-DD>-<execution>` everywhere, so a bare number is a second spelling."""
    payload = _sample("watermark", "a-daily-watermark")
    bare = payload["run_id"].rsplit("-", 1)[1]

    error = _refusal(Watermark, payload | {"run_id": bare})

    assert (error["type"], error["loc"]) == ("string_pattern_mismatch", ("run_id",))


def test_a_raw_day_index_accepts_one_size_per_file() -> None:
    payload = _sample("raw-day-index", "a-populated-day")
    sizes = list(range(len(payload["files"])))

    index = RawDayIndex.model_validate(payload | {"bytes": sizes})

    assert index.bytes == sizes


def test_a_raw_day_index_accepts_no_sizes_for_an_old_compaction_listing() -> None:
    payload = _sample("raw-day-index", "a-populated-day")
    payload.pop("bytes", None)

    index = RawDayIndex.model_validate(payload)

    assert index.bytes is None


def test_a_raw_day_index_refuses_a_size_count_that_differs_by_ledger_and_day() -> None:
    payload = _sample("raw-day-index", "a-populated-day")

    error = _refusal(RawDayIndex, payload | {"bytes": [1]})

    _names_the_file(error, payload["ledger"], payload["date"], "sizes")


def test_a_raw_day_index_refuses_a_negative_size() -> None:
    payload = _sample("raw-day-index", "a-populated-day")
    sizes = [0 for _ in payload["files"]]
    sizes[0] = -1

    error = _refusal(RawDayIndex, payload | {"bytes": sizes})

    _names_the_file(error, payload["ledger"], payload["date"], "negative")
