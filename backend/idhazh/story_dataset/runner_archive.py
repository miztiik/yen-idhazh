"""Extract one hash-checked, bounded artifact ZIP without trusting its filenames."""

import hashlib
import zipfile
from pathlib import Path, PurePosixPath


def extract_archive(
    archive: Path, expected_sha256: str, output: Path, max_bytes: int = 64 * 1024 * 1024
) -> None:
    with archive.open("rb") as stream:
        checksum = hashlib.file_digest(stream, "sha256").hexdigest()
    if checksum != expected_sha256 or output.exists():
        raise ValueError("archive hash differs or extraction target already exists")
    with zipfile.ZipFile(archive) as bundle:
        members = bundle.infolist()
        if (
            sum(m.file_size for m in members) > max_bytes
            or len(members) > 1300
            or len({m.filename for m in members}) != len(members)
        ):
            raise ValueError("archive size or unique-file bound exceeded")
        for member in members:
            name = PurePosixPath(member.filename)
            if (
                not member.filename
                or member.orig_filename != member.filename
                or "\\" in member.filename
                or ":" in member.filename
                or name.is_absolute()
                or any(p in ("..", ".") for p in name.parts)
                or member.is_dir()
                or (member.external_attr >> 16) & 0o170000 == 0o120000
            ):
                raise ValueError("unsafe archive path, directory or symbolic link")
        output.mkdir(parents=True)
        for member in members:
            destination = output / member.filename
            destination.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(member) as source, destination.open("xb") as target:
                while block := source.read(1024 * 1024):
                    target.write(block)
