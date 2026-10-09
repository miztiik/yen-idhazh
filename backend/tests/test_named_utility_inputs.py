"""Do utility reads stay inside their named inputs when neighbouring files grow?"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from types import ModuleType

import pytest
from conftest import REPO_ROOT, SEED_COMMIT

from idhazh.contracts.article import Article
from idhazh.contracts.base import derive_url_key
from idhazh.contracts.pipeline_tests import TRIAL_STATE_PREFIX
from utilities import (
    backfill_report,
    build_reference_dataset,
    capture_request_bodies,
    capture_server_argv,
    index_sizing,
    pipeline_test_ledgers,
    prompt_loop,
    sample_sheet,
    token_budget,
)
from utilities.named_inputs import day_files, named_files
from utilities.slow_mark_audit import average_seconds_by_module, report_modules


def a_digest(root: Path, day: str, title: str = "A bridge opened") -> Path:
    path = day_files(root, [day])[0]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"date": day, "items": [{"source_url": "https://example.org/bridge", "title": title}]}
        ),
        encoding="ascii",
        newline="\n",
    )
    return path


def test_day_addresses_do_not_discover_neighbours(tmp_path: Path) -> None:
    root = tmp_path / "frontend/public/digest"
    wanted = a_digest(root, "2026-09-01")
    unrelated = a_digest(root, "2026-09-02")
    unrelated.write_bytes(b"\xff")
    assert index_sizing.digest_paths(tmp_path, ["2026-09-01"]) == [wanted]
    assert token_budget.digest_paths(tmp_path, ["2026-09-01"]) == [wanted]
    assert len(build_reference_dataset.archive_candidates(root, ["2026-09-01"])) == 1
    assert len(sample_sheet.index(root, ["2026-09-01"])) == 1


@pytest.mark.parametrize("day", ["20260901", "2026-02-30", "../2026-09-01", ""])
def test_invalid_day_addresses_are_refused(tmp_path: Path, day: str) -> None:
    with pytest.raises(ValueError):
        day_files(tmp_path, [day])


def test_named_files_refuse_escape_and_empty_input(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        named_files(tmp_path, ["../other.json"])
    with pytest.raises(ValueError):
        named_files(tmp_path, [])


def test_backfill_report_reads_only_requested_days(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    a_digest(tmp_path, "2026-09-01")
    a_digest(tmp_path, "2026-09-02").write_bytes(b"\xff")
    assert backfill_report.main(["--digest-root", str(tmp_path), "--day", "2026-09-01"]) == 0
    printed = capsys.readouterr().out
    assert "2026-09-01" in printed
    assert "2026-09-02" not in printed
    assert "named days: 0 vectors over 1 items" in printed


def test_sample_resolution_reads_only_named_days_and_draws(tmp_path: Path) -> None:
    digests = tmp_path / "digest"
    named = a_digest(digests, "2026-09-01")
    a_digest(digests, "2026-09-02").write_bytes(b"\xff")
    # A second article on the named day, so the drawn pair is two articles.
    payload = json.loads(named.read_text(encoding="ascii"))
    payload["items"].append({"source_url": "https://example.org/tunnel", "title": "A tunnel"})
    named.write_text(json.dumps(payload), encoding="ascii", newline="\n")
    key = derive_url_key("https://example.org/bridge")
    other = derive_url_key("https://example.org/tunnel")
    draw = tmp_path / "draw.csv"
    with draw.open("w", encoding="ascii", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["date", "pair_key", "left_url_key", "right_url_key", "composite_score"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "date": "2026-09-01",
                "pair_key": "pair",
                "left_url_key": key,
                "right_url_key": other,
                "composite_score": "0.95",
            }
        )
    (tmp_path / "unrelated.csv").write_bytes(b"\xff")
    pairs, refused = sample_sheet.resolve(
        tmp_path, digests, line=0.94, corridor=0.02, days=["2026-09-01"], draws=["draw.csv"]
    )
    assert len(pairs) == 1
    assert not any(refused.values())
    (tmp_path / "labels.json").write_text('{"by_pair_key":{"pair":true}}', encoding="ascii")
    (tmp_path / "labels-batch-unrelated.json").write_bytes(b"\xff")
    assert (
        sample_sheet.harvest(
            tmp_path,
            tmp_path / "state",
            pairs,
            labeller="fixture",
            labelled_on="2026-09-03",
            batches=["labels.json"],
            run_id="2026-09-03-1",
            commit_sha=SEED_COMMIT,
        )
        == 1
    )


def test_junit_report_names_only_modules_it_ran(tmp_path: Path) -> None:
    report = tmp_path / "report.xml"
    report.write_text(
        '<testsuite><testcase classname="backend.tests.test_named.TestClass" time="2"/>'
        '<testcase classname="backend.tests.test_named" time="4"/></testsuite>',
        encoding="ascii",
    )
    assert report_modules(report, repo_root=tmp_path) == [tmp_path / "backend/tests/test_named.py"]
    assert average_seconds_by_module(report, repo_root=tmp_path) == {"test_named": 3.0}


@pytest.mark.parametrize("capture", [capture_request_bodies, capture_server_argv])
def test_capture_writes_only_named_models(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capture: ModuleType
) -> None:
    source = REPO_ROOT / "config/models/qwen3.5-9b-q4km.json"
    models = tmp_path / "models"
    models.mkdir()
    named = models / source.name
    named.write_bytes(source.read_bytes())
    (models / "unrelated.json").write_bytes(b"\xff")
    golden = tmp_path / "golden"
    monkeypatch.setattr(capture, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(capture, "GOLDEN_DIR", golden)

    capture.main([str(named)])

    assert json.loads((golden / named.name).read_text(encoding="utf-8"))
    assert not (golden / "unrelated.json").exists()
    with pytest.raises(SystemExit) as refused:
        capture.main([])
    assert refused.value.code == 2


def test_prompt_loop_ignores_unnamed_articles(tmp_path: Path, article_ok: Article) -> None:
    (tmp_path / "wanted.json").write_text(article_ok.to_json(), encoding="ascii", newline="\n")
    (tmp_path / "unrelated.json").write_bytes(b"\xff")

    articles, items = prompt_loop.load_frozen_articles(tmp_path, ["wanted.json"])

    assert articles == [article_ok]
    assert len(items) == 1
    assert items[0].source == article_ok.text


def test_trial_gather_copies_only_named_days(tmp_path: Path) -> None:
    state = tmp_path / "state"
    root = "fixture"
    # `gather` reads raw ledger files tier-first, from `state/raw/pipeline-tests/<root>/<ledger>/`
    # (`ledger.overlay_registry`), and traces from their own sibling root at
    # `state/trial-traces/pipeline-tests/<root>/` (module docstring). Written-to and
    # artifact-shaped paths differ for both cases, so both sides are tracked.
    written = (
        f"raw/{TRIAL_STATE_PREFIX}/{root}/feed-health/2026/09/01/a.parquet",
        f"trial-traces/{TRIAL_STATE_PREFIX}/{root}/2026/09/01/a.jsonl",
        f"raw/{TRIAL_STATE_PREFIX}/{root}/published/2026/09/01/a.parquet",
    )
    wanted = (
        f"{root}/raw/feed-health/2026/09/01/a.parquet",
        f"{root}/traces/2026/09/01/a.jsonl",
        f"{root}/raw/published/2026/09/01/a.parquet",
    )
    for name in written:
        path = state / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("one day", encoding="ascii")
    other = state / "raw" / TRIAL_STATE_PREFIX / root / "feed-health/2026/09/02/a.parquet"
    other.parent.mkdir(parents=True)
    other.write_bytes(b"\xff")
    tree = tmp_path / "artifact"

    assert pipeline_test_ledgers.gather(state, tree, roots=[root], days=["2026-09-01"]) == [root]
    assert sorted(
        path.relative_to(tree).as_posix() for path in tree.rglob("*") if path.is_file()
    ) == sorted(wanted)
    with pytest.raises(ValueError, match="name at least one UTC day"):
        pipeline_test_ledgers.gather(state, tree, roots=[root], days=[])
