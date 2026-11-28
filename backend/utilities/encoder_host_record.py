"""Which completed local fingerprint writes belong in an encoder score artifact?"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from idhazh import completed_writes
from idhazh.atomic_write import write_atomic_bytes
from idhazh.publication_paths import IntegrityError, contains, safe_file
from idhazh.telemetry import machine_evidence


@contextmanager
def stage_local_host(bundle: Path, day: str) -> Iterator[Path]:
    """Keep only verified native captures from this score's private state root."""
    scope = machine_evidence.raw_scope(machine_evidence.HOST, day)
    with TemporaryDirectory(prefix="encoder-host-") as directory:
        private = Path(directory)
        try:
            with completed_writes.collect() as writes:
                yield private / machine_evidence.STATE
        finally:
            for path, digest in writes.items():
                if not path.is_relative_to(private):
                    continue
                relative = path.relative_to(private).as_posix()
                if not contains(scope, relative):
                    continue
                data = safe_file(private, relative, exists=True).read_bytes()
                if hashlib.sha256(data).hexdigest() != digest:
                    raise IntegrityError("completed write bytes changed", (relative,))
                write_atomic_bytes(safe_file(bundle, relative, exists=False), data)
