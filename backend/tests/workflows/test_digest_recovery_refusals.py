"""Does recovery refuse each unsafe, foreign or inconsistent input for its own reason, and accept the same input when it is sound?

Every refusal case changes one thing in an input that is accepted unchanged and asserts the
typed reason, never the wording. Each family opens with that accepted control, so a function
that refuses everything fails here as well as one that accepts too much.
"""

from __future__ import annotations

import hashlib
import io
import json
import stat
import warnings
import zipfile
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final

import pytest
from gardener._garden import an_origin, git, quiet_git
from pipeline._builders import article, row, summary
from retention._trees import health_row

from idhazh import ledger
from idhazh.contracts.article import Article
from idhazh.contracts.base import ServerJob, canonical_json
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.file_envelope import Format, WriterIdentity
from idhazh.contracts.fingerprint import PipelineInputs
from idhazh.contracts.item_health import ItemHealthRow, ItemStage
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.run_plan import PlannedItem, RunPlan
from idhazh.contracts.summary import Summary
from idhazh.ledger import json_lines
from idhazh.stages import common
from idhazh.telemetry.record import HEALTH_SUFFIX
from utilities.digest_recovery_download import (
    PlatformCall,
    SourceRun,
    download,
    fetch_source,
    pages,
    select_artifacts,
)
from utilities.digest_recovery_inputs import (
    RestoredInputs,
    plan_import,
    restore,
    select_plan,
    unpack,
    worker_files,
)
from utilities.digest_recovery_refusal import RecoveryRefusalError, RefusalReason
from utilities.publication_request import Write

from ._recovery_inputs import saved_inputs, zipped

pytestmark = pytest.mark.workflow

#: The commit every sound input claims as its source attempt's code.
SOURCE_COMMIT: Final = "a" * 40
SHARD_ONE_FAILED: Final = frozenset({1})
REPOSITORY: Final = "example/repository"


@dataclass(frozen=True)
class SoundRun:
    """The sound saved run every case starts from, and the files inside its two archives."""

    plan: RunPlan
    archives: Mapping[str, bytes]
    plan_files: Mapping[str, bytes]
    item_files: Mapping[str, bytes]

    @property
    def plan_name(self) -> str:
        (name,) = self.plan_files
        return name

    @property
    def plan_bytes(self) -> bytes:
        return self.plan_files[self.plan_name]


def read_members(archive: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(archive)) as opened:
        return {name: opened.read(name) for name in opened.namelist()}


@pytest.fixture(scope="module")
def sound(tmp_path_factory: pytest.TempPathFactory) -> SoundRun:
    saved, _, archives = saved_inputs(tmp_path_factory.mktemp("saved"), SOURCE_COMMIT)
    return SoundRun(
        saved,
        archives,
        read_members(archives["plan"]),
        read_members(archives["items-0"]),
    )


def a_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    quiet_git(tmp_path, monkeypatch)
    _, repo = an_origin(tmp_path, {"seed": "seed\n"})
    return repo


def an_empty_directory(tmp_path: Path, name: str) -> Path:
    directory = tmp_path / name
    directory.mkdir()
    return directory


def item_directory(repo: Path, saved: RunPlan) -> Path:
    return repo / "backend" / "var" / "run" / saved.date / "items"


# --- unpack -----------------------------------------------------------------------------------


def build_archive(entries: Iterable[tuple[str | zipfile.ZipInfo, bytes]]) -> bytes:
    """One ZIP built entry by entry, so a name or a mode can be as unsafe as a case needs."""
    stream = io.BytesIO()
    with warnings.catch_warnings(), zipfile.ZipFile(stream, "w") as archive:
        warnings.simplefilter("ignore", UserWarning)  # a repeated name warns as it is written
        for entry, data in entries:
            archive.writestr(entry, data)
    return stream.getvalue()


def entry_with_kind(name: str, kind: int, data: bytes) -> tuple[zipfile.ZipInfo, bytes]:
    info = zipfile.ZipInfo(name)
    info.external_attr = (kind | 0o644) << 16
    return info, data


def flip_stored_byte(archive: bytes, stored: bytes) -> bytes:
    """The archive with the first byte of one stored entry changed, so its checksum fails."""
    at = archive.index(stored)
    return archive[:at] + bytes([archive[at] ^ 0xFF]) + archive[at + 1 :]


def declared_deflated(archive: bytes) -> bytes:
    """A one-entry archive whose entry is declared deflated, so its stored bytes fail to inflate."""
    at = archive.index(b"PK\x01\x02") + 10  # The compression method of the first central entry.
    return archive[:at] + zipfile.ZIP_DEFLATED.to_bytes(2, "little") + archive[at + 2 :]


UNSAFE_NAME = RefusalReason.UNSAFE_OR_DUPLICATE_FILE

