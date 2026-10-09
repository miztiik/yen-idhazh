"""Which changed files are confirmed writes inside a job's declared publication paths?"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Sequence
from pathlib import Path

from idhazh.contracts.publication_receipt import PublicationReceipt
from idhazh.council.publication import inside


def confirmed_paths(
    prefixes: Sequence[str], *, receipt_path: Path, changed: set[str]
) -> tuple[str, ...]:
    """Check the changed names, then read only the receipt's named output files.

    The receipt confirms bytes. The caller's declarations grant permission.
    Neither can stand in for the other.
    """
    receipt = PublicationReceipt.from_json(receipt_path.read_text(encoding="utf-8"))
    writer = receipt.identity
    for variable, expected in (
        ("GITHUB_JOB", writer.job.value),
        ("GITHUB_RUN_ATTEMPT", str(writer.attempt)),
        ("SHARD", str(writer.shard)),
        ("GITHUB_RUN_ID", writer.run_id.rsplit("-", 1)[-1]),
    ):
        actual = os.environ.get(variable)
        if actual and actual != expected:
            raise ValueError(f"{variable} does not match the publication receipt's writer")
    outside = sorted(path for path in changed | receipt.writes.keys() if not inside(path, prefixes))
    if outside:
        raise ValueError(f"{outside[0]} is outside the declared publication paths")
    unconfirmed = sorted(changed - receipt.writes.keys())
    if unconfirmed:
        raise ValueError(f"{unconfirmed[0]} has no completed write in this job's receipt")
    root = Path.cwd().resolve()
    for path, expected_digest in receipt.writes.items():
        held = Path(path)
        if not held.resolve().is_relative_to(root) or held.is_symlink() or not held.is_file():
            raise ValueError(f"{path} is not a confirmed regular file")
        if hashlib.sha256(held.read_bytes()).hexdigest() != expected_digest:
            raise ValueError(f"{path} changed after its publication write was recorded")
    return tuple(sorted(changed))
