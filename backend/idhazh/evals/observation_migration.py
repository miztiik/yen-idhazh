"""Migrate every legacy evaluation ID to the exact lookup without rewriting evaluation rows.

This explicit operator pass reads all legacy index CSVs and all raw and compact
evaluation files. Its cost grows with those files and rows: a bounded date
cannot preserve an identity whose legacy key did not carry a date. No live
writer calls this pass. The operator must exclude concurrent legacy writers
and compaction during cutover; source checks refuse changes observed here.
"""

from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

from idhazh import day_shards, ledger
from idhazh.contracts.base import canonical_json, derive_text_digest
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.file_envelope import Format, Period, Tier
from idhazh.contracts.ledger_index import CompactIndex, RawDayIndex, Watermark
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.observation_index import ObservationIndexRow
from idhazh.contracts.observation_lookup import (
    ObservationLookupEntry,
    ObservationLookupRoot,
    ObservationLookupSettings,
)
from idhazh.evals import writer
from idhazh.evals.observation_batches import lookup_root, row_digest
from idhazh.evals.observation_lookup import ROOT_NAME, ObservationLookup
from idhazh.ledger.paths import INDEX_DIRNAME


@dataclass(frozen=True)
class MigrationResult:
    """Actual counts and state-relative paths from one explicit migration, not a saved receipt."""

    lookup: str
    generation: str
    legacy_rows_read: int
    legacy_ids: int
    evaluation_rows_read: int
    current_ids: int
    required_ids: int
    existing_verified: bool
    written_paths: tuple[str, ...]
    removed_paths: tuple[str, ...]


def _guard(path: Path, state: Path) -> None:
    if not path.is_relative_to(state):
        raise ValueError("migration input and output must stay inside the named state directory")
    for part in (path, *path.parents):
        if part.is_symlink() or part.is_junction():
            raise ValueError("migration refuses symbolic links and directory junctions")
        if part == state:
            break
    if not path.resolve().is_relative_to(state.resolve()):
        raise ValueError("migration input and output must stay inside the named state directory")


def _files(root: Path, state: Path, *, exclude: Path | None = None) -> list[Path]:
    _guard(root, state)
    if not root.exists():
        return []
    if not root.is_dir():
        raise ValueError(f"expected a directory: {root.relative_to(state).as_posix()}")
    found: list[Path] = []
    for path in sorted(root.iterdir()):
        _guard(path, state)
        if path == exclude:
            continue
        if path.is_dir():
            found.extend(_files(path, state))
        elif path.is_file():
            found.append(path)
        else:
            raise ValueError(f"not a regular input file: {path.relative_to(state).as_posix()}")
    return found


def _source_files(state: Path) -> tuple[list[Path], list[Path]]:
    root = lookup_root(state)
    legacy = _files(root.parent, state, exclude=root)
    evaluations = _files(ledger.raw_root(state, LedgerName.SUMMARY_QUALITY_EVALS), state)
    compact = ledger.compact_index_path(state, LedgerName.SUMMARY_QUALITY_EVALS, Period.DAILY)
    evaluations.extend(_files(compact.parent.parent, state))
    return legacy, evaluations