UNPACK_REFUSALS = [
    pytest.param(b"not a ZIP", RefusalReason.NOT_A_ZIP_ARCHIVE, id="not-a-zip"),
    pytest.param(build_archive([("", b"x")]), UNSAFE_NAME, id="empty-name"),
    pytest.param(build_archive([(".", b"x")]), UNSAFE_NAME, id="current-folder"),
    pytest.param(build_archive([("..", b"x")]), UNSAFE_NAME, id="parent-folder"),
    pytest.param(build_archive([("folder/file.json", b"x")]), UNSAFE_NAME, id="nested-path"),
    pytest.param(build_archive([("../escape", b"x")]), UNSAFE_NAME, id="parent-escape"),
    pytest.param(build_archive([("C:escape", b"x")]), UNSAFE_NAME, id="drive-prefix"),
    # On Windows zipfile rewrites the backslash to a slash, so only Linux reaches its own clause.
    pytest.param(build_archive([("folder\\escape", b"x")]), UNSAFE_NAME, id="backslash"),
    pytest.param(
        build_archive([entry_with_kind("link", stat.S_IFLNK, b"/etc/passwd")]),
        UNSAFE_NAME,
        id="symbolic-link",
    ),
    pytest.param(
        build_archive([("same.json", b"1"), ("same.json", b"2")]), UNSAFE_NAME, id="duplicate-name"
    ),
    pytest.param(
        flip_stored_byte(build_archive([("stored.json", b"stored payload")]), b"stored payload"),
        RefusalReason.CORRUPT_FILE_BYTES,
        id="corrupt-bytes",
    ),
    pytest.param(
        # 0xFF opens a deflate block of the reserved type, which zlib refuses.
        declared_deflated(build_archive([("deflated.json", b"\xffnot a deflate stream")])),
        RefusalReason.CORRUPT_FILE_BYTES,
        id="corrupt-deflated-bytes",
    ),
]


def test_unpack_returns_each_plain_flat_file() -> None:
    archive = build_archive(
        [("implicit-mode.json", b"1"), entry_with_kind("regular-mode.json", stat.S_IFREG, b"2")]
    )
    assert unpack(archive) == {"implicit-mode.json": b"1", "regular-mode.json": b"2"}


@pytest.mark.parametrize(("archive", "reason"), UNPACK_REFUSALS)
def test_unpack_refuses_one_unsafe_archive_for_its_own_reason(
    archive: bytes, reason: RefusalReason
) -> None:
    with pytest.raises(RecoveryRefusalError) as caught:
        unpack(archive)
    assert caught.value.reason is reason


# --- select_artifacts -------------------------------------------------------------------------

SOURCE_RUN: Final = SourceRun(
    id=1,
    run_attempt=2,
    head_sha=SOURCE_COMMIT,
    path=".github/workflows/digest.yml",
    status="completed",
    conclusion="failure",
    run_started_at="2026-10-31T01:00:00Z",
)


def platform_artifact(name: str, **changes: object) -> dict[str, object]:
    return {
        "id": 4,
        "name": name,
        "expired": False,
        "created_at": "2026-10-31T02:00:00Z",
        "digest": f"sha256:{hashlib.sha256(b'archive').hexdigest()}",
        "workflow_run": {"id": 1, "head_sha": SOURCE_COMMIT},
    } | changes


NOT_THIS_ATTEMPT = RefusalReason.ARTIFACT_EXPIRED_FOREIGN_OR_AMBIGUOUS

ARTIFACT_REFUSALS = [
    pytest.param([platform_artifact("plan", expired=True)], NOT_THIS_ATTEMPT, id="expired"),
    pytest.param(
        [platform_artifact("plan", created_at="2026-10-30T02:00:00Z")],
        NOT_THIS_ATTEMPT,
        id="created-before-the-source-attempt",
    ),
    pytest.param(
        [platform_artifact("plan", workflow_run={"id": 2, "head_sha": SOURCE_COMMIT})],
        NOT_THIS_ATTEMPT,
        id="another-run",
    ),
    pytest.param(
        [platform_artifact("plan", workflow_run={"id": 1, "head_sha": "b" * 40})],
        NOT_THIS_ATTEMPT,
        id="another-commit",
    ),
    pytest.param([platform_artifact("plan", digest="")], NOT_THIS_ATTEMPT, id="no-sha256-digest"),
    pytest.param(
        [platform_artifact("plan"), platform_artifact("plan")], NOT_THIS_ATTEMPT, id="two-plans"
    ),
    pytest.param([platform_artifact("items-0")], RefusalReason.NO_PLAN_ARTIFACT, id="no-plan"),
]


def test_select_artifacts_keeps_the_plan_and_items_and_skips_other_artifacts() -> None:
    captures = platform_artifact(
        "model-captures", expired=True, workflow_run={"id": 9, "head_sha": "c" * 40}
    )
    selected = select_artifacts(
        SOURCE_RUN,
        [
            platform_artifact("plan", id=4),
            platform_artifact("items-0", id=5),
            platform_artifact("items-10", id=6),
            captures,
        ],
    )
    assert {name: artifact.id for name, artifact in selected.items()} == {
        "plan": 4,
        "items-0": 5,
        "items-10": 6,
    }


@pytest.mark.parametrize(("values", "reason"), ARTIFACT_REFUSALS)
def test_select_artifacts_refuses_one_broken_listing_for_its_own_reason(
    values: list[dict[str, object]], reason: RefusalReason
) -> None:
    with pytest.raises(RecoveryRefusalError) as caught:
        select_artifacts(SOURCE_RUN, values)
    assert caught.value.reason is reason


# --- select_plan ------------------------------------------------------------------------------


def plan_writer(saved: RunPlan, **changes: object) -> WriterIdentity:
    return WriterIdentity.model_validate(
        {
            "run_id": saved.run_id,
            "attempt": 1,
            "job": ServerJob.PLAN,
            "shard": 0,
            "producer": "stages.plan",
            "git_sha": SOURCE_COMMIT,
        }
        | changes
    )


def persist_plan(
    root: Path, rows: Sequence[RunPlan], writer: WriterIdentity, fmt: Format | None = None
) -> dict[str, bytes]:
    written = ledger.persist(
        root, list(rows), ledger=LedgerName.RUN_PLAN, covers=rows[0].date, identity=writer, fmt=fmt
    )
    return {path.name: path.read_bytes() for path in written}


