"""Does collection fetch only declared blobs and retain the full checkout's completed bytes?"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from conftest import FIXTURES_DIR
from gardener._garden import a_partial_clone, an_origin, git, lazy_fetches, quiet_git, write

from idhazh.contracts.publication_receipt import PublicationReceipt
from idhazh.council import registry, session
from utilities.council_publish import main
from utilities.publication_git import Repository

from ._tenants import a_venue, forget
from .test_publication import configuration

DATE = "2026-10-10"
SLUGS = ("first-judge", "second-judge")
PACKAGE = "named_input_judges"
FORBIDDEN = "state/unrelated/never-read.txt"
RETRY = (
    '{"deadline_seconds":{"default":300},"base_step_seconds":0.001,'
    '"ceiling_seconds":0.001,"ceiling_after":1}\n'
)


def seed(root: Path) -> tuple[Path, Path, dict[str, str]]:
    """A generated bounded repository with code, config, declared data and decoys."""
    target = configuration(root / "settings", SLUGS)
    a_venue(
        root / "modules",
        package=PACKAGE,
        slugs={slug: (1, ("state/results/" + slug,)) for slug in SLUGS},
        source=(FIXTURES_DIR / "council" / "named_input_tenant.py").read_text(encoding="utf-8"),
    )
    files = {
        "config/" + path.relative_to(target).as_posix(): path.read_text(encoding="utf-8")
        for path in target.rglob("*.json")
    }
    files.update(
        {
            "backend/" + path.relative_to(root / "modules").as_posix(): path.read_text(
                encoding="utf-8"
            )
            for path in (root / "modules").rglob("*.py")
        }
    )
    files["config/push-retry.json"] = RETRY
    files[FORBIDDEN] = "this blob must stay unavailable\n"
    for slug in SLUGS:
        files["state/index/" + slug + ".json"] = json.dumps({"judge": slug}) + "\n"
        for date in (DATE, "2026-10-09"):
            for name in ("first", "second"):
                files["state/input/" + slug + "/" + date + "/" + name + ".txt"] = (
                    slug + " " + date + " " + name + "\n"
                )
    origin, repo = an_origin(root, files)
    return origin, repo, files


def checkout_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    quiet_git(tmp_path, monkeypatch)
    monkeypatch.delenv("GIT_NO_LAZY_FETCH", raising=False)


def blob_available(repo: Path, oid: str) -> bool:
    """Ask real Git with the process's no-lazy-fetch switch, not an adapter's default."""
    return (
        subprocess.run(
            ["git", "cat-file", "-e", oid],
            cwd=repo,
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )


def collect(repo: Path, monkeypatch: pytest.MonkeyPatch) -> int:
    monkeypatch.syspath_prepend(str(repo / "backend"))
    monkeypatch.setattr(registry, "TENANT_PACKAGE", PACKAGE)
    monkeypatch.setattr(session, "COUNCIL_ROOT", repo / "backend" / "var" / "council")
    for slug in SLUGS:
        write(
            repo / "backend" / "var" / "council" / DATE / "verdicts" / slug / "completed.txt",
            slug + " completed unit\n",
        )
    forget(PACKAGE)
    try:
        return main(
            [
                "--repo-root",
                str(repo),
                "--config-root",
                str(repo / "config"),
                "--date",
                DATE,
                "--run-id",
                "2026-10-11-123",
                "--commit",
                git(repo, "rev-parse", "HEAD").strip(),
                "--job-started-at",
                str(int(datetime.now(UTC).timestamp())),
            ]
        )
    finally:
        forget(PACKAGE)


def test_partial_collector_fetches_only_named_inputs_and_matches_full_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checkout_environment(tmp_path, monkeypatch)
    origin, full, files = seed(tmp_path)
    full_origin = tmp_path / "full-origin.git"
    shutil.copytree(origin, full_origin)
    git(full, "remote", "set-url", "origin", str(full_origin))
    sparse = a_partial_clone(tmp_path, origin, "config", "backend", ".github")
    base = git(origin, "rev-parse", "main").strip()
    assert git(sparse, "rev-parse", "HEAD").strip() == base
    assert git(full, "rev-parse", "HEAD").strip() == base
    before_patterns = (sparse / ".git" / "info" / "sparse-checkout").read_bytes()
    monkeypatch.setenv("GIT_NO_LAZY_FETCH", "1")
    remote = Repository(origin)
    blobs = {
        path: git(origin, "rev-parse", base + ":" + path).strip()
        for path in files
        if path.startswith("state/")
    }
    declared = {
        path for path in blobs if path.startswith("state/index/") or ("/" + DATE + "/") in path
    }
    assert declared and FORBIDDEN not in declared
    assert all(not blob_available(sparse, oid) for oid in blobs.values())
    trace, packets = tmp_path / "git.trace", tmp_path / "git.packets"
    monkeypatch.setenv("GIT_TRACE", str(trace))
    monkeypatch.setenv("GIT_TRACE_PACKET", str(packets))
    assert collect(sparse, monkeypatch) == 0
    monkeypatch.delenv("GIT_TRACE")
    monkeypatch.delenv("GIT_TRACE_PACKET")
    assert lazy_fetches(trace) == len(declared)
    wants = set(re.findall(r"\bwant ([0-9a-f]{40})", packets.read_text(encoding="utf-8")))
    assert wants & set(blobs.values()) == {blobs[path] for path in declared}
    assert all(blob_available(sparse, blobs[path]) for path in declared)
    assert all(
        not blob_available(sparse, oid) for path, oid in blobs.items() if path not in declared
    )
    assert not (sparse / FORBIDDEN).exists()
    assert not (sparse / "state" / "optional").exists()
    assert git(sparse, "rev-parse", "HEAD").strip() == base
    assert (sparse / ".git" / "info" / "sparse-checkout").read_bytes() == before_patterns
    sparse_outputs = {
        "state/results/" + slug + "/" + DATE + ".txt": (
            sparse / "state" / "results" / slug / (DATE + ".txt")
        ).read_bytes()
        for slug in SLUGS
    }
    for path, content in sparse_outputs.items():
        entry = remote.entry("main", path)
        assert entry is not None and remote.blob(entry.oid) == content
    assert collect(full, monkeypatch) == 0
    for path, content in sparse_outputs.items():
        assert (full / path).read_bytes() == content
        entry = Repository(full_origin).entry("main", path)
        assert entry is not None and Repository(full_origin).blob(entry.oid) == content
    receipts = [
        PublicationReceipt.read(path)
        for path in (sparse / "backend" / "var" / "council" / "publication").iterdir()
    ]
    confirmed = {path for receipt in receipts for path in receipt.writes}
    assert set(sparse_outputs) <= confirmed
    assert not declared & confirmed, "imported inputs are not completed writes"


def test_unavailable_declared_blob_fails_without_publishing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checkout_environment(tmp_path, monkeypatch)
    origin, _, _ = seed(tmp_path)
    sparse = a_partial_clone(tmp_path, origin, "config", "backend")
    base = git(origin, "rev-parse", "main").strip()
    offline = origin.with_name("offline.git")
    origin.rename(offline)
    monkeypatch.setenv("GIT_NO_LAZY_FETCH", "1")
    assert collect(sparse, monkeypatch) == 1
    assert git(offline, "rev-parse", "main").strip() == base
    for slug in SLUGS:
        assert not (sparse / "state" / "results" / slug / (DATE + ".txt")).exists()


def test_sparse_judge_without_input_declaration_is_refused(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checkout_environment(tmp_path, monkeypatch)
    origin, _, _ = seed(tmp_path)
    sparse = a_partial_clone(tmp_path, origin, "config", "backend")
    path = sparse / "backend" / PACKAGE / "first_judge" / "tenant.py"
    source = path.read_text(encoding="utf-8")
    path.write_text(
        source.replace("def publication_inputs(", "def undeclared_inputs("),
        encoding="utf-8",
        newline="\n",
    )
    base = git(origin, "rev-parse", "main").strip()
    monkeypatch.setenv("GIT_NO_LAZY_FETCH", "1")
    trace = tmp_path / "git.trace"
    monkeypatch.setenv("GIT_TRACE", str(trace))
    assert collect(sparse, monkeypatch) == 1
    assert git(origin, "rev-parse", "main").strip() == base
    assert lazy_fetches(trace) == 0


def test_undeclared_read_cannot_fetch_and_completed_sibling_still_lands(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checkout_environment(tmp_path, monkeypatch)
    origin, _, _ = seed(tmp_path)
    sparse = a_partial_clone(tmp_path, origin, "config", "backend")
    oid = git(origin, "rev-parse", "main:" + FORBIDDEN).strip()
    path = sparse / "backend" / PACKAGE / "first_judge" / "tenant.py"
    source = path.read_text(encoding="utf-8")
    path.write_text(
        source.replace(
            "        root = state_dir.parent",
            "        import subprocess\n"
            '        subprocess.run(["git", "cat-file", "blob", "' + oid + '"],\n'
            "                       cwd=state_dir.parent, capture_output=True, check=True)\n"
            "        root = state_dir.parent",
        ),
        encoding="utf-8",
        newline="\n",
    )
    monkeypatch.setenv("GIT_NO_LAZY_FETCH", "1")
    assert not blob_available(sparse, oid)
    monkeypatch.delenv("GIT_NO_LAZY_FETCH")
    assert collect(sparse, monkeypatch) == 1
    assert "GIT_NO_LAZY_FETCH" not in os.environ, "the entrypoint restores its caller's environment"
    monkeypatch.setenv("GIT_NO_LAZY_FETCH", "1")
    assert not blob_available(sparse, oid)
    assert not (sparse / FORBIDDEN).exists()
    remote = Repository(origin)
    assert remote.entry("main", "state/results/first-judge/" + DATE + ".txt") is None
    path = "state/results/second-judge/" + DATE + ".txt"
    entry = remote.entry("main", path)
    assert entry is not None
    assert remote.blob(entry.oid) == (sparse / path).read_bytes()
