"""What happens when a run reads back a payload written before the contract moved?"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

import pytest
from conftest import CONTRACT_FIXTURES_DIR, SCHEMAS_DIR, read_text
from pydantic import ValidationError

from idhazh.contracts.base import Contract, StalePayloadError
from idhazh.contracts.console_band import ConsoleBand, ConsoleRoute, RouteId
from idhazh.contracts.console_payloads import CONSOLE_PAYLOADS, payloads_by_stem
from idhazh.contracts.export import CONTRACTS
from idhazh.contracts.item_health import DROPPED_CELLS, RETIRED_CELLS, ItemHealthRow
from idhazh.contracts.knobs.console import ConsoleConfig
from idhazh.contracts.knobs.observability import ObservabilityConfig
from idhazh.contracts.knobs.windows import months_a_window_can_touch
from idhazh.contracts.public_run_day import PublicRunDay
from idhazh.contracts.public_telemetry import PublicTelemetryRow
from idhazh.contracts.visual_decision import VisualDecision

pytestmark = pytest.mark.contract


def _staged(tmp_path: Path, payload: dict[str, Any], name: str = "x.visual.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _a_decision() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(
        read_text(CONTRACT_FIXTURES_DIR / "visual-decision" / "chart-rendered.json")
    )
    return payload


def test_a_payload_written_before_a_field_was_renamed_is_named_not_called_invalid(
    tmp_path: Path,
) -> None:
    """The real incident, reduced to its two facts.

    Run 33951249328 wrote its visual decisions at 08:23, a field rename merged,
    and the rebuild at 09:03 read them with the new contract. What it reported
    was three validation errors about fields, which points an operator at the
    payload - and the payload is fine. The stamp is what says otherwise, so the
    stamp is what decides.
    """
    payload = _a_decision()
    payload["version"] = "2026-01-01"
    payload["routed_at"] = payload.pop("decided_at")

    with pytest.raises(StalePayloadError) as raised:
        VisualDecision.read(_staged(tmp_path, payload))

    message = str(raised.value)
    assert "2026-01-01" in message, "the stamp the payload was written under is missing"
    assert VisualDecision.schema_version() in message, "the stamp this build reads is missing"
    assert "re-run the stage that wrote it" in message, "the remedy is missing"
    assert isinstance(raised.value.__cause__, ValidationError), "the parser's own error is lost"


def test_a_payload_stamped_with_this_build_is_still_an_ordinary_validation_error(
    tmp_path: Path,
) -> None:
    """The half that keeps this from being a blanket excuse.

    Identical damage, current stamp. Nothing straddled a contract change here,
    so this is a defect in the payload and it must read like one. A guard that
    caught this too would hide every real bug behind a story about timing.
    """
    payload = _a_decision()
    payload["version"] = VisualDecision.schema_version()
    payload["routed_at"] = payload.pop("decided_at")

    with pytest.raises(ValidationError):
        VisualDecision.read(_staged(tmp_path, payload))


def test_an_older_payload_this_build_can_still_read_just_reads(tmp_path: Path) -> None:
    """Most older payloads are readable, and refusing them would be the worse bug.

    A stamp older than the build's is the normal case after any additive change,
    which is what the base class already promises. The stamp selects which
    failure this would be; it never fails on its own.
    """
    payload = _a_decision()
    payload["version"] = "2026-01-01"

    assert VisualDecision.read(_staged(tmp_path, payload)).version == "2026-01-01"


def _a_sealed_item_row() -> dict[str, Any]:
    return dict(
        json.loads(read_text(CONTRACT_FIXTURES_DIR / "item-health-row" / "published.json"))
    )


@pytest.mark.parametrize("dropped", sorted(DROPPED_CELLS))
def test_a_sealed_row_carrying_a_column_the_contract_dropped_still_reads(
    dropped: str, tmp_path: Path
) -> None:
    """The incident this migration exists for, one dropped column at a time.

    A work shard seals one of these the moment it finishes an item and a later
    job of the same run reads it back hours afterwards. Run 35537015073 lost its
    digest to exactly this: `cgroup_peak_bytes` left the row while the run was
    in flight, and the rebuild refused a payload that was correct under the
    contract that wrote it. A dropped column has no replacement, so the cell is
    the only thing lost and the day is not.
    """
    payload = _a_sealed_item_row()
    payload["version"] = "2026-01-01"
    payload[dropped] = None

    row = ItemHealthRow.read(_staged(tmp_path, payload, "ai-01.health.json"))

    assert row.version == "2026-01-01"
    assert not hasattr(row, dropped), "a dropped column is gone, not carried"


def test_a_sealed_row_carrying_a_column_the_contract_renamed_is_still_named_stale(
    tmp_path: Path,
) -> None:
    """The half that keeps the migration narrow.

    A column in `RETIRED_CELLS` moved to another column, so a reader that
    dropped it would publish a row missing a value that exists - which is the
    silent loss `docs/architecture/publishing/committing.md` refuses. Only a
    column with nothing to move to is dropped; everything else still stops the
    run and names both stamps.
    """
    retired = sorted(RETIRED_CELLS)[0]
    payload = _a_sealed_item_row()
    payload["version"] = "2026-01-01"
    payload[retired] = "summary"

    with pytest.raises(StalePayloadError) as raised:
        ItemHealthRow.read(_staged(tmp_path, payload, "ai-01.health.json"))

    assert "2026-01-01" in str(raised.value)
    assert ItemHealthRow.schema_version() in str(raised.value)


def test_the_payload_a_stale_error_names_leaves_the_process_posix_and_relative(
    tmp_path: Path,
) -> None:
    """CLAUDE.md section 2, at the one boundary this error crosses."""
    payload = _a_decision()
    payload["version"] = "2026-01-01"
    payload["routed_at"] = payload.pop("decided_at")

    with pytest.raises(StalePayloadError) as raised:
        VisualDecision.read(_staged(tmp_path, payload, "world-01.visual.json"))

    named = raised.value.payload
    assert named == "world-01.visual.json"
    assert "\\" not in named and ":" not in named and not named.startswith("/")


def test_every_contract_can_be_read_through_the_stamped_boundary() -> None:
    """The boundary is on the base class, so no contract can be left out of it.

    Cheap to state and worth stating: the next contract someone adds gets this
    for free, and a subclass that quietly replaced `read` fails here.
    """
    boundary = inspect.getattr_static(Contract, "read")
    for model in CONTRACTS:
        assert inspect.getattr_static(model, "read") is boundary, model.__name__


def test_every_console_read_resolves_to_exactly_one_committed_schema() -> None:
    """The inventory's whole job: no dataset without a shape, no shape twice.

    A dataset the console fetches with no schema file is the gap this closes -
    the producer, the consumer and the drift gate would each work out
    their own answer. Two files for one shape is the other failure, and it is
    the one that lets a committed shard stop validating.
    """
    for entry in CONSOLE_PAYLOADS:
        stem = entry.contract.__schema_stem__
        assert (SCHEMAS_DIR / f"{stem}.schema.json").is_file(), entry.reader
        assert entry.contract in CONTRACTS, f"{stem} is not exported"

    stems = payloads_by_stem()
    assert len(stems) == 7, "ten console reads answer off seven shapes"
    assert set(stems) == {entry.contract.__schema_stem__ for entry in CONSOLE_PAYLOADS}


def test_a_console_payload_says_where_it_is_written_and_why_it_crosses() -> None:
    """An inventory row with no destination is a note, not an instruction.

    Row 9 writes these payloads off this list, so a blank `published_to` would
    be a producer with nowhere to put its file. The path is checked for the form
    CLAUDE.md section 2 allows out of a process, because it is copied into a
    workflow's `REFRESH_PATHS` verbatim.
    """
    for entry in CONSOLE_PAYLOADS:
        assert entry.published_to.startswith("frontend/public/"), entry.reader
        assert "\\" not in entry.published_to and ":" not in entry.published_to
        assert entry.why.endswith("."), entry.reader
        assert entry.reader.strip() == entry.reader and entry.reader


@pytest.mark.parametrize(
    ("projection", "source", "expected"),
    [
        (PublicTelemetryRow, ItemHealthRow, {"canonical_url", "url_key", "detail"}),
    ],
)
def test_a_forbidden_cell_is_on_the_ledger_and_off_the_projection(
    projection: type[Contract], source: type[Contract], expected: set[str]
) -> None:
    """A refusal that names a cell nothing has is decoration.

    Both halves matter. A name absent from the source ledger would be a list
    that has drifted off the thing it guards, and would keep passing while the
    real address column crossed under another name. A name present on the
    projection is the leak itself, and the contract module already refuses that
    at import - this says so a second time where a reader looking for the trust
    boundary will find it (Guardrail #11).
    """
    entry = payloads_by_stem()[projection.__schema_stem__]
    assert entry.forbidden == expected
    assert expected <= set(source.model_fields), "the list has drifted off its ledger"
    assert not (expected & set(projection.model_fields))


def test_a_published_shape_with_no_refusals_says_so_in_its_own_words() -> None:
    """An empty list is a real answer and it needs a reason on the page.

    Six of the nine shapes forbid nothing, because nothing on them came from the
    open web. That is a claim, so the module making it has to state it - an
    empty `frozenset()` with no sentence beside it reads as a list nobody
    filled in.
    """
    for entry in CONSOLE_PAYLOADS:
        if entry.forbidden:
            continue
        source = inspect.getmodule(entry.contract)
        assert source is not None and source.__doc__ is not None, entry.reader
        prose = f"{source.__doc__}\n{entry.why}".lower()
        assert any(
            phrase in prose
            for phrase in ("never the response body", "no cell", "nothing", "our own")
        ), f"{entry.contract.__name__} forbids nothing and does not say why"


def test_the_band_refuses_a_link_that_could_leave_the_site() -> None:
    """The one cell on the band a browser follows.

    A protocol-relative href is an origin wearing a path's clothes, and a site
    that never calls home (Guardrail #1) must not be able to grow one. The grammar is
    what refuses it, so a producer cannot compose a link out of fetched text.
    """
    for bad in ("//evil.example/", "https://evil.example/", "/console", "/Console/"):
        with pytest.raises(ValidationError):
            ConsoleRoute(
                id=RouteId.MODEL,
                label="Summaries",
                href=bad,
                description="What the model wrote.",
                worst=None,
                severity=0,
                carries="Feed failures are on Pipelines.",
            )


def test_the_band_refuses_a_worst_route_the_strip_does_not_carry() -> None:
    """The strip is the console's only navigation, so a band pointing off it is
    a link that goes nowhere."""
    band = ConsoleBand.read(CONTRACT_FIXTURES_DIR / "console-band" / "newest-day.json")
    assert band.worst is not None
    payload = band.model_dump(mode="json")
    with pytest.raises(ValidationError, match="not on the strip"):
        ConsoleBand.model_validate(payload | {"routes": []})


def test_the_band_refuses_months_that_run_backwards() -> None:
    """The console pans by index, so a repeat or an inversion reads as a jump
    backwards in time rather than as a malformed payload."""
    band = ConsoleBand.read(CONTRACT_FIXTURES_DIR / "console-band" / "newest-day.json")
    payload = band.model_dump(mode="json")
    for months in (["2026-09", "2026-08"], ["2026-08", "2026-08"]):
        with pytest.raises(ValidationError, match="oldest first"):
            ConsoleBand.model_validate(payload | {"months": months})


def test_a_day_cannot_draw_more_charts_than_it_published() -> None:
    """The charts are a subset of the items, counted from the same payload, so a
    row claiming more is a producer that counted two different trees."""
    day = PublicRunDay.read(CONTRACT_FIXTURES_DIR / "public-run-day" / "five-runs.json")
    payload = day.model_dump(mode="json")
    with pytest.raises(ValidationError, match="claims"):
        PublicRunDay.model_validate(payload | {"published_items": 3, "published_charts": 7})


def test_every_published_month_payload_has_a_non_null_retention_knob() -> None:
    """A payload a run appends to with no age is a directory that grows for ever.

    `item_health_aggregate_keep_months` and `score_archive_keep_months` are null
    today and each says in its own description why. Nothing minted for the
    console may join them: a null default that spreads stops reading as a
    decision (CLAUDE.md Guardrail #12).
    """
    observability = ObservabilityConfig()
    monthly = {
        entry.published_to.rsplit("/", 1)[0].removeprefix("frontend/public/")
        for entry in CONSOLE_PAYLOADS
        if "<YYYY-MM>" in entry.published_to
    }
    assert monthly == {
        "telemetry",
        "run-days",
        "day-metrics",
        "machine",
        "span-rollup",
    }
    for root in monthly:
        knob = f"public_{root.replace('-', '_')}_keep_months"
        months = getattr(observability, knob)
        assert months is not None, f"observability.{knob} may not be null"
        assert months >= months_a_window_can_touch(ConsoleConfig().max_window_days)