def persist_readable_plan(root: Path, saved: RunPlan) -> tuple[str, bytes]:
    """The sound plan as a JSON-lines file, whose envelope and rows a case can edit as text."""
    ((name, data),) = persist_plan(root, [saved], plan_writer(saved), Format.JSON).items()
    return name, data


def change_envelope(data: bytes, **changes: str) -> bytes:
    head, _, rows = data.partition(b"\n")
    return json_lines.row_line(json.loads(head) | changes).encode() + rows


def change_first_row(data: bytes, **changes: object) -> bytes:
    head, _, rows = data.partition(b"\n")
    first, _, rest = rows.partition(b"\n")
    return head + b"\n" + json_lines.row_line(json.loads(first) | changes).encode() + rest


def with_run_id(saved: RunPlan, run_id: str) -> RunPlan:
    return RunPlan.model_validate(saved.model_dump() | {"run_id": run_id})


@dataclass(frozen=True)
class PlanCall:
    """What select_plan is asked: the plan artifact's files and the attempt they must match."""

    files: Mapping[str, bytes]
    execution: str = "1"
    attempt: int = 1
    commit: str = SOURCE_COMMIT

    def select(self, scratch: Path) -> tuple[RunPlan, str]:
        return select_plan(
            self.files,
            scratch,
            execution=self.execution,
            attempt=self.attempt,
            commit=self.commit,
        )


def a_plan_in_the_compact_tier(sound: SoundRun, root: Path) -> PlanCall:
    name, data = persist_readable_plan(root, sound.plan)
    return PlanCall({name: change_envelope(data, tier="compact", period="daily")})


def a_file_holding_no_plan(sound: SoundRun, root: Path) -> PlanCall:
    name, data = persist_readable_plan(root, sound.plan)
    return PlanCall({name: data.partition(b"\n")[0] + b"\n"})


def a_plan_row_dated_another_day(sound: SoundRun, root: Path) -> PlanCall:
    name, data = persist_readable_plan(root, sound.plan)
    return PlanCall({name: change_first_row(data, date="2026-08-22")})


def two_plans_in_one_file(sound: SoundRun, root: Path) -> PlanCall:
    rival = with_run_id(sound.plan, f"{sound.plan.date}-2")
    return PlanCall(persist_plan(root, [sound.plan, rival], plan_writer(sound.plan)))


def two_compatible_plan_files(sound: SoundRun, root: Path) -> PlanCall:
    again = persist_plan(root, [sound.plan], plan_writer(sound.plan, producer="stages.plan-again"))
    return PlanCall({**sound.plan_files, **again})


def a_plan_row_for_another_run(sound: SoundRun, root: Path) -> PlanCall:
    rival = with_run_id(sound.plan, f"{sound.plan.date}-2")
    return PlanCall(persist_plan(root, [rival], plan_writer(sound.plan)))


def a_plan_without_a_shard_count(sound: SoundRun, root: Path) -> PlanCall:
    unsharded = RunPlan.model_validate(sound.plan.model_dump() | {"shards": None})
    return PlanCall(persist_plan(root, [unsharded], plan_writer(sound.plan)))


PLAN_REFUSALS = [
    pytest.param(
        lambda sound, root: PlanCall({"notes.txt": b"not a ledger file"}),
        RefusalReason.NON_LEDGER_PLAN_FILE,
        id="not-a-ledger-file",
    ),
    pytest.param(
        lambda sound, root: PlanCall({"renamed.parquet": sound.plan_bytes}),
        RefusalReason.PLAN_FILENAME_NOT_FILE_IDENTITY,
        id="file-renamed",
    ),
    pytest.param(a_plan_in_the_compact_tier, RefusalReason.PLAN_NOT_RAW_OUTPUT, id="compact-tier"),
    pytest.param(
        lambda sound, root: PlanCall(sound.plan_files, commit="b" * 40),
        RefusalReason.PLAN_WRITER_MISMATCH,
        id="written-by-another-commit",
    ),
    pytest.param(
        lambda sound, root: PlanCall(
            persist_plan(root, [sound.plan], plan_writer(sound.plan, job=ServerJob.WORK))
        ),
        RefusalReason.PLAN_WRITER_MISMATCH,
        id="written-by-another-job",
    ),
    pytest.param(
        lambda sound, root: PlanCall(
            persist_plan(root, [sound.plan], plan_writer(sound.plan, shard=1))
        ),
        RefusalReason.PLAN_WRITER_MISMATCH,
        id="written-by-another-shard",
    ),
    pytest.param(two_plans_in_one_file, RefusalReason.PLAN_FILE_NOT_ONE_PLAN, id="two-plans"),
    pytest.param(a_file_holding_no_plan, RefusalReason.PLAN_FILE_NOT_ONE_PLAN, id="no-plan-row"),
    pytest.param(
        a_plan_row_for_another_run,
        RefusalReason.PLAN_RUN_DATE_OR_SHARDS_MISMATCH,
        id="row-for-another-run",
    ),
    pytest.param(
        a_plan_row_dated_another_day,
        RefusalReason.PLAN_RUN_DATE_OR_SHARDS_MISMATCH,
        id="row-dated-another-day",
    ),
    pytest.param(
        a_plan_without_a_shard_count,
        RefusalReason.PLAN_RUN_DATE_OR_SHARDS_MISMATCH,
        id="no-shard-count",
    ),
    pytest.param(
        lambda sound, root: PlanCall({}),
        RefusalReason.NO_ONE_SOURCE_ATTEMPT_PLAN,
        id="no-plan-file",
    ),
    pytest.param(
        lambda sound, root: PlanCall(sound.plan_files, attempt=2),
        RefusalReason.NO_ONE_SOURCE_ATTEMPT_PLAN,
        id="plan-of-another-attempt",
    ),
    pytest.param(
        lambda sound, root: PlanCall(sound.plan_files, execution="3"),
        RefusalReason.NO_ONE_SOURCE_ATTEMPT_PLAN,
        id="plan-of-another-execution",
    ),
    pytest.param(
        two_compatible_plan_files, RefusalReason.NO_ONE_SOURCE_ATTEMPT_PLAN, id="two-attempt-plans"
    ),
]


