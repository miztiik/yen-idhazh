"""Which exact native host files may this independently identified publisher consume?"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import replace
from datetime import date as utc_date
from pathlib import Path

from idhazh import ledger
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.host_output import (
    HOST_OUTPUT_VERSION,
    HOST_PRODUCER,
    HostPublicationReceipt,
    HostWriterIdentity,
)
from idhazh.contracts.ledger_name import LedgerName
from idhazh.ledger import paths
from idhazh.telemetry.host_evidence_inputs import CONFIG_BYTES, NativeSettings, read_bytes
from idhazh.telemetry.host_output_verify import (
    VerificationLimits,
    load_verification_document,
    read_host_output,
)

RECEIPT_ENV = "IDHAZH_HOST_TELEMETRY_RECEIPT"
MODE_ENV = "IDHAZH_HOST_TELEMETRY_MODE"


def verify_host_publication(
    receipt: HostPublicationReceipt,
    *,
    repo: Path,
    identity: WriterIdentity,
    date: str,
    limits: VerificationLimits,
    registry: paths.DoorRegistry | None = None,
    host_enabled: bool = True,
) -> dict[str, str]:
    """Read native bytes in their registry addresses; never grant permission or write files.

    The lifecycle owner supplies completed, reconciled receipt evidence after
    closing/draining the session. Identity, UTC day, registry and limits come
    from the invocation, not from that receipt. Shared publication still checks
    its own permissions and hashes these same paths again before staging.
    """
    if utc_date.fromisoformat(date).isoformat() != date:
        raise ValueError("native publication requires an independently expected UTC date")
    expected = HostWriterIdentity.model_validate(
        identity.model_dump() | {"producer": HOST_PRODUCER}
    )
    receipt = HostPublicationReceipt.model_validate(receipt.model_dump(mode="json"))
    if receipt.identity != expected:
        raise ValueError("native receipt belongs to another executed invocation")
    if type(host_enabled) is not bool:
        raise ValueError("expected host control must be a Boolean")
    if not host_enabled:
        if receipt.writes:
            raise ValueError("disabled host instrumentation produced unexpected native files")
        return {}
    if not receipt.writes:
        raise ValueError("native publication has no completed host evidence")
    if len(receipt.writes) > limits.max_files:
        raise ValueError("native receipt exceeds the file count limit")
    root = repo.absolute() / paths.STATE_DIRNAME
    prefix = paths.entry(LedgerName.HOST_FINGERPRINT, registry=registry).prefix
    allowed = paths.raw_root(
        Path(paths.STATE_DIRNAME), LedgerName.HOST_FINGERPRINT, registry=registry
    ).as_posix()
    targets: list[tuple[str, Path, str]] = []
    for relative, digest in receipt.writes.items():
        if not relative.startswith(f"{allowed}/{date.replace('-', '/')}/"):
            raise ValueError("native receipt exceeds the invocation's host registry address")
        targets.append((relative, repo.absolute() / Path(relative), digest))
    # The bounded reader performs link, regular-file and race checks before decoding.
    # Reserve the remaining aggregate budget for each read, not only after parsing.
    total = 0
    for _, target, digest in targets:
        remaining = limits.max_total_bytes - total
        if remaining <= 0:
            raise ValueError("native receipt exceeds the total byte limit")
        verified = read_host_output(
            target,
            root=root,
            limits=replace(limits, max_file_bytes=min(limits.max_file_bytes, remaining)),
            prefix=prefix,
            physical_sha256=digest,
        )
        env = verified.envelope
        if (
            not env.writer.startswith("idhazh_rust.ledger.")
            or env.version != HOST_OUTPUT_VERSION
            or env.row_schema_version != HOST_OUTPUT_VERSION
            or env.covers != date
            or env.identity.model_dump() != expected.model_dump()
        ):
            raise ValueError("native host file has foreign schema, writer, date or invocation")
        total += verified.size_bytes
    return dict(receipt.writes)


def consume_host_publication(
    *,
    repo: Path,
    identity: WriterIdentity,
    date: str,
    receipt: HostPublicationReceipt | Path | None = None,
    limits: VerificationLimits | None = None,
    registry: paths.DoorRegistry | None = None,
    environment: Mapping[str, str] | None = None,
    host_enabled: bool = True,
) -> dict[str, str]:
    """Consume an explicit receipt or the native workflow handoff; legacy performs no I/O."""
    environment = os.environ if environment is None else environment
    mode = environment.get(MODE_ENV, "legacy")
    if mode not in {"legacy", "rust"}:
        raise ValueError("unknown host telemetry publication mode")
    if receipt is None and mode == "legacy":
        return {}
    if receipt is None:
        named = environment.get(RECEIPT_ENV)
        if not named:
            raise ValueError("native publication requires a completed host receipt")
        receipt = Path(named)
    host_enabled = host_enabled and ledger.accepts_new_rows(LedgerName.HOST_FINGERPRINT, 0)
    if limits is None:
        # Committed caller configuration owns the allocation bounds, never receipt claims.
        from idhazh.telemetry.host_event_files import HostEventFiles

        config_path = HostEventFiles._safe_path(
            repo.absolute(), Path("config") / "host-telemetry-experiment.json"
        )
        limits = NativeSettings.model_validate_json(
            read_bytes(config_path, CONFIG_BYTES)
        ).verification_limits
    if isinstance(receipt, Path):
        named_path = receipt if receipt.is_absolute() else repo.absolute() / receipt
        document = load_verification_document(named_path, root=repo.absolute(), limits=limits)
        writes = document.get("writes")
        if not isinstance(writes, dict) or len(writes) > limits.max_files:
            raise ValueError("native receipt has missing or unbounded completed writes")
        receipt = HostPublicationReceipt.model_validate(document)
    return verify_host_publication(
        receipt,
        repo=repo,
        identity=identity,
        date=date,
        limits=limits,
        registry=registry,
        host_enabled=host_enabled,
    )


def reconcile_host_writes(
    completed: Mapping[str, str],
    native: Mapping[str, str],
    *,
    registry: paths.DoorRegistry | None = None,
) -> dict[str, str]:
    """Retain Python-owned outputs without accepting a second host writer."""
    allowed = paths.raw_root(
        Path(paths.STATE_DIRNAME), LedgerName.HOST_FINGERPRINT, registry=registry
    ).as_posix()
    for path, digest in completed.items():
        if path.startswith(allowed + "/") and native.get(path) != digest:
            raise ValueError("completed output conflicts with native host ownership")
    return dict(completed) | dict(native)