def _fingerprint(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _snapshot(state: Path) -> dict[Path, str]:
    legacy, evaluations = _source_files(state)
    return {path: _fingerprint(path) for path in (*legacy, *evaluations)}


def _legacy_ids(paths: list[Path], state: Path) -> tuple[set[str], int]:
    root = lookup_root(state).parent
    identities: set[str] = set()
    count = 0
    columns = ObservationIndexRow.csv_columns()
    for path in paths:
        relative = path.relative_to(root)
        parts = relative.parts
        try:
            if path.suffix != ".csv":
                raise ValueError("expected CSV")
            if len(parts) == 3 and parts[-1] == day_shards.SETTLED_NAME:
                stamp = "-".join((*parts[:2], "01"))
            elif len(parts) == 4:
                if not (
                    path.name in (day_shards.SETTLED_NAME, ledger.BEFORE_PARTITION_NAME)
                    or ledger.is_repair(path.name)
                ):
                    ledger.parse_segment_name(path)
                stamp = "-".join(parts[:3])
            else:
                raise ValueError("expected a daily segment or a settled month")
            if date.fromisoformat(stamp).isoformat() != stamp:
                raise ValueError("expected zero-padded UTC date folders")
        except ValueError as refusal:
            raise ValueError(f"unknown legacy index path: {relative.as_posix()}") from refusal
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, strict=True)
            if reader.fieldnames is None or tuple(reader.fieldnames) != columns:
                raise ValueError(f"invalid legacy index header: {relative.as_posix()}")
            for record in reader:
                if set(record) != set(columns) or any(value is None for value in record.values()):
                    raise ValueError(f"invalid legacy index row: {relative.as_posix()}")
                if record["version"] != ObservationIndexRow.schema_version():
                    raise ValueError(f"unknown legacy index version: {relative.as_posix()}")
                identities.add(ObservationIndexRow.from_csv_row(record).observation_digest)
                count += 1
    return identities, count


def _metadata(path: Path, state: Path) -> bool:
    which = LedgerName.SUMMARY_QUALITY_EVALS
    raw = ledger.raw_root(state, which)
    if path.parent == raw / INDEX_DIRNAME:
        listing = RawDayIndex.read(path)
        if listing.ledger != which or path != ledger.raw_index_path(state, which, listing.date):
            raise ValueError("a raw evaluation listing names another ledger or day")
        return True
    for period in Period:
        if path == ledger.compact_index_path(state, which, period):
            index = CompactIndex.read(path)
            if (index.ledger, index.period) != (which, period):
                raise ValueError("a compact evaluation index names another ledger or period")
            for entry in index.entries:
                if not any(
                    ledger.compact_path(state, which, period, entry.covers, fmt=fmt).is_file()
                    for fmt in Format
                ):
                    raise ValueError(f"a compact evaluation file is missing for {entry.covers}")
            return True
        if path == ledger.watermark_path(state, which, period):
            watermark = Watermark.read(path)
            if (watermark.ledger, watermark.period) != (which, period):
                raise ValueError("an evaluation watermark names another ledger or period")
            return True
    return False


def _evaluation_ids(paths: list[Path], state: Path) -> tuple[set[str], int]:
    which = LedgerName.SUMMARY_QUALITY_EVALS
    identities: set[str] = set()
    count = 0
    for path in paths:
        if _metadata(path, state):
            continue
        envelope = ledger.read_envelope(path)
        fmt = Format(path.suffix.removeprefix("."))
        if envelope.ledger != which:
            raise ValueError("an evaluation source file names another ledger")
        if envelope.tier is Tier.RAW:
            expected = ledger.raw_path(state, which, envelope.covers, envelope.file_id, fmt=fmt)
        elif envelope.period is not None:
            expected = ledger.compact_path(state, which, envelope.period, envelope.covers, fmt=fmt)
        else:
            raise ValueError("a compact evaluation file has no period")
        if expected != path:
            raise ValueError(f"misplaced evaluation file: {path.relative_to(state).as_posix()}")
        rows = ledger.load([path], model=EvalRow)
        identities.update(row_digest(row) for row in rows)
        count += len(rows)
    return identities, count


def _semantics(state: Path) -> str:
    return derive_text_digest(canonical_json(list(writer.records(state))))


def _unchanged(state: Path, before: dict[Path, str], semantics: str) -> None:
    if _snapshot(state) != before or _semantics(state) != semantics:
        raise ValueError("evaluation history changed during migration; no more CSVs may be removed")


def _verify(lookup: ObservationLookup, identities: set[str]) -> str:
    manifest = lookup.manifest()
    if manifest.key_fields != ledger.OBSERVATION_KEY:
        raise ValueError("the existing lookup names another observation key; it was not replaced")
    missing = identities - lookup.recorded(identities)
    if missing:
        raise ValueError(f"the lookup is missing {len(missing)} required IDs; it was not reset")
    return manifest.generation