def test_select_plan_returns_the_source_attempts_single_plan(
    sound: SoundRun, tmp_path: Path
) -> None:
    chosen = PlanCall(sound.plan_files).select(an_empty_directory(tmp_path, "scratch"))
    assert chosen == (sound.plan, sound.plan_name)


@pytest.mark.parametrize(("build", "reason"), PLAN_REFUSALS)
def test_select_plan_refuses_one_broken_plan_artifact_for_its_own_reason(
    build: Callable[[SoundRun, Path], PlanCall],
    reason: RefusalReason,
    sound: SoundRun,
    tmp_path: Path,
) -> None:
    call = build(sound, tmp_path / "variant")
    with pytest.raises(RecoveryRefusalError) as caught:
        call.select(an_empty_directory(tmp_path, "scratch"))
    assert caught.value.reason is reason


# --- worker_files -----------------------------------------------------------------------------


def build_pipeline_inputs(**changes: object) -> bytes:
    inputs = PipelineInputs(
        model_sha256="a" * 64,
        quantisation="q4_k_m",
        runtime_build="b1234",
        chat_template_sha256="b" * 64,
        prompt_sha256="c" * 64,
        output_schema_sha256="d" * 64,
        truncation_cap_tokens=4000,
        sampling={"temperature": "0"},
        runtime_flags={"-fa": "set"},
        n_ctx=8192,
        n_batch=512,
        n_ubatch=512,
        n_threads=4,
        runner_class="ubuntu-latest",
        extractor_version="extractor-1",
        sanitizer_version="sanitizer-1",
    )
    return canonical_json(inputs.model_dump(mode="json") | changes).encode()


def build_article(item: PlannedItem) -> bytes:
    changes = {
        "item_id": item.item_id,
        "canonical_url": str(item.canonical_url),
        "url_key": item.url_key,
    }
    return Article.model_validate(article().model_dump() | changes).to_json().encode()


def build_summary(**changes: object) -> bytes:
    return Summary.model_validate(summary().model_dump() | changes).to_json().encode()


def build_eval_row(**changes: object) -> bytes:
    return EvalRow.model_validate(row().model_dump() | changes).to_json().encode()


def build_health_row(saved: RunPlan, **changes: object) -> bytes:
    item = saved.items[0]
    cells = health_row(day=saved.date, run=1, number=1, stage=ItemStage.PUBLISH).model_dump() | {
        "date": saved.date,
        "run_id": saved.run_id,
        "item_id": item.item_id,
        "url_key": item.url_key,
        "canonical_url": str(item.canonical_url),
        "vertical": item.vertical,
        "source_id": item.source_id,
        "machine_shard": 0,
        "machine_job": ServerJob.WORK,
    }
    return ItemHealthRow.model_validate(cells | changes).to_json().encode()


@dataclass(frozen=True)
class Worker:
    """Retained worker output: the files inside each shard's items artifact, by shard number."""

    plan: RunPlan
    shards: Mapping[int, Mapping[str, bytes]]
    failed: frozenset[int] = frozenset()

    @property
    def first(self) -> PlannedItem:
        return self.plan.items[0]

    @property
    def second(self) -> PlannedItem:
        return self.plan.items[1]

    def name(self, suffix: str, item: PlannedItem | None = None) -> str:
        return f"{(item or self.first).item_id}{suffix}"

    def with_files(self, shard: int, files: Mapping[str, bytes | None]) -> Worker:
        """Add, replace or (given None) remove files of one shard's artifact."""
        kept = {name: data for name, data in self.shards.get(shard, {}).items() if name not in files}
        kept |= {name: data for name, data in files.items() if data is not None}
        return replace(self, shards={**self.shards, shard: kept})

    def run(self) -> dict[str, bytes]:
        archives = {f"items-{shard}": zipped(dict(files)) for shard, files in self.shards.items()}
        return worker_files(self.plan, archives, failed_shards=self.failed)


def sound_worker(saved: RunPlan) -> Worker:
    first = saved.items[0]
    return Worker(
        saved,
        {
            0: {
                f"{first.item_id}.article.json": article().to_json().encode(),
                f"{first.item_id}.summary.json": summary().to_json().encode(),
                f"{first.item_id}.eval.json": build_eval_row(),
                f"{first.item_id}{HEALTH_SUFFIX}": build_health_row(saved),
                common.INPUTS_PAYLOAD: build_pipeline_inputs(),
            },
            1: {common.INPUTS_PAYLOAD: build_pipeline_inputs()},
        },
    )


