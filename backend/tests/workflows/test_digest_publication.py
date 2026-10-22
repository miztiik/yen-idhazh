"""Does digest publication preserve immutable inputs and stop invalid work?"""

import dataclasses
import json
from datetime import date, timedelta
from pathlib import Path

import pytest
from conftest import CONFIG_DIR
from gardener._garden import an_origin, git, quiet_git, write
from retention._trees import health_row

from idhazh import completed_writes, config, ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import Period, WriterIdentity
from idhazh.contracts.item_health import ItemStage
from idhazh.contracts.ledger_index import CompactEntry, CompactIndex
from idhazh.contracts.ledger_name import LedgerName
from idhazh.ledger import paths
from utilities import digest_assemble, digest_publish, publication_evidence
from utilities.publication_git import Repository
from utilities.publication_request import IntegrityError, PublicationRequest, Write
from utilities.publish_to_repo import Status, _verify_preparation


def a_repository(root: Path, files: dict[str, str]) -> tuple[Path, str]:
    repo = root / "checkout"
    repo.mkdir()
    git(repo, "init", "--quiet", "-b", "main")
    for name, text in files.items():
        write(repo / name, text)
    git(repo, "add", "--all")
    git(repo, "commit", "--quiet", "-m", "seed")
    return repo, git(repo, "rev-parse", "HEAD").strip()


def test_preparation_cannot_change_immutable_counts_inside_its_scope() -> None:
    source, fresh = "a" * 40, "b" * 40
    scope = digest_assemble.count_scope("2026-08-21")
    path = f"{scope}/completed.parquet"
    identity = WriterIdentity(
        run_id="2026-08-21-1", attempt=1, job=ServerJob.ASSEMBLE, shard=0,
        producer="tests.publisher", git_sha=source,
    )
    original = PublicationRequest(
        identity, "assembled", source, (scope,), (),
        {path: Write("c" * 64, None, immutable=True)},
        preparation_scopes=(scope,),
    )
    changed = dataclasses.replace(
        original, source_tip=fresh, writes={path: Write("d" * 64, None, immutable=True)}
    )
    with pytest.raises(IntegrityError, match="changed completed artifact"):
        _verify_preparation(original, changed, fresh)


def test_native_band_inputs_include_both_spans_without_retired_projection_roots() -> None:
    settings = config.load(CONFIG_DIR)
    through = "2026-10-09"
    widest = max(settings.appearance.console.window_presets)
    first = (date.fromisoformat(through) - timedelta(days=2 * widest - 1)).isoformat()
    inputs = digest_assemble.input_paths(date=through, settings=settings)
    day = first.replace("-", "/")
    assert f"frontend/public/digest/{day}/run.json" in inputs
    assert f"state/day-metrics/{day}.json" in inputs
    assert f"frontend/public/digest/{day}/digest.json" not in inputs
    assert not any(
        path.startswith(f"frontend/public/{root}/")
        for path in inputs for root in ("machine", "run-days", "day-metrics")
    )


def test_inputs_include_the_full_seen_and_published_consumer_windows() -> None:
    settings = config.load(CONFIG_DIR)
    settings.app.collect.seen_window_days = 900
    settings.app.collect.published_window_days = 1000
    through = "2026-10-09"
    inputs = digest_assemble.input_paths(date=through, settings=settings)

    for which, window in ((LedgerName.SEEN, 900), (LedgerName.PUBLISHED, 1000)):
        first = (date.fromisoformat(through) - timedelta(days=window)).isoformat()
        expected = (ledger.raw_root(Path("state"), which) / first.replace("-", "/")).as_posix()
        assert expected in inputs, "the reader includes the boundary day"
        excluded = (date.fromisoformat(first) - timedelta(days=1)).isoformat()
        outside = (ledger.raw_root(Path("state"), which) / excluded.replace("-", "/")).as_posix()
        assert outside not in inputs


