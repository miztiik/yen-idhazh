"""Do the ledger files the site publishes carry the columns their row contracts declare?"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from idhazh.contracts.base import Contract
from idhazh.contracts.file_envelope import FileEnvelope
from idhazh.contracts.ledger_name import LedgerName
from idhazh.ledger import keys, paths
from idhazh.ledger.persist import file_columns

_STATE_DIR: Final = "state"
_PARQUET_SUFFIX: Final = ".parquet"
_NO_COLUMN: Final = "<not declared>"
_REPACK_FIX: Final = (
    "give the contract a new version, CLAUDE.md section 11, or re-pack the file"
)
_ZERO_FILE_FIX: Final = "is --site-tree the built site?"


@dataclass(frozen=True, slots=True)
class _History:
    files: int = 0
    missing: frozenset[str] = field(default_factory=frozenset)
    extra: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True, slots=True)
class _Report:
    ledger: LedgerName
    files: int
    current: int
    history: dict[str, _History]


@dataclass(frozen=True, slots=True)
class _Fault:
    kind: str
    ledger: LedgerName
    path: Path | None
    file_stamp: str | None
    contract_stamp: str | None
    column: str
    file_type: str
    contract_type: str
    fix: str


def _relative(site_tree: Path, path: Path | None) -> str:
    if path is None:
        return "<no file>"
    try:
        return path.relative_to(site_tree).as_posix()
    except ValueError:
        return path.as_posix()


def _fault_line(site_tree: Path, fault: _Fault) -> str:
    return (
        f"published-columns FAIL {fault.kind} ledger={fault.ledger.value} "
        f"file={_relative(site_tree, fault.path)} file_schema={fault.file_stamp or _NO_COLUMN} "
        f"contract_schema={fault.contract_stamp or _NO_COLUMN} column={fault.column} "
        f"file_type={fault.file_type} contract_type={fault.contract_type}; fix: {fault.fix}"
    )


def _zero_file_line(site_tree: Path) -> str:
    return (
        "published-columns FAIL F0 "
        f"tree={site_tree.as_posix()} file_schema={_NO_COLUMN} "
        f"contract_schema={_NO_COLUMN} column={_NO_COLUMN} "
        f"file_type={_NO_COLUMN} contract_type={_NO_COLUMN}; fix: {_ZERO_FILE_FIX}"
    )


def _history_line(stamp: str, history: _History) -> str:
    missing = ", ".join(sorted(history.missing)) or "none"
    extra = ", ".join(sorted(history.extra)) or "none"
    return f"{stamp}: {history.files} file(s), missing [{missing}], extra [{extra}]"


def _report_line(report: _Report) -> str:
    history = "; ".join(
        _history_line(stamp, held) for stamp, held in sorted(report.history.items())
    )
    if not history:
        history = "none"
    return (
        f"published-columns {report.ledger.value}: checked {report.files} file(s), "
        f"current {report.current}, history {history}"
    )


def _parquet_files(site_tree: Path, ledger: LedgerName) -> list[Path]:
    folders = paths.door_folders(ledger)
    state = site_tree / _STATE_DIR
    files: list[Path] = []
    for tier in ("compact", "raw"):
        root = state.joinpath(tier, *folders)
        if root.exists():
            files.extend(path for path in root.rglob(f"*{_PARQUET_SUFFIX}") if path.is_file())
    return sorted(files)


def _add_history(
    history: dict[str, _History], stamp: str, *, missing: Iterable[str], extra: Iterable[str]
) -> None:
    held = history.get(stamp, _History())
    history[stamp] = _History(
        files=held.files + 1,
        missing=held.missing | frozenset(missing),
        extra=held.extra | frozenset(extra),
    )


def _contract_schema(model: type[Contract]) -> Any:
    from idhazh.ledger import parquet

    return parquet.schema_of(file_columns(model))


def _check_file(
    *,
    site_tree: Path,
    path: Path,
    ledger: LedgerName,
    contract_stamp: str,
    expected: Any,
) -> tuple[FileEnvelope, Any, list[_Fault]]:
    from idhazh.ledger import parquet

    metadata, actual = parquet.read_footer_schema(path)
    envelope = FileEnvelope.from_metadata(metadata)
    faults: list[_Fault] = []
    file_stamp = envelope.row_schema_version
    if file_stamp > contract_stamp:
        faults.append(
            _Fault(
                kind="F3",
                ledger=ledger,
                path=path,
                file_stamp=file_stamp,
                contract_stamp=contract_stamp,
                column=_NO_COLUMN,
                file_type=_NO_COLUMN,
                contract_type=_NO_COLUMN,
                fix="re-pack the file with this build or run a build at least as new",
            )
        )
        return envelope, actual, faults

    expected_names = set(expected.names)
    actual_names = set(actual.names)
    missing = sorted(expected_names - actual_names)
    extra = sorted(actual_names - expected_names)
    if file_stamp == contract_stamp:
        for name in missing:
            faults.append(
                _Fault(
                    kind="F1",
                    ledger=ledger,
                    path=path,
                    file_stamp=file_stamp,
                    contract_stamp=contract_stamp,
                    column=name,
                    file_type=_NO_COLUMN,
                    contract_type=str(expected.field(name).type),
                    fix=_REPACK_FIX,
                )
            )
        for name in extra:
            faults.append(
                _Fault(
                    kind="F1",
                    ledger=ledger,
                    path=path,
                    file_stamp=file_stamp,
                    contract_stamp=contract_stamp,
                    column=name,
                    file_type=str(actual.field(name).type),
                    contract_type=_NO_COLUMN,
                    fix=_REPACK_FIX,
                )
            )
    for name in sorted(expected_names & actual_names):
        if not expected.field(name).type.equals(actual.field(name).type):
            faults.append(
                _Fault(
                    kind="F2",
                    ledger=ledger,
                    path=path,
                    file_stamp=file_stamp,
                    contract_stamp=contract_stamp,
                    column=name,
                    file_type=str(actual.field(name).type),
                    contract_type=str(expected.field(name).type),
                    fix=_REPACK_FIX,
                )
            )
    return envelope, actual, faults


def check(site_tree: Path, published: Sequence[LedgerName]) -> int:
    """Print the published-column check result and return a process exit code.

    Guardrail 12: this reads only the site tree handed to `--site-tree`. The site
    build copies each published ledger only to the widest span the console can
    ask for, so the check's cost grows with that capped browser window and not
    with the repository's accumulated history.
    """
    site_tree = site_tree.resolve()
    faults: list[_Fault] = []
    reports: list[_Report] = []
    contracted_ledgers = 0
    contracted_files = 0
    for ledger in published:
        try:
            model = keys.door_contract(ledger)
        except ValueError:
            faults.append(
                _Fault(
                    kind="F4",
                    ledger=ledger,
                    path=None,
                    file_stamp=None,
                    contract_stamp=None,
                    column=_NO_COLUMN,
                    file_type=_NO_COLUMN,
                    contract_type=_NO_COLUMN,
                    fix="add the ledger to the door table in idhazh/ledger/keys.py",
                )
            )
            continue
        contracted_ledgers += 1
        expected = _contract_schema(model)
        contract_stamp = model.schema_version()
        current = 0
        history: dict[str, _History] = {}
        files = _parquet_files(site_tree, ledger)
        contracted_files += len(files)
        for path in files:
            envelope, actual, file_faults = _check_file(
                site_tree=site_tree,
                path=path,
                ledger=ledger,
                contract_stamp=contract_stamp,
                expected=expected,
            )
            faults.extend(file_faults)
            missing = sorted(set(expected.names) - set(actual.names))
            extra = sorted(set(actual.names) - set(expected.names))
            if envelope.row_schema_version == contract_stamp and not missing and not extra:
                current += 1
            elif envelope.row_schema_version < contract_stamp:
                _add_history(
                    history, envelope.row_schema_version, missing=missing, extra=extra
                )
        reports.append(_Report(ledger=ledger, files=len(files), current=current, history=history))

    zero_file_fault = contracted_ledgers > 0 and contracted_files == 0
    if faults or zero_file_fault:
        if zero_file_fault:
            print(_zero_file_line(site_tree))
        for fault in faults:
            print(_fault_line(site_tree, fault))
        return 1
    for report in reports:
        print(_report_line(report))
    return 0