WORKER_REFUSALS = [
    pytest.param(
        lambda w: replace(w, plan=w.plan.model_copy(update={"shards": None})),
        RefusalReason.PLAN_HAS_NO_SHARD_COUNT,
        id="plan-without-a-shard-count",
    ),
    pytest.param(
        lambda w: replace(w, shards={**w.shards, 5: {}}),
        RefusalReason.UNDISPATCHED_SHARD_ARTIFACT,
        id="artifact-of-an-undispatched-shard",
    ),
    pytest.param(
        lambda w: replace(w, shards={1: w.shards[1]}),
        RefusalReason.SUCCESSFUL_WORKER_ARTIFACT_MISSING,
        id="successful-worker-without-an-artifact",
    ),
    pytest.param(
        lambda w: w.with_files(0, {w.name(".article.json"): b"{}"}),
        RefusalReason.WORKER_PAYLOAD_INVALID,
        id="article-is-not-valid",
    ),
    pytest.param(
        lambda w: w.with_files(0, {common.INPUTS_PAYLOAD: b"{}"}),
        RefusalReason.WORKER_PAYLOAD_INVALID,
        id="inputs-are-not-valid",
    ),
    pytest.param(
        lambda w: w.with_files(
            0, {w.name(".summary.json"): build_summary(item_id=w.second.item_id)}
        ),
        RefusalReason.PAYLOAD_NAMES_ANOTHER_ITEM,
        id="summary-names-another-item",
    ),
    pytest.param(
        lambda w: w.with_files(
            0, {w.name(".summary.json"): build_summary(url_key=w.second.url_key)}
        ),
        RefusalReason.PAYLOAD_ADDRESS_MISMATCH,
        id="summary-has-another-address",
    ),
    pytest.param(
        lambda w: w.with_files(0, {w.name(".eval.json"): build_eval_row(run_id="2026-08-21-9")}),
        RefusalReason.RECORD_FROM_ANOTHER_RUN,
        id="eval-row-from-another-run",
    ),
    pytest.param(
        lambda w: w.with_files(0, {w.name(".eval.json"): build_eval_row(date="2026-08-20")}),
        RefusalReason.RECORD_FROM_ANOTHER_RUN,
        id="eval-row-from-another-day",
    ),
    pytest.param(
        lambda w: w.with_files(
            0, {w.name(HEALTH_SUFFIX): build_health_row(w.plan, run_id="2026-08-21-9")}
        ),
        RefusalReason.RECORD_FROM_ANOTHER_RUN,
        id="health-row-from-another-run",
    ),
    pytest.param(
        lambda w: w.with_files(
            0, {w.name(HEALTH_SUFFIX): build_health_row(w.plan, machine_shard=1)}
        ),
        RefusalReason.RECORD_FROM_ANOTHER_SHARD,
        id="health-row-from-another-shard",
    ),
    pytest.param(
        lambda w: w.with_files(
            0, {w.name(HEALTH_SUFFIX): build_health_row(w.plan, machine_job=ServerJob.ASSEMBLE)}
        ),
        RefusalReason.RECORD_FROM_ANOTHER_SHARD,
        id="health-row-from-another-job",
    ),
    pytest.param(
        lambda w: w.with_files(0, {"foreign.summary.json": b"{}"}),
        RefusalReason.UNPLANNED_WORKER_FILE,
        id="file-not-planned",
    ),
    pytest.param(
        lambda w: w.with_files(0, {w.name(".article.json", w.second): build_article(w.second)}),
        RefusalReason.UNPLANNED_WORKER_FILE,
        id="item-of-another-shard",
    ),
    pytest.param(
        lambda w: w.with_files(1, {common.INPUTS_PAYLOAD: build_pipeline_inputs(n_ctx=4096)}),
        RefusalReason.SHARED_BYTES_DISAGREE,
        id="shards-disagree-on-the-inputs",
    ),
    pytest.param(
        lambda w: w.with_files(0, {w.name(".article.json"): None}),
        RefusalReason.SOURCE_ARTICLE_MISSING,
        id="summary-without-its-article",
    ),
]


def test_worker_files_return_the_sound_output_of_every_shard(sound: SoundRun) -> None:
    worker = sound_worker(sound.plan)
    assert worker.run() == worker.shards[0]


def test_worker_files_accept_a_failed_shard_that_kept_no_artifact(sound: SoundRun) -> None:
    worker = sound_worker(sound.plan)
    failed = replace(worker, shards={0: worker.shards[0]}, failed=SHARD_ONE_FAILED)
    assert failed.run() == worker.shards[0]


def test_worker_files_accept_a_shard_planned_nothing_that_kept_no_artifact(sound: SoundRun) -> None:
    worker = sound_worker(sound.plan)
    three_shards = replace(worker, plan=sound.plan.model_copy(update={"shards": 3}))
    assert three_shards.run() == worker.shards[0]


@pytest.mark.parametrize(("change", "reason"), WORKER_REFUSALS)
def test_worker_files_refuse_one_broken_output_for_its_own_reason(
    change: Callable[[Worker], Worker], reason: RefusalReason, sound: SoundRun
) -> None:
    broken = change(sound_worker(sound.plan))
    with pytest.raises(RecoveryRefusalError) as caught:
        broken.run()
    assert caught.value.reason is reason


# --- restore ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class RestoreCall:
    """What restore is asked: the downloaded archives and the source attempt they must match."""

    archives: Mapping[str, bytes]
    execution: str = "1"
    commit: str = SOURCE_COMMIT
    failed: frozenset[int] = SHARD_ONE_FAILED

    def restore(self, repo: Path, scratch: Path) -> RestoredInputs:
        return restore(
            repo,
            scratch,
            self.archives,
            execution=self.execution,
            attempt=1,
            commit=self.commit,
            failed_shards=self.failed,
        )


def a_worker_archive_holding(sound: SoundRun, files: Mapping[str, bytes]) -> RestoreCall:
    return RestoreCall({**sound.archives, "items-0": zipped(dict(files))})