def migrate(
    state_dir: Path,
    settings: ObservationLookupSettings,
    *,
    existing: Literal["refuse", "verify"] = "refuse",
) -> MigrationResult:
    """Build once, or explicitly verify a published root and finish its interrupted CSV cleanup.

    Existing roots are never rebuilt or extended by migration. A missing or
    invalid existing manifest refuses verification. The complete lookup is
    published before the first legacy CSV is removed, so a retry needs only
    that root, not another persisted receipt. Evaluation files are read only.
    """
    state = state_dir.absolute()
    if ".." in state.parts or state.resolve() != state:
        raise ValueError("use a direct state directory, without parent traversal or linked parents")
    _guard(state, state)
    if not state.is_dir():
        raise ValueError("the named state directory does not exist")
    if existing not in ("refuse", "verify"):
        raise ValueError("existing must be refuse or verify")
    root = lookup_root(state)
    _guard(root, state)
    was_present = root.exists()
    if was_present and existing == "refuse":
        raise FileExistsError(
            "lookup already exists; use existing=verify to resume verified cleanup"
        )
    if was_present:
        _files(root, state)
        ObservationLookupRoot.read(root / ROOT_NAME)
    legacy, evaluation_files = _source_files(state)
    before = {path: _fingerprint(path) for path in (*legacy, *evaluation_files)}
    legacy_ids, legacy_count = _legacy_ids(legacy, state)
    current_ids, evaluation_count = _evaluation_ids(evaluation_files, state)
    identities = legacy_ids | current_ids
    if not identities and not was_present:
        raise ValueError("no legacy IDs or evaluation rows were found; refusing an empty migration")
    semantics = _semantics(state)
    written: tuple[str, ...] = ()
    if not was_present:
        with TemporaryDirectory(prefix=".observation-migration-", dir=state) as temporary:
            staged = Path(temporary) / root.name
            with ObservationLookup(staged) as lookup:
                lookup.initialize(ledger.OBSERVATION_KEY, settings)
                lookup.put(
                    [
                        ObservationLookupEntry(namespace="observation", identity=identity)
                        for identity in sorted(identities)
                    ],
                    generation=derive_text_digest(
                        canonical_json([ledger.OBSERVATION_KEY, sorted(identities)])
                    ),
                )
                _verify(lookup, identities)
                written = tuple(
                    sorted(
                        (root / path.relative_to(staged)).relative_to(state).as_posix()
                        for path in lookup.changed
                        if path.is_file()
                    )
                )
            _unchanged(state, before, semantics)
            _guard(root, state)
            if root.exists():
                raise FileExistsError("a lookup appeared during migration; it was not replaced")
            root.parent.mkdir(parents=True, exist_ok=True)
            staged.rename(root)
    with ObservationLookup(root) as lookup:
        generation = _verify(lookup, identities)
        _unchanged(state, before, semantics)
        removed: list[str] = []
        for path in legacy:
            _guard(path, state)
            if _fingerprint(path) != before[path]:
                raise ValueError("a legacy CSV changed before removal; retry with existing=verify")
            path.unlink()
            removed.append(path.relative_to(state).as_posix())
        written = tuple(sorted(set(written) | {
            path.relative_to(state).as_posix() for path in lookup.changed
        }))
    if _snapshot(state) != {path: digest for path, digest in before.items() if path not in legacy}:
        raise ValueError("evaluation sources changed during cleanup; retain the published lookup")
    if _semantics(state) != semantics:
        raise ValueError("evaluation row semantics changed; retain the published lookup")
    return MigrationResult(
        lookup=root.relative_to(state).as_posix(),
        generation=generation,
        legacy_rows_read=legacy_count,
        legacy_ids=len(legacy_ids),
        evaluation_rows_read=evaluation_count,
        current_ids=len(current_ids),
        required_ids=len(identities),
        existing_verified=was_present,
        written_paths=written,
        removed_paths=tuple(removed),
    )