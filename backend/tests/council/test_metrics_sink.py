"""Does a row the council knows nothing about survive the whole trip?

Written on a runner, uploaded under a name the collecting job looks for, and
appended to the store the tenant named. Every payload here is declared in this
file, so nothing in it names a judge and the whole module runs in a repository
with no judge in it.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Self

import pytest
import yaml  # type: ignore[import-untyped]
from conftest import REPO_ROOT, read_text
from pydantic import Field

from idhazh.contracts.base import ChangelogEntry, Contract, DateStamp, RunId
from idhazh.contracts.council_shard_outcome import ShardOutcome
from idhazh.council.metrics_sink import collect_judge_metrics, ship_judge_metrics
from idhazh.council.tenancy import ShardResult, Tenant

COUNCIL_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "llm-council.yml"

#: What the capability writes into on a runner. One directory a night.
METRICS_DIRNAME = "metrics"


class PaperMetrics(Contract):
    """A tenant's metrics row that measures nothing at all.

    **A fixture, not a mock** (Guardrail #7). A mock stands in for a real
    implementation and hands back a plausible value it did not compute. This
    computes its own two cells and stands in for nobody: it exists so the
    shipping capability is gated on a row the council owns rather than on a
    judge's metrics contract, which would give the venue a false red the day
    that judge moved a column and would make this file unrunnable with no judge
    in the tree.

    It is deliberately absent from `contracts.export.CONTRACTS`, so no schema is
    generated for it and the drift gate never reports an orphan. It declares one
    changelog entry because the base class refuses a subclass without one, and it
    hand-declares the three CSV members like every other row under `state/`.
    """

    __schema_stem__: ClassVar[str] = "paper-tenant-metrics"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-21",
            change="Initial shape: the date, and how many units the tenant read.",
            why="The shipping capability needs a row that names no judge.",
        ),
    )

    date: DateStamp = Field(description="The date this row is about.")
    units: int = Field(ge=0, description="How many units of its own work the tenant read.")

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        return tuple(cls.model_fields)

    def csv_row(self) -> dict[str, str]:
        payload = self.model_dump(mode="json")
        return {name: str(payload[name]) for name in payload}

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> Self:
        payload: dict[str, Any] = {name: row.get(name, "") for name in cls.model_fields}
        return cls.model_validate(payload)


class OtherPaperMetrics(PaperMetrics):
    """A second tenant's row, with a column the first one does not have.

    Two shapes through one capability is the whole claim: the council writes what
    `csv_row()` returns and reads no field of it by name, so a tenant may declare
    any columns it likes.
    """

    __schema_stem__: ClassVar[str] = "other-paper-tenant-metrics"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-21",
            change="Initial shape: the paper row, plus a column only this tenant has.",
            why="One capability has to carry two tenants' columns without knowing either.",
        ),
    )

    warmth: float = Field(description="A reading only this tenant takes.")


@dataclass(frozen=True)
class PaperTenant:
    """A tenant that runs no model, judges nothing, and answers all seven members.

    A fixture for the same reason `PaperMetrics` is: it makes the venue testable
    without a tenant existing. Nothing here is stubbed - every member computes
    the answer it returns.
    """

    judge_id: str = "paper-tenant"
    shard_count: int = 1
    committed_paths: tuple[str, ...] = ("state/paper-tenant/metrics",)

    def nights_outstanding(self, *, window: tuple[DateStamp, ...]) -> tuple[DateStamp, ...]:
        """It has counted every night it was ever asked about."""
        return ()

    def prepare(self, *, date: DateStamp, run_id: RunId) -> ShardResult:
        return ShardResult(outcome=ShardOutcome.NOTHING_TO_DO)

    def run_shard(
        self,
        *,
        date: DateStamp,
        run_id: RunId,
        shard: int,
        shards: int,
        deadline: float,
    ) -> ShardResult:
        return ShardResult(
            outcome=ShardOutcome.COMPLETED,
            metrics=_paper_row(date=date, units=shard + 1),
        )

    def settle(self, *, date: DateStamp, run_id: RunId) -> ShardResult:
        return ShardResult(outcome=ShardOutcome.NOTHING_TO_DO)


def _paper_row(date: str = "2026-09-20", units: int = 3) -> PaperMetrics:
    """The base class stamps `version` itself, the way every contract here is built."""
    return PaperMetrics.model_validate({"date": date, "units": units})


def test_a_tenant_the_council_never_named_answers_the_whole_protocol() -> None:
    """Seven members, and the count is checked rather than restated.

    The assignment is the real check and mypy makes it: a structural protocol is
    satisfied by shape, so a tenant declared in this file - with no import of the
    council in it beyond the types - is a tenant.
    """
    tenant: Tenant = PaperTenant()

    declared = {name for name in vars(Tenant) if not name.startswith("_")}
    assert declared == {
        "judge_id",
        "shard_count",
        "committed_paths",
        "nights_outstanding",
        "prepare",
        "run_shard",
        "settle",
    }
    assert tenant.shard_count == 1, "a tenant with no model takes one shard"
    assert tenant.nights_outstanding(window=("2026-09-20",)) == ()


def test_a_shard_result_hands_the_tenants_row_over_whole() -> None:
    """The defect the frozen dataclass exists to stop.

    A pydantic model with a base-typed field drops every subclass column on the
    dump, measured on pydantic 2.13.4 on 2026-09-21. `ShardResult` has no dump at
    all, so the row it carries is the row that was put in it.
    """
    result = PaperTenant().run_shard(
        date="2026-09-20", run_id="2026-09-20-1", shard=2, shards=4, deadline=0.0
    )

    assert result.outcome is ShardOutcome.COMPLETED
    assert result.model_calls is None, "a tenant with no model files null, never zero"
    assert not hasattr(result, "model_dump"), "nothing may flatten a tenant's row"
    assert result.metrics is not None
    assert result.metrics.csv_row() == {"version": "2026-09-21", "date": "2026-09-20", "units": "3"}

    with pytest.raises(AttributeError):
        result.outcome = ShardOutcome.NOTHING_TO_DO  # type: ignore[misc]


def test_a_shipped_row_lands_under_the_tenants_own_slug(tmp_path: Path) -> None:
    """One file a unit, so the collecting job can merge every upload into one tree."""
    out_dir = tmp_path / METRICS_DIRNAME
    path = ship_judge_metrics(_paper_row(), judge_id="paper-tenant", shard=2, out_dir=out_dir)

    assert path == out_dir / "paper-tenant" / "2.csv"
    assert path.read_text(encoding="utf-8") == "version,date,units\n2026-09-21,2026-09-20,3\n"
    assert sorted(child.name for child in path.parent.iterdir()) == ["2.csv"], (
        "the rename leaves no scratch file behind"
    )


def test_a_judge_id_that_is_not_a_slug_never_becomes_a_directory(tmp_path: Path) -> None:
    """It is a path component, and a path built from an unchecked string is a hole."""
    with pytest.raises(ValueError, match="not a slug"):
        ship_judge_metrics(_paper_row(), judge_id="../escape", shard=0, out_dir=tmp_path)


def test_the_collecting_job_appends_every_shipped_row_to_the_store_the_tenant_named(
    tmp_path: Path,
) -> None:
    """The Oracle, end to end: written, named for the download, appended, read back."""
    tenant = PaperTenant()
    shipped = tmp_path / "var" / METRICS_DIRNAME
    for shard in (0, 1):
        ship_judge_metrics(
            _paper_row(units=shard + 1),
            judge_id=tenant.judge_id,
            shard=shard,
            out_dir=shipped,
        )

    into = tmp_path / tenant.committed_paths[0] / "2026" / "09" / "20.csv"
    landed = collect_judge_metrics(
        shipped, judge_id=tenant.judge_id, contract=PaperMetrics, into=into
    )

    assert landed == 2
    assert into.read_text(encoding="utf-8").splitlines() == [
        "version,date,units",
        "2026-09-21,2026-09-20,1",
        "2026-09-21,2026-09-20,2",
    ]
    assert [row.units for row in _read_back(into)] == [1, 2]


def test_a_second_tenants_columns_travel_the_same_path_unchanged(tmp_path: Path) -> None:
    """The capability declares nothing about the payload, so two shapes fit one pipe."""
    shipped = tmp_path / METRICS_DIRNAME
    row = OtherPaperMetrics.model_validate({"date": "2026-09-20", "units": 1, "warmth": 0.5})
    ship_judge_metrics(row, judge_id="other-paper-tenant", shard=0, out_dir=shipped)

    into = tmp_path / "state" / "other-paper-tenant" / "metrics" / "20.csv"
    landed = collect_judge_metrics(
        shipped, judge_id="other-paper-tenant", contract=OtherPaperMetrics, into=into
    )

    assert landed == 1
    assert into.read_text(encoding="utf-8").startswith("version,date,units,warmth\n")


def test_a_truncated_upload_fails_before_it_reaches_the_store(tmp_path: Path) -> None:
    """A row is read back through the contract that wrote it, and refused here."""
    shipped = tmp_path / METRICS_DIRNAME
    path = ship_judge_metrics(_paper_row(), judge_id="paper-tenant", shard=0, out_dir=shipped)
    path.write_text("version,date,units\n2026-09-21,2026-09-20,\n", encoding="utf-8")

    into = tmp_path / "state" / "paper-tenant" / "metrics" / "20.csv"
    with pytest.raises(ValueError):
        collect_judge_metrics(shipped, judge_id="paper-tenant", contract=PaperMetrics, into=into)
    assert not into.exists(), "a store never gains a row the contract refused"


def test_the_upload_name_matches_what_the_collecting_job_downloads() -> None:
    """An artifact nobody downloads is a reading the runner deletes.

    Both sides are read out of the workflow, so a rename of either one fails here
    rather than on a night nobody is watching.
    """
    workflow = yaml.safe_load(read_text(COUNCIL_WORKFLOW))
    uploaded = [
        str(step["with"]["name"])
        for step in workflow["jobs"]["judge"]["steps"]
        if str(step.get("uses", "")).startswith("actions/upload-artifact")
        and METRICS_DIRNAME in str(step["with"]["path"])
    ]
    patterns = [
        str(step["with"]["pattern"])
        for step in workflow["jobs"]["fold"]["steps"]
        if str(step.get("uses", "")).startswith("actions/download-artifact")
        and "pattern" in step["with"]
    ]

    assert len(uploaded) == 1, "one metrics upload a unit, or this test names the wrong step"
    assert any(fnmatch.fnmatch(uploaded[0], pattern) for pattern in patterns), (
        f"{uploaded[0]} is uploaded and no download pattern in the collecting job "
        f"({', '.join(patterns)}) matches it, so the rows are deleted with the runner."
    )


def _read_back(path: Path) -> list[PaperMetrics]:
    """The committed rows, through the contract that wrote them."""
    lines = path.read_text(encoding="utf-8").splitlines()
    columns = lines[0].split(",")
    return [
        PaperMetrics.from_csv_row(dict(zip(columns, line.split(","), strict=True)))
        for line in lines[1:]
    ]