RESTORE_REFUSALS = [
    pytest.param(
        lambda sound: RestoreCall({"items-0": sound.archives["items-0"]}),
        RefusalReason.NO_PLAN_ARTIFACT,
        id="no-plan-artifact",
    ),
    pytest.param(
        lambda sound: RestoreCall({"plan": sound.archives["plan"]}),
        RefusalReason.SUCCESSFUL_WORKER_ARTIFACT_MISSING,
        id="successful-worker-without-an-artifact",
    ),
    pytest.param(
        lambda sound: a_worker_archive_holding(
            sound, {f"{sound.plan.items[0].item_id}.article.json": b"{}"}
        ),
        RefusalReason.WORKER_PAYLOAD_INVALID,
        id="article-is-not-valid",
    ),
    pytest.param(
        lambda sound: RestoreCall(sound.archives, execution="3"),
        RefusalReason.NO_ONE_SOURCE_ATTEMPT_PLAN,
        id="another-execution",
    ),
    pytest.param(
        lambda sound: RestoreCall(sound.archives, commit="b" * 40),
        RefusalReason.PLAN_WRITER_MISMATCH,
        id="another-commit",
    ),
    pytest.param(
        lambda sound: a_worker_archive_holding(sound, {"foreign.summary.json": b"{}"}),
        RefusalReason.UNPLANNED_WORKER_FILE,
        id="file-not-planned",
    ),
    pytest.param(
        lambda sound: RestoreCall({"plan": sound.archives["plan"]}, failed=frozenset({0, 1})),
        RefusalReason.NO_WORKER_OUTPUT,
        id="every-worker-failed",
    ),
]


def leave_old_work_in_the_item_directory(repo: Path, sound: SoundRun) -> dict[Path, bytes]:
    leftover = item_directory(repo, sound.plan) / "leftover.txt"
    leftover.parent.mkdir(parents=True)
    leftover.write_bytes(b"old unfinished work")
    return {leftover: b"old unfinished work"}


def stage_an_incoming_item_file(repo: Path, sound: SoundRun) -> dict[Path, bytes]:
    name = f"{sound.plan.items[0].item_id}.article.json"
    target = item_directory(repo, sound.plan) / name
    target.parent.mkdir(parents=True)
    # The staged bytes equal the incoming bytes: only the index entry makes the file foreign.
    target.write_bytes(sound.item_files[name])
    git(repo, "add", target.relative_to(repo).as_posix())
    return {target: sound.item_files[name]}


def keep_a_different_local_item_file(repo: Path, sound: SoundRun) -> dict[Path, bytes]:
    target = item_directory(repo, sound.plan) / f"{sound.plan.items[0].item_id}.article.json"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"foreign")
    return {target: b"foreign"}


CHECKOUT_REFUSALS = [
    pytest.param(
        leave_old_work_in_the_item_directory,
        RefusalReason.FOREIGN_ITEM_DIRECTORY_FILES,
        id="old-work-in-the-item-directory",
    ),
    pytest.param(
        stage_an_incoming_item_file, RefusalReason.FOREIGN_STAGED_INPUT, id="staged-item-file"
    ),
    pytest.param(
        keep_a_different_local_item_file,
        RefusalReason.FOREIGN_LOCAL_BYTES,
        id="different-local-item-file",
    ),
]