@pytest.mark.parametrize("raw_only", [False, True], ids=["packed-and-raw", "raw-only"])
def test_unbounded_published_inputs_use_the_declared_start_and_all_index_heads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, raw_only: bool
) -> None:
    quiet_git(tmp_path, monkeypatch)
    which = LedgerName.PUBLISHED
    gardener = json.loads((CONFIG_DIR / "idhazh_gardener.json").read_text(encoding="utf-8"))
    gardener["first_ledger_year"] = "2023"
    seed = {
        "config/idhazh_gardener.json": json.dumps(gardener),
        "state/raw/published/2023/01/01/older-than-the-index.json": "old raw\n",
        "state/raw/published/2022/01/01/foreign-archive.json": "outside the declared start\n",
    }
    heads: set[str] = set()
    if not raw_only:
        for period, covers in (
            (Period.DAILY, "2024-02-01"),
            (Period.MONTHLY, "2024-03"),
            (Period.YEARLY, "2024"),
        ):
            head = paths.compact_path(Path("state"), which, period, covers).as_posix()
            heads.add(head)
            seed[head] = "head\n"
            seed[paths.compact_index_path(Path("state"), which, period).as_posix()] = CompactIndex(
                version=CompactIndex.schema_version(),
                ledger=which,
                period=period,
                entries=[CompactEntry(covers=covers, rows=1, bytes=5)],
            ).to_json()
    repo, tip = a_repository(tmp_path, seed)
    settings = config.load(CONFIG_DIR)
    settings.app.collect.published_window_days = -1

    inputs = digest_assemble.resolved_inputs(
        Repository(repo), tip, date="2026-10-09", settings=settings
    )

    assert "state/raw/published/2023/01/01" in inputs
    assert not any(path.startswith("state/raw/published/2022") for path in inputs)
    assert heads <= set(inputs)
    assert "state/raw/published" not in inputs


def test_work_adapter_lands_exact_completed_raw_not_pre_staged_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    quiet_git(tmp_path, monkeypatch)
    retry = {
        "deadline_seconds": {"default": 300},
        "base_step_seconds": 0.001,
        "ceiling_seconds": 0.001,
        "ceiling_after": 1,
    }
    origin, repo = an_origin(
        tmp_path, {"seed": "seed\n", "config/push-retry.json": json.dumps(retry) + "\n"}
    )
    source = git(repo, "rev-parse", "HEAD").strip()
    identity = WriterIdentity(
        run_id="2026-10-09-123",
        attempt=1,
        job=ServerJob.WORK,
        shard=0,
        producer="utilities.digest_publish",
        git_sha=source,
    )
    with completed_writes.collect() as evidence:
        ledger.persist(
            repo / "state",
            [health_row(day="2026-10-09", run=123, number=1, stage=ItemStage.PUBLISH)],
            ledger=LedgerName.ITEM_HEALTH,
            covers="2026-10-09",
            identity=identity,
        )
    publication_evidence.save(repo, identity, "record", evidence)
    write(repo / "state/foreign-staged.json", "foreign staged bytes\n")
    git(repo, "add", "state/foreign-staged.json")
    index = (repo / ".git/index").read_bytes()
    result = digest_publish.land(repo=repo, identity=identity, date="2026-10-09")
    assert result.status is Status.LANDED, result
    assert git(repo, "rev-parse", "HEAD").strip() == source
    assert (repo / ".git/index").read_bytes() == index
    remote = Repository(origin, git_dir=origin)
    assert remote.entry("main", "state/foreign-staged.json") is None
    for target in evidence:
        entry = remote.entry("main", target.relative_to(repo).as_posix())
        assert entry is not None and entry.mode == "100644"
        assert remote.blob(entry.oid) == target.read_bytes()


def test_plan_workflow_call_parses_and_bad_retry_config_stops_before_git_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from ._harness import _commit_call, _substitute

    quiet_git(tmp_path, monkeypatch)
    origin, repo = an_origin(tmp_path, {"seed": "seed\n", "config/push-retry.json": "{}\n"})
    monkeypatch.chdir(repo)
    source = git(repo, "rev-parse", "HEAD").strip()
    index = (repo / ".git/index").read_bytes()
    args, _ = _commit_call("plan")
    argv = [_substitute(value) for value in args]
    assert digest_publish.main(argv) == 2
    assert "deadline_seconds" in capsys.readouterr().err
    assert git(repo, "rev-parse", "HEAD").strip() == source
    assert git(origin, "rev-parse", "main").strip() == source
    assert (repo / ".git/index").read_bytes() == index
    write(repo / "config/push-retry.json", (CONFIG_DIR / "push-retry.json").read_text())
    assert digest_publish.main(argv) == 0
