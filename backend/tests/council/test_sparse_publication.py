"""Does collection fetch only declared blobs and publish the completed tenant bytes?"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from gardener._garden import a_bare_origin, a_partial_clone, git, lazy_fetches, quiet_git
from support.paths import FIXTURES_DIR

from idhazh import config
from idhazh.contracts.council_events import (
    CouncilExit,
    CouncilProgram,
    Diagnostic,
    NightPublished,
    ProgramFinished,
)
from idhazh.contracts.council_invocation import SelectedJudge, Selection
from idhazh.contracts.knobs.council import JudgeLifecycleStatus
from idhazh.contracts.publication_receipt import PublicationReceipt
from idhazh.council import event_log, outcome, registry, session
from idhazh.event_lines import payload
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


def seed(root: Path) -> tuple[Path, dict[str, str]]:
    """A generated bounded repository with code, config, declared data and decoys."""
    target = configuration(root / "settings", SLUGS)
    app_config = target / "idhazh.json"
    settings = json.loads(app_config.read_text(encoding="utf-8"))
    # These tests cover council collection, not host telemetry or its metadata lookup.
    settings["observability"]["host_telemetry_enabled"] = False
    app_config.write_text(json.dumps(settings), encoding="utf-8", newline="\n")
    a_venue(
        root / "modules",
        package=PACKAGE,
        slugs={slug: (1, ("state/results/" + slug,)) for slug in SLUGS},
        source=(FIXTURES_DIR / "council" / "named_input_tenant.py").read_text(encoding="utf-8"),
    )
    app = config.load(target).app
    names = (
        "idhazh.json",
        "llm_council.json",
        "sources.json",
        "taxonomy.json",
        "watchlist.json",
        "appearance.json",
        "ledgers.json",
        app.models_file,
        *(f"judges/{slug}.json" for slug in SLUGS),
    )
    files = {"config/" + name: (target / name).read_text(encoding="utf-8") for name in names}
    sources = (
        f"{PACKAGE}/__init__.py",
        *(
            f"{PACKAGE}/{slug.replace('-', '_')}/{name}"
            for slug in SLUGS
            for name in ("__init__.py", "tenant.py")
        ),
    )
    files.update(
        {
            "backend/" + name: (root / "modules" / name).read_text(encoding="utf-8")
            for name in sources
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
    return a_bare_origin(root, files), files


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


def collect(repo: Path, monkeypatch: pytest.MonkeyPatch, *, prepare: bool = True) -> int:
    monkeypatch.syspath_prepend(str(repo / "backend"))
    monkeypatch.setattr(registry, "TENANT_PACKAGE", PACKAGE)
    monkeypatch.setattr(session, "COUNCIL_ROOT", repo / "backend" / "var" / "council")
    commit = git(repo, "rev-parse", "HEAD").strip()
    selected = Selection(
        version=Selection.schema_version(),
        run_id="2026-10-11-123",
        attempt=1,
        git_sha=commit,
        mode="manual",
        anchor_date=DATE,
        window=(DATE,),
        judges=tuple(
            SelectedJudge(tenant=slug, status=JudgeLifecycleStatus.ACTIVE, dates=(DATE,), shards=1)
            for slug in SLUGS
        ),
    )
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    monkeypatch.setenv("COUNCIL_SELECTION", selected.model_dump_json())
    forget(PACKAGE)
    try:
        if prepare:
            monkeypatch.setenv(
                "COUNCIL_EVENT_FILE", str(session.COUNCIL_ROOT / "events" / "planner.jsonl")
            )
            event_log.install()
            outcome.run(CouncilProgram.PREPARE, lambda: _prepare(repo, selected))
            monkeypatch.delenv("COUNCIL_EVENT_FILE")
            event_log.install()
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


def _prepare(repo: Path, selected: Selection) -> int:
    return outcome.of_results(
        session.prepare(
            config.load_council(repo / "config"),
            date=DATE,
            run_id=selected.run_id,
            selection=selected,
        )
    )


def test_partial_collector_fetches_only_named_inputs_and_publishes_expected_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checkout_environment(tmp_path, monkeypatch)
    origin, files = seed(tmp_path)
    sparse = a_partial_clone(tmp_path, origin, "config", "backend", ".github")
    base = git(origin, "rev-parse", "main").strip()
    assert git(sparse, "rev-parse", "HEAD").strip() == base
    before_patterns = (sparse / ".git" / "info" / "sparse-checkout").read_bytes()
    monkeypatch.setenv("GIT_NO_LAZY_FETCH", "1")
    remote = Repository(origin, git_dir=origin)
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
    assert lazy_fetches(trace) > 0
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
    expected_outputs = {}
    for slug in SLUGS:
        path = "state/results/" + slug + "/" + DATE + ".txt"
        input_paths = (
            "state/input/" + slug + "/" + DATE + "/first.txt",
            "state/input/" + slug + "/" + DATE + "/second.txt",
            "state/index/" + slug + ".json",
        )
        expected = "".join(files[name] for name in input_paths) + slug + " completed unit\n"
        expected_outputs[path] = expected.encode("utf-8")
    assert sparse_outputs == expected_outputs
    for path, content in sparse_outputs.items():
        entry = remote.entry("main", path)
        assert entry is not None and remote.blob(entry.oid) == content
    receipts = [
        PublicationReceipt.read(path)
        for path in (
            sparse / "backend" / "var" / "council" / "publication" / f"{index:04}.json"
            for index in range(3)
        )
        if path.is_file()
    ]
    confirmed = {path for receipt in receipts for path in receipt.writes}
    assert set(sparse_outputs) <= confirmed
    assert not declared & confirmed, "imported inputs are not completed writes"


def test_unavailable_declared_blob_fails_without_publishing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    checkout_environment(tmp_path, monkeypatch)
    origin, _ = seed(tmp_path)
    sparse = a_partial_clone(tmp_path, origin, "config", "backend")
    base = git(origin, "rev-parse", "main").strip()
    offline = origin.with_name("offline.git")
    origin.rename(offline)
    monkeypatch.setenv("GIT_NO_LAZY_FETCH", "1")
    with caplog.at_level(logging.INFO):
        assert collect(sparse, monkeypatch) == 1
    events = tuple(payload(record) for record in caplog.records)
    assert any(
        isinstance(event, Diagnostic) and event.error == "ExceptionGroup" for event in events
    ), "the unavailable declared inputs must fail settlement"
    published = [event for event in events if isinstance(event, NightPublished)]
    assert len(published) == 1
    assert (published[0].landing, published[0].pushes, published[0].writes) == (
        "preparation-failure",
        0,
        1,
    )
    assert git(offline, "rev-parse", "main").strip() == base
    for slug in SLUGS:
        assert not (sparse / "state" / "results" / slug / (DATE + ".txt")).exists()


def test_sparse_judge_without_input_declaration_is_refused(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    checkout_environment(tmp_path, monkeypatch)
    origin, _ = seed(tmp_path)
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
    with caplog.at_level(logging.INFO):
        assert collect(sparse, monkeypatch, prepare=False) == 2
    events = tuple(payload(record) for record in caplog.records)
    assert any(
        isinstance(event, Diagnostic) and event.error == "JudgeRefusalError" for event in events
    ), "missing input declaration must cause the refusal"
    published = [event for event in events if isinstance(event, NightPublished)]
    assert published == [], "pre-work refusal never reaches publication"
    finished = [event for event in events if isinstance(event, ProgramFinished)]
    assert len(finished) == 1
    assert (finished[0].program, finished[0].code) == (
        CouncilProgram.PUBLISH,
        CouncilExit.REFUSED,
    )
    assert git(origin, "rev-parse", "main").strip() == base
    assert lazy_fetches(trace) == 0


def test_undeclared_read_cannot_fetch_and_completed_sibling_still_lands(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checkout_environment(tmp_path, monkeypatch)
    origin, _ = seed(tmp_path)
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
    remote = Repository(origin, git_dir=origin)
    assert remote.entry("main", "state/results/first-judge/" + DATE + ".txt") is None
    output_path = "state/results/second-judge/" + DATE + ".txt"
    entry = remote.entry("main", output_path)
    assert entry is not None
    assert remote.blob(entry.oid) == (sparse / output_path).read_bytes()