def test_restore_copies_the_sound_inputs_and_returns_the_source_plan(
    sound: SoundRun, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = a_checkout(tmp_path, monkeypatch)
    restored = RestoreCall(sound.archives).restore(repo, an_empty_directory(tmp_path, "scratch"))
    assert restored.plan == sound.plan
    assert restored.plan_sha256 == hashlib.sha256(sound.plan_bytes).hexdigest()
    assert (repo / restored.plan_path).read_bytes() == sound.plan_bytes
    for name, data in sound.item_files.items():
        assert (item_directory(repo, sound.plan) / name).read_bytes() == data


@pytest.mark.parametrize(("build", "reason"), RESTORE_REFUSALS)
def test_restore_refuses_one_broken_input_before_copying_anything(
    build: Callable[[SoundRun], RestoreCall], reason: RefusalReason, sound: SoundRun, tmp_path: Path
) -> None:
    repo = an_empty_directory(tmp_path, "repo")
    with pytest.raises(RecoveryRefusalError) as caught:
        build(sound).restore(repo, an_empty_directory(tmp_path, "scratch"))
    assert caught.value.reason is reason
    assert not (repo / "state").exists()
    assert not (repo / "backend").exists()


@pytest.mark.parametrize(("prepare", "reason"), CHECKOUT_REFUSALS)
def test_restore_refuses_a_checkout_it_would_overwrite_and_leaves_it_as_found(
    prepare: Callable[[Path, SoundRun], dict[Path, bytes]],
    reason: RefusalReason,
    sound: SoundRun,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = a_checkout(tmp_path, monkeypatch)
    found = prepare(repo, sound)
    with pytest.raises(RecoveryRefusalError) as caught:
        RestoreCall(sound.archives).restore(repo, an_empty_directory(tmp_path, "scratch"))
    assert caught.value.reason is reason
    assert not (repo / "state").exists()
    for path, data in found.items():
        assert path.read_bytes() == data


# --- plan_import ------------------------------------------------------------------------------


@dataclass(frozen=True)
class ImportCall:
    """What plan_import is asked: the restored plan and the source attempt it must still match."""

    restored: RestoredInputs
    execution: str = "1"
    attempt: int = 1
    commit: str = SOURCE_COMMIT

    def authorize(self, repo: Path) -> Write:
        return plan_import(
            repo,
            self.restored,
            execution=self.execution,
            attempt=self.attempt,
            commit=self.commit,
            baseline=SOURCE_COMMIT,
        )


def place_plan(repo: Path, saved: RunPlan, name: str, data: bytes) -> RestoredInputs:
    """A restored plan as restore reports it: the file in the checkout, hashed as received."""
    (repo / name).write_bytes(data)
    return RestoredInputs(saved, name, hashlib.sha256(data).hexdigest())


def a_plan_file_edited_after_restoring(sound: SoundRun, repo: Path, root: Path) -> ImportCall:
    restored = place_plan(repo, sound.plan, sound.plan_name, sound.plan_bytes)
    (repo / sound.plan_name).write_bytes(sound.plan_bytes + b"\n")
    return ImportCall(restored)


def a_restored_plan_asked_about(
    sound: SoundRun,
    repo: Path,
    *,
    execution: str = "1",
    attempt: int = 1,
    commit: str = SOURCE_COMMIT,
) -> ImportCall:
    restored = place_plan(repo, sound.plan, sound.plan_name, sound.plan_bytes)
    return ImportCall(restored, execution=execution, attempt=attempt, commit=commit)


def a_restored_plan_written_by(
    sound: SoundRun, repo: Path, root: Path, **writer: object
) -> ImportCall:
    ((name, data),) = persist_plan(root, [sound.plan], plan_writer(sound.plan, **writer)).items()
    return ImportCall(place_plan(repo, sound.plan, name, data))


def a_restored_plan_that_differs_from_its_file(
    sound: SoundRun, repo: Path, root: Path
) -> ImportCall:
    other = sound.plan.model_copy(update={"shards": 3})
    return ImportCall(place_plan(repo, other, sound.plan_name, sound.plan_bytes))


IDENTITY_CHANGED = RefusalReason.RESTORED_PLAN_IDENTITY_CHANGED

IMPORT_REFUSALS = [
    pytest.param(
        a_plan_file_edited_after_restoring,
        RefusalReason.RESTORED_PLAN_BYTES_CHANGED,
        id="file-edited-after-restoring",
    ),
    pytest.param(
        lambda sound, repo, root: a_restored_plan_asked_about(sound, repo, execution="2"),
        IDENTITY_CHANGED,
        id="another-execution",
    ),
    pytest.param(
        lambda sound, repo, root: a_restored_plan_asked_about(sound, repo, attempt=2),
        IDENTITY_CHANGED,
        id="another-attempt",
    ),
    pytest.param(
        lambda sound, repo, root: a_restored_plan_asked_about(sound, repo, commit="b" * 40),
        IDENTITY_CHANGED,
        id="another-commit",
    ),
    pytest.param(
        lambda sound, repo, root: a_restored_plan_written_by(sound, repo, root, job=ServerJob.WORK),
        IDENTITY_CHANGED,
        id="written-by-another-job",
    ),
    pytest.param(
        lambda sound, repo, root: a_restored_plan_written_by(sound, repo, root, shard=1),
        IDENTITY_CHANGED,
        id="written-by-another-shard",
    ),
    pytest.param(
        a_restored_plan_that_differs_from_its_file, IDENTITY_CHANGED, id="rows-differ-from-the-plan"
    ),
]


def test_plan_import_authorizes_exactly_the_restored_plan(
    sound: SoundRun, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = a_checkout(tmp_path, monkeypatch)
    head = git(repo, "rev-parse", "HEAD").strip()
    restored = RestoreCall(sound.archives).restore(repo, an_empty_directory(tmp_path, "scratch"))
    authorized = plan_import(
        repo, restored, execution="1", attempt=1, commit=SOURCE_COMMIT, baseline=head
    )
    assert authorized == Write(restored.plan_sha256, None, immutable=True, baseline_tip=head)


@pytest.mark.parametrize(("build", "reason"), IMPORT_REFUSALS)
def test_plan_import_refuses_a_restored_plan_that_no_longer_matches_for_its_own_reason(
    build: Callable[[SoundRun, Path, Path], ImportCall],
    reason: RefusalReason,
    sound: SoundRun,
    tmp_path: Path,
) -> None:
    repo = an_empty_directory(tmp_path, "repo")
    call = build(sound, repo, tmp_path / "variant")
    with pytest.raises(RecoveryRefusalError) as caught:
        call.authorize(repo)
    assert caught.value.reason is reason


# --- pages, fetch_source and download -----------------------------------------------------------


def record(payload: object) -> bytes:
    return json.dumps(payload).encode()


def listing(key: str, total: int, *batches: Sequence[object]) -> PlatformCall:
    """The platform's paged inventory: page N answers with the Nth batch, then with none."""

    def call(repository: str, path: str) -> bytes:
        assert repository == REPOSITORY
        number = int(path.rpartition("page=")[2])
        rows = list(batches[number - 1]) if number <= len(batches) else []
        return record({"total_count": total, key: rows})

    return call


def recorded_platform(answers: Mapping[str, bytes]) -> PlatformCall:
    """The platform as a recording: each API path, query aside, answers the bytes it once did."""

    def call(repository: str, path: str) -> bytes:
        assert repository == REPOSITORY
        return answers[path.partition("?")[0]]

    return call


def sound_answers(sound: SoundRun) -> dict[str, bytes]:
    plan_zip, items_zip = sound.archives["plan"], sound.archives["items-0"]
    jobs = [
        {"name": "plan", "conclusion": "success"},
        {"name": "work (0)", "conclusion": "success"},
        {"name": "work (1)", "conclusion": "failure"},
    ]
    artifacts = [
        platform_artifact("plan", id=4, digest=f"sha256:{hashlib.sha256(plan_zip).hexdigest()}"),
        platform_artifact(
            "items-0", id=5, digest=f"sha256:{hashlib.sha256(items_zip).hexdigest()}"
        ),
    ]
    return {
        "actions/runs/1": record(SOURCE_RUN.model_dump(mode="json")),
        "actions/runs/1/attempts/2/jobs": record({"total_count": len(jobs), "jobs": jobs}),
        "actions/runs/1/artifacts": record({"total_count": 2, "artifacts": artifacts}),
        "actions/artifacts/4/zip": plan_zip,
        "actions/artifacts/5/zip": items_zip,
    }


def a_run_with_another_id(sound: SoundRun) -> dict[str, bytes]:
    other = SOURCE_RUN.model_dump(mode="json") | {"id": 2}
    return {**sound_answers(sound), "actions/runs/1": record(other)}


def a_run_whose_plan_job_failed(sound: SoundRun) -> dict[str, bytes]:
    jobs = [{"name": "plan", "conclusion": "failure"}, {"name": "work (0)", "conclusion": "success"}]
    return {
        **sound_answers(sound),
        "actions/runs/1/attempts/2/jobs": record({"total_count": len(jobs), "jobs": jobs}),
    }


def a_download_that_differs_from_its_digest(sound: SoundRun) -> dict[str, bytes]:
    return {**sound_answers(sound), "actions/artifacts/4/zip": sound.archives["plan"] + b"x"}


PLATFORM_REFUSALS = [
    pytest.param(a_run_with_another_id, RefusalReason.ANOTHER_SOURCE_RUN, id="another-source-run"),
    pytest.param(
        a_run_whose_plan_job_failed, RefusalReason.NO_SUCCESSFUL_PLAN_JOB, id="plan-job-failed"
    ),
    pytest.param(
        a_download_that_differs_from_its_digest,
        RefusalReason.CHECKSUM_DIFFERS_FROM_DIGEST,
        id="download-differs-from-its-digest",
    ),
]


def test_pages_collect_every_row_across_pages() -> None:
    call = listing("jobs", 3, ["a", "b"], ["c"])
    assert pages(REPOSITORY, "actions/runs/1/jobs", "jobs", call) == ["a", "b", "c"]


def test_pages_refuse_an_inventory_that_is_not_a_list() -> None:
    def call(repository: str, path: str) -> bytes:
        return record({"total_count": 1, "jobs": "none"})

    with pytest.raises(RecoveryRefusalError) as caught:
        pages(REPOSITORY, "actions/runs/1/jobs", "jobs", call)
    assert caught.value.reason is RefusalReason.PLATFORM_LIST_MISSING
    assert caught.value.paths == ("jobs",)


def test_pages_refuse_pagination_that_ends_before_the_declared_count() -> None:
    call = listing("jobs", 3, ["a"], [])
    with pytest.raises(RecoveryRefusalError) as caught:
        pages(REPOSITORY, "actions/runs/1/jobs", "jobs", call)
    assert caught.value.reason is RefusalReason.PAGINATION_ENDED_EARLY


def test_fetch_source_returns_the_run_its_checksummed_archives_and_failed_shards(
    sound: SoundRun,
) -> None:
    fetched = fetch_source("1", REPOSITORY, recorded_platform(sound_answers(sound)))
    assert fetched == (SOURCE_RUN, dict(sound.archives), SHARD_ONE_FAILED)


@pytest.mark.parametrize(("answers", "reason"), PLATFORM_REFUSALS)
def test_fetch_source_refuses_one_broken_platform_answer_for_its_own_reason(
    answers: Callable[[SoundRun], dict[str, bytes]], reason: RefusalReason, sound: SoundRun
) -> None:
    with pytest.raises(RecoveryRefusalError) as caught:
        fetch_source("1", REPOSITORY, recorded_platform(answers(sound)))
    assert caught.value.reason is reason


@pytest.mark.parametrize(
    "execution",
    [
        pytest.param("", id="empty"),
        pytest.param("0", id="zero"),
        pytest.param("01", id="leading-zero"),
        pytest.param("-3", id="negative"),
        pytest.param("12a", id="trailing-letter"),
        pytest.param(" 1", id="leading-space"),
    ],
)
def test_download_refuses_a_run_id_that_is_not_positive_before_asking_the_platform(
    execution: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # With no `gh` on the path a regression fails here instead of reaching the network.
    monkeypatch.setenv("PATH", str(tmp_path))
    with pytest.raises(RecoveryRefusalError) as caught:
        download(execution)
    assert caught.value.reason is RefusalReason.RUN_ID_NOT_POSITIVE


def test_download_lets_a_positive_run_id_through_to_the_platform_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Past the id check the first thing it does is start `gh`, which is not on this path.
    monkeypatch.setenv("PATH", str(tmp_path))
    with pytest.raises(FileNotFoundError):
        download("1")


# --- the refusal itself -----------------------------------------------------------------------


def test_a_refusal_names_its_subject_and_keeps_a_name_from_an_artifact_on_one_line() -> None:
    reason = RefusalReason.UNSAFE_OR_DUPLICATE_FILE
    hostile = "bad\nname\x1b[0m"

    named = RecoveryRefusalError(reason, (hostile,))
    bare = RecoveryRefusalError(RefusalReason.NOT_A_ZIP_ARCHIVE)

    assert named.reason is reason
    assert named.paths == (hostile,)
    assert str(named).startswith(reason.value)
    assert ascii(hostile) in str(named)
    assert str(named).isprintable()
    assert str(bare) == RefusalReason.NOT_A_ZIP_ARCHIVE.value
